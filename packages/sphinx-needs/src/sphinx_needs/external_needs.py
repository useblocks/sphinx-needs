from __future__ import annotations

import os

import requests
from requests_file import FileAdapter
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment

from sphinx_needs import exchange
from sphinx_needs._jinja import compile_template
from sphinx_needs.api import InvalidNeedException, add_external_need, del_need
from sphinx_needs.api.need import _record_params
from sphinx_needs.config import ExternalSource, NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItemSourceExternal
from sphinx_needs.utils import clean_log, import_prefix_link_edit

log = get_logger(__name__)


def load_external_needs(
    app: Sphinx, env: BuildEnvironment, _docnames: list[str]
) -> None:
    """Load needs from configured external sources."""
    needs_config = NeedsSphinxConfig(app.config)
    data = SphinxNeedsData(env)
    needs_schema = data.get_schema()
    # the ids this pass has added: an external need of one of them is a duplicate
    # across this build's sources, any other is left from the previous build
    added: set[str] = set()

    for idx, source in enumerate(needs_config.external_needs):
        if "base_url" not in source:
            raise NeedsExternalException(
                f"base_url must be configured in external_needs item {idx}."
            )

        if source["base_url"].endswith("/"):
            source["base_url"] = source["base_url"][:-1]

        target_url = source.get("target_url", "")

        if source.get("json_url", False) and source.get("json_path", False):
            raise NeedsExternalException(
                clean_log(
                    "json_path and json_url are both configured, but only one is allowed.\n"
                    f"json_path: {source['json_path']}\n"
                    f"json_url: {source['json_url']}."
                )
            )
        elif not (source.get("json_url", False) or source.get("json_path", False)):
            raise NeedsExternalException(
                "json_path or json_url must be configured to use external_needs."
            )

        source_str = source.get("json_url", "") or source.get("json_path", "")
        try:
            document = _read_source(app, source)
            selected = document.select_version(source.get("version") or None)
        except (exchange.ExchangeError, _UnreadableSource) as err:
            # a source no need can be read from: one warning, and the build goes on
            log_warning(
                log,
                clean_log(
                    f"Could not load external needs from {source_str!r}: {err.message}"
                ),
                "external_needs",
                location=None,
            )
            continue

        records = selected.records()
        for diagnostic in (
            *selected.diagnostics,
            *(d for r in records for d in r.diagnostics),
        ):
            log_warning(
                log,
                clean_log(
                    f"External needs source {source_str!r}: {diagnostic.message} "
                    f"(at {diagnostic.path})"
                ),
                "external_needs",
                location=None,
            )

        log.debug(f"Loading {len(records)} needs.")

        # the prefix is added as written, to the ids and to the links between the
        # file's needs
        id_prefix = source.get("id_prefix", "")
        needs = {r.key: r.fields for r in records}
        import_prefix_link_edit(needs, id_prefix, needs_schema.iter_link_field_names())

        # Pre-compile target_url template once (avoids re-parsing per need)
        target_tpl = (
            compile_template(target_url, autoescape=False) if target_url else None
        )

        # collect keys for warning logs, so that we only log one warning per key
        unknown_keys: set[str] = set()

        for key, need in needs.items():
            # Replace id, to get unique ids
            ext_need_id = id_prefix + key
            try:
                need_params, _ = _record_params(
                    need, needs_schema, reader="external", unknown_keys=unknown_keys
                )
            except InvalidNeedException as err:
                _refuse_need(ext_need_id, source_str, err)
                continue
            need_params["id"] = ext_need_id
            need_params["external_css"] = source.get("css_class")

            if target_tpl:
                # render jinja content
                cal_target_url = target_tpl.render({"need": need})
                external_url = f"{source['base_url']}/{cal_target_url}"
            else:
                external_url = f"{source['base_url']}/{need.get('docname', '__error__')}.html#{key}"

            existing = data.get_needs_mutable().get(ext_need_id)
            if (
                existing is not None
                and existing["is_external"]
                and ext_need_id not in added
            ):
                # an external need left from a previous build (an incremental build
                # keeps the environment): replaced. One added in this pass, by this
                # source or another, is a duplicate: ``add_external_need`` refuses it
                del_need(app, ext_need_id)

            try:
                add_external_need(
                    app,
                    need_source=NeedItemSourceExternal(url=external_url),
                    allow_type_coercion=source.get("allow_type_coercion", True),
                    **need_params,
                )
            except InvalidNeedException as err:
                _refuse_need(ext_need_id, source_str, err)
            else:
                added.add(ext_need_id)

        if unknown_keys:
            log_warning(
                log,
                clean_log(
                    f"Unknown keys in external need source {source_str!r}: {sorted(unknown_keys)!r}"
                ),
                "unknown_external_keys",
                location=None,
            )


def _read_source(app: Sphinx, source: ExternalSource) -> exchange.Document:
    """Download or read an external source's needs.json.

    :raises _UnreadableSource: If it cannot be obtained.
    :raises exchange.ExchangeError: If it cannot be read.
    """
    if json_url := source.get("json_url"):
        log.info(clean_log(f"Loading external needs from url {json_url}."))
        s = requests.Session()
        s.mount("file://", FileAdapter())
        try:
            response = s.get(json_url)
        except Exception as e:
            raise _UnreadableSource(f"getting it failed: {e}") from e
        return exchange.parse(response.content)

    json_path = source["json_path"]
    if not os.path.isabs(json_path):
        json_path = os.path.join(app.confdir, json_path)
    if not os.path.exists(json_path):
        raise _UnreadableSource(f"the file {json_path} does not exist")
    return exchange.load(json_path)


class _UnreadableSource(Exception):
    """An external source's needs.json that cannot be obtained."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _refuse_need(need_id: str, source_str: str, err: InvalidNeedException) -> None:
    log_warning(
        log,
        clean_log(
            f"External need {need_id!r} in {source_str!r} could not be added: {err.message}"
        ),
        "load_external_need",
        location=None,
    )


class NeedsExternalException(BaseException):
    """Raised for an external source whose configuration is wrong (no ``base_url``;
    both or neither of ``json_path`` and ``json_url``). A source whose needs.json cannot
    be obtained or read is a ``needs.external_needs`` warning instead."""
