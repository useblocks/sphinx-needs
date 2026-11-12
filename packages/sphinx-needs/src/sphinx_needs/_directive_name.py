"""Which directive names a need type's needs are written with.

Every need type is written ``.. need:<directive>::`` (and ```` ```{need:<directive>} ````
in MyST), served by the ``need`` domain (:class:`NeedsDomain`), whatever else the
project loads. The bare ``.. <directive>::`` is decided per type by
``needs_directive_name`` and the type's ``directive_name`` key
(:func:`directive_name_of`), when the type's directive is registered
(:func:`register_need_directive`):

- ``claim`` (and unset, which behaves as ``claim``): the bare name is the need's, over
  another extension's directive of that name;
- ``yield``: the bare name is the need's unless another directive has it, which keeps it;
- ``qualified``: the bare name is never registered.

**When "another directive has it" is decided.** At the moment the type's directive is
registered: sphinx-needs' ``load_config`` (``config-inited``, priority 500) for a
configured type, or the ``add_need_type`` call for a type an extension adds (at its
documented time, a ``config-inited`` handler). By then every extension's ``setup()`` has
run, so every directive registered in ``setup()`` (sphinx-design's, sphinx-subfigure's)
is seen, in any ``extensions`` order. What is seen is what a bare name resolves to in a
Sphinx build: docutils' directive registry (as Sphinx's own ``app.add_directive``
warning reads it), the ``std`` domain, and the ``primary_domain``; for ``yield``, also
docutils' own directives that Sphinx has not registered (``image``, ``role``, ...),
which docutils loads on their first use.

A directive registered after that is not seen, and replaces the need's bare name
whatever the mode, as it did before this choice existed: one a ``config-inited``
handler registers after sphinx-needs' has run (a priority above 500, or 500 in an
extension listed after sphinx-needs, as sphinx-design's ``sd_custom_directives`` are),
or one registered at ``builder-inited`` or later. Sphinx warns about it
(``app.add_directive``) only when it is registered without ``override=True``.

**What is reported.** A bare name another directive has, under a type whose mode is
unset (neither ``needs_directive_name`` nor its ``directive_name`` is given), is one
``needs.directive_name_clash`` warning when the type's directive is registered -- in
place of Sphinx's ``app.add_directive`` warning, which said the directive would not be
overridden although it was. The warning is not emitted where ``app.add_directive`` is
suppressed (``suppress_warnings``), which silenced the same clash before. A mode that is
given is the project's choice, and is not reported.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Final, Literal, cast

from docutils.parsers.rst import Directive
from docutils.parsers.rst import directives as rst_directives
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.domains import Domain
from sphinx.util.logging import getLogger, is_suppressed_warning

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.logging import log_warning

LOGGER = getLogger(__name__)

DirectiveNameMode = Literal["claim", "yield", "qualified"]

#: The values of ``needs_directive_name`` and of a need type's ``directive_name``.
DIRECTIVE_NAME_VALUES: Final[tuple[DirectiveNameMode, ...]] = (
    "claim",
    "yield",
    "qualified",
)

#: The domain every need type's qualified spelling is in: ``.. need:<directive>::``.
QUALIFIER: Final = "need"

#: The text a finding names the values with.
VALUES_TEXT: Final = "one of 'claim', 'yield' and 'qualified'"


def need_type_of(directive_name: str) -> str:
    """The need type a need directive's name is of: the name, qualified or not."""
    return directive_name.removeprefix(f"{QUALIFIER}:")


class NeedsDomain(Domain):
    """The ``need`` domain: each need type's directive under its qualified name.

    It holds no objects, roles or data. Its :meth:`directive` serves the need directive
    for every need type of the build, by the type's ``directive``, whenever the type was
    added; any other name is no directive of the domain.
    """

    name = QUALIFIER
    label = "Sphinx-Needs"

    def directive(self, name: str) -> type[Directive] | None:
        """The need directive for a need type's directive name, else the domain's own."""
        if name not in self.directives and name in _need_type_directives(
            self.env.config
        ):
            from sphinx_needs.directives.need import NeedDirective  # avoid a cycle

            # the instance's own mapping (Domain copies the class's), so a later build
            # of the application starts from none
            self.directives[name] = NeedDirective
        # Sphinx 7 declares the adapter a callable, Sphinx 8 and later a directive class
        return cast("type[Directive] | None", super().directive(name))

    def clear_doc(self, docname: str) -> None:
        """The domain stores nothing for a document."""

    def merge_domaindata(
        self, docnames: Iterable[str], otherdata: dict[str, Any]
    ) -> None:
        """The domain stores nothing to merge from a parallel read."""

    def resolve_any_xref(self, *args: Any, **kwargs: Any) -> list[tuple[str, Any]]:
        """The domain has no objects an ``any`` reference resolves to."""
        return []


def _need_type_directives(config: Config) -> set[str]:
    """The directive names of the need types of the build."""
    types = NeedsSphinxConfig(config).types
    if not isinstance(types, list):
        return set()
    return {t["directive"] for t in types}


