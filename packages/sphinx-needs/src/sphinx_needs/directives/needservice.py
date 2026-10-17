from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst.states import RSTState, RSTStateMachine
from docutils.statemachine import StringList
from sphinx.util.docutils import SphinxDirective
from sphinx_data_viewer.api import get_data_viewer_node

from sphinx_needs.api import InvalidNeedException, add_need
from sphinx_needs.config import _NEEDS_CONFIG, NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItemSourceService
from sphinx_needs.needs_schema import FieldsSchema
from sphinx_needs.services.base import BaseService
from sphinx_needs.services.config.github import GITHUB_SERVICES
from sphinx_needs.services.github import GithubService
from sphinx_needs.services.manager import NeedsServiceException
from sphinx_needs.utils import DummyOptionSpec, add_doc, coerce_to_boolean


def _unconfigured_builtin_hint(service: BaseService, need_type: object) -> str:
    """The fix for a GitHub service need whose type is unknown because the built-in
    service that adds the type is not configured, or ``""``.

    A ``GithubService`` -- a custom entry built on the class, such as a GitHub
    Enterprise one, included -- creates needs of its ``gh_type``'s type, which only the
    built-in service of that type adds, when ``needs_services`` configures it.
    """
    if not isinstance(service, GithubService):
        return ""
    builtin = {gh_type: name for name, gh_type in GITHUB_SERVICES.items()}.get(
        service.gh_type
    )
    if (
        builtin is None
        or need_type != service.gh_type
        or builtin in _NEEDS_CONFIG.builtin_services
    ):
        return ""
    return (
        f" The {need_type!r} type is registered by the built-in {builtin!r} service: "
        f"configure needs_services[{builtin!r}] (an empty entry is enough), or "
        f"declare the {need_type!r} need type."
    )


class Needservice(nodes.General, nodes.Element):
    pass


class NeedserviceDirective(SphinxDirective):
    has_content = True

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True

    option_spec: Final[DummyOptionSpec] = DummyOptionSpec()

    def __init__(
        self,
        name: str,
        arguments: list[str],
        options: dict[str, Any],
        content: StringList,
        lineno: int,
        content_offset: int,
        block_text: str,
        state: RSTState,
        state_machine: RSTStateMachine,
    ):
        super().__init__(
            name,
            arguments,
            options,
            content,
            lineno,
            content_offset,
            block_text,
            state,
            state_machine,
        )
        self.log = get_logger(__name__)

    def run(self) -> Sequence[nodes.Node]:
        needs_config = NeedsSphinxConfig(self.env.config)
        needs_schema = SphinxNeedsData(self.env).get_schema()
        needs_services = SphinxNeedsData(self.env).get_or_create_services()

        # the service first, before its options: a built-in service's control options
        # are fields only once a service registered them, so an unconfigured built-in
        # would otherwise be one "Unknown option" warning per option before the one
        # warning that names the cause
        service_name = self.arguments[0]
        try:
            service = needs_services.get(service_name)
        except NeedsServiceException as err:
            # not registered: an unknown name, an unconfigured built-in, or a service
            # whose configuration was refused (and reported) when it was registered
            log_warning(
                self.log, str(err), "load_service_need", location=self.get_location()
            )
            return []

        try:
            self._process_options(needs_schema)
        except (AssertionError, ValueError):
            return []

        need_types = needs_config.types
        all_data = needs_config.service_all_data
        section = []

        if "debug" not in self.options:
            service_data = service.request_from_directive(self)
            core_options = {
                "debug",
                "type",
                "id",
                "collapse",
                "hide",
                "jinja_content",
                "status",
                "tags",
                "style",
                "layout",
                "template",
                "pre_template",
                "post_template",
                "constraints",
                "content",
            }
            #: need type -> the options of a datum of that type
            defined_by_type: dict[str | None, set[str]] = {}
            for datum in service_data:
                options = {}

                try:
                    content = datum["content"].split("\n")
                except KeyError:
                    content = []

                content.extend(self.content)

                if "type" not in datum:
                    # Use the first defined type, if nothing got defined by service (should not be the case)
                    need_type = need_types[0]["directive"]
                else:
                    need_type = datum["type"]
                    del datum["type"]

                if "title" not in datum:
                    need_title = ""
                else:
                    need_title = datum["title"]
                    del datum["title"]

                # We need to check if all given options from services are really available as configured
                # needs_fields or needs_links, for a need of the datum's type
                type_key = need_type if isinstance(need_type, str) else None
                if (defined_options := defined_by_type.get(type_key)) is None:
                    type_schema = needs_schema.for_type(type_key)
                    defined_options = defined_by_type[type_key] = {
                        *core_options,
                        *type_schema.iter_extra_field_names(),
                        *type_schema.iter_link_field_names(),
                    }
                missing_options = {}
                for element in datum:
                    if element not in defined_options:
                        missing_options[element] = datum[element]

                # Finally delete not found options
                for missing_option in missing_options:
                    del datum[missing_option]

                if all_data:
                    for name, value in missing_options.items():
                        content.append(f"\n:{name}: {value}")

                # content.insert(0, '.. code-block:: text\n')
                options["content"] = "\n".join(content)
                # Replace values in datum with calculated/checked ones.
                datum.update(options)

                # ToDo: Tags and Status are not set (but exist in data)
                source = NeedItemSourceService(
                    docname=self.env.docname, lineno=self.lineno
                )
                try:
                    section += add_need(
                        app=self.env.app,
                        state=self.state,
                        need_source=source,
                        need_type=need_type,
                        title=need_title,
                        **datum,
                    )
                except InvalidNeedException as err:
                    hint = (
                        _unconfigured_builtin_hint(service, need_type)
                        if err.type == "invalid_type"
                        else ""
                    )
                    log_warning(
                        self.log,
                        f"Service need could not be created: {err.message}{hint}",
                        "load_service_need",
                        location=self.get_location(),
                    )
        else:
            try:
                service_debug_data = service.debug(self.options)
            except NotImplementedError:
                service_debug_data = {
                    "error": f'Service {service_name} does not support "debug" output.'
                }
            viewer_node = get_data_viewer_node(
                title="Debug data", data=service_debug_data
            )
            section.append(viewer_node)

        add_doc(self.env, self.env.docname)

        return section

    def _process_options(self, needs_schema: FieldsSchema) -> None:
        """
        Process the options of the directive and coerce them to the correct value.
        """
        link_keys = set(needs_schema.iter_link_field_names())
        extra_keys = set(needs_schema.iter_extra_field_names())
        for key in list(self.options):
            value: str | None = self.options[key]
            try:
                match key:
                    case "debug":
                        self.options[key] = directives.flag(self.options[key])
                    case (
                        "id"
                        | "status"
                        | "tags"
                        | "style"
                        | "layout"
                        | "template"
                        | "pre_template"
                        | "post_template"
                        | "constraints"
                        | "type"  # TODO this is only used by the github service
                    ):
                        assert value, f"'{key}' must not be empty"
                    case "collapse" | "hide" | "jinja_content":
                        self.options[key] = coerce_to_boolean(value)
                    case key if key in extra_keys:
                        self.options[key] = value or ""
                    case key if key in link_keys:
                        self.options[key] = value or ""
                    case _:
                        log_warning(
                            self.log,
                            f"Unknown option '{key}'",
                            "directive",
                            location=self.get_location(),
                        )
                        self.options.pop(key, None)
            except (AssertionError, ValueError) as err:
                log_warning(
                    self.log,
                    f"Invalid value for '{key}' option: {err}",
                    "directive",
                    location=self.get_location(),
                )
                raise