def directive_name_of(config: Config, directive: str) -> tuple[DirectiveNameMode, bool]:
    """What the bare directive name of the need type ``directive`` is, and whether the
    project gave it.

    The type's ``directive_name``, else ``needs_directive_name``, else ``claim``, not
    given. A value that is none of :data:`DIRECTIVE_NAME_VALUES` is reported where it
    is read (:func:`check_directive_name_config`, and the type's entry), and is unset.
    """
    types = NeedsSphinxConfig(config).types
    if isinstance(types, list):
        for need_type in types:
            if need_type["directive"] == directive:
                value = need_type.get("directive_name")
                if value in DIRECTIVE_NAME_VALUES:
                    return value, True
                break
    value = getattr(config, "needs_directive_name", None)
    if value in DIRECTIVE_NAME_VALUES:
        return value, True
    return "claim", False


def check_directive_name_config(config: Config) -> None:
    """Report a ``needs_directive_name`` that is none of the values; it is then unset."""
    value = getattr(config, "needs_directive_name", None)
    if value is not None and value not in DIRECTIVE_NAME_VALUES:
        log_warning(
            LOGGER,
            f"needs_directive_name is {value!r}, which is not {VALUES_TEXT}; "
            "it is ignored (a need type's bare directive name is the need's, and a "
            "clash is reported)",
            "config",
            None,
        )


def other_owner(
    app: Sphinx, name: str, *, builtins: bool = False
) -> tuple[str, bool] | None:
    """What a bare ``.. <name>::`` resolves to other than the need directive, as a
    warning names it, and whether it is a domain's directive; ``None`` when nothing
    else has the name.

    Sphinx looks a bare name up in the current default domain (``primary_domain``,
    unless a page changes it), then the ``std`` domain, then docutils' registry: a
    domain's directive wins over every registered one. With ``builtins``, docutils'
    own directives count too where Sphinx has not registered them (``image``,
    ``role``, ``raw``, ...), which docutils loads on their first use; Sphinx's
    ``app.add_directive`` warning never counted them.
    """
    from sphinx_needs.directives.need import NeedDirective  # avoid a cycle

    primary = app.config.primary_domain
    for domain_name in dict.fromkeys([primary, "std"]):
        if not domain_name:
            continue
        domain = app.registry.domains.get(domain_name)
        if domain is None:
            continue
        if name in domain.directives or name in app.registry.domain_directives.get(
            domain_name, {}
        ):
            return f"the {domain_name} domain's directive '{domain_name}:{name}'", True
    # the registry Sphinx's own ``is_directive_registered`` reads, which docutils'
    # stubs do not declare
    registry = rst_directives._directives  # ty: ignore[unresolved-attribute]
    registered = registry.get(name)
    if registered is NeedDirective:
        return None
    if registered is None:
        # docutils' table of the directives it loads on first use
        lazy = rst_directives._directive_registry  # ty: ignore[unresolved-attribute]
        return (
            (f"docutils' directive {name!r}", False)
            if builtins and name in lazy
            else None
        )
    module = getattr(registered, "__module__", "") or ""
    if module == "builtins":
        # a class a conf.py defines: its module is no name a project knows it by
        module = ""
    qualname = getattr(registered, "__qualname__", None) or repr(registered)
    return f"the directive {module + '.' if module else ''}{qualname}", False


def register_need_directive(app: Sphinx, name: str) -> None:
    """Register the bare directive name of the need type ``name``, as its mode says.

    A name that already holds the need directive itself is left alone, so a type
    registers its directive once whichever of ``load_config`` and ``add_need_type``
    comes first (#2271). The qualified name needs no registration: the ``need`` domain
    serves it (:class:`NeedsDomain`).
    """
    from sphinx_needs.directives.need import NeedDirective  # avoid a cycle

    registry = rst_directives._directives  # ty: ignore[unresolved-attribute]
    if registry.get(name) is NeedDirective:
        return
    mode, given = directive_name_of(app.config, name)
    if mode == "qualified":
        return
    # yield leaves the bare name to any other directive, docutils' own included; claim
    # reports what Sphinx's own warning reported (and the domains, which it did not)
    found = other_owner(app, name, builtins=mode == "yield")
    if found is None:
        app.add_directive(name, NeedDirective)
        return
    if mode == "yield":
        return
    # claim: the need takes the bare name, as it always has; the clash is reported
    # once, by sphinx-needs rather than by Sphinx (``override``), unless the project
    # chose the mode or silences Sphinx's warning for the same clash
    if not given and not is_suppressed_warning(
        "app", "add_directive", app.config.suppress_warnings
    ):
        owner, domain_owned = found
        fix = (
            # a domain's directive is looked up first: the bare name was never the need
            f"a bare '.. {name}::' runs it, as Sphinx looks it up first. Write "
            f"'.. {QUALIFIER}:{name}::' for the need, and set needs_directive_name "
            "(or the type's directive_name) to 'yield' to say so"
            if domain_owned
            else f"a bare '.. {name}::' is the need. Set needs_directive_name (or the "
            "type's directive_name) to 'claim' to keep it so, or to 'yield' to leave "
            f"the bare name to the other directive and write '.. {QUALIFIER}:{name}::' "
            "for the need"
        )
        log_warning(
            LOGGER,
            f"need type {name!r}: the directive name {name!r} is also {owner}; {fix}",
            "directive_name_clash",
            None,
        )
    app.add_directive(name, NeedDirective, override=True)
