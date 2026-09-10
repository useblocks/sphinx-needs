"""The need fields this package declares, and their JSON schema.

One table for the two writers. The extension registers these fields with
sphinx-needs at ``config-inited`` so the directives may set them; the
converter writes the same declarations into the ``needs_schema`` of the
``needs.json`` it produces, so the file says what the type of each of its
fields is. A consumer of that file -- a schema check, a metamodel validator,
S-CORE's tooling -- learns the types from the file instead of having to load
this extension into a Sphinx build.

**Nothing in this module may import Sphinx.** The converter runs as a build
action, without the documentation toolchain installed.

The declarations are the *format*, not a description of one report: a field is
declared whether or not the cases at hand happen to populate it, the way
sphinx-needs declares every registered field.
"""

from typing import Iterable, Mapping

#: ``name -> (JSON type, description)`` for every field declared under a fixed
#: name. The build registers all of them, on test-file, test-suite and
#: test-case needs alike; the converter writes test-case needs and therefore
#: declares :data:`CASE_FIELDS`.
FIELDS: dict[str, tuple[str, str]] = {
    "suite": ("string", "Test suite name"),
    "case": ("string", "Test case name"),
    # pytest spells a parameterised case ``name[param]``; the two halves are
    # split apart so a filter can address either.
    "case_name": ("string", "Test case name without its parameter"),
    "case_parameter": (
        "string",
        "Parameter of a parameterised test case ('a-b' for pytest's test_x[a-b])",
    ),
    "classname": ("string", "Test class name"),
    # A string, not a number, because that is what the directives have always
    # written and what a filter, a needtable and a schema in the field consume.
    # Turning it into a number is issue #156: it has to change here, in both
    # writers and in every consuming filter at once.
    "time": ("string", "Test execution time, in seconds"),
    "result": ("string", "Test result status"),
    "result_text": ("string", "One-line rendering of the first failure message"),
    "remote_url": ("string", "URL of the test's source in the remote repository"),
    "suites": ("integer", "Number of test suites"),
    "cases": ("integer", "Number of test cases"),
    "passed": ("integer", "Number of passed tests"),
    "skipped": ("integer", "Number of skipped tests"),
    "failed": ("integer", "Number of failed tests"),
    "errors": ("integer", "Number of test errors"),
}

#: ``role -> (JSON type, description)`` for the fields whose *name* the
#: configuration chooses; the roles are the keys of
#: :data:`~sphinxcontrib.test_reports.projectconfig.DEFAULT_FIELD_NAMES`.
#: Keying them by role rather than by name is what lets the description follow
#: a renamed field.
RENAMEABLE_FIELDS: dict[str, tuple[str, str]] = {
    "file_option": ("string", "Test file name"),
    "source_file_option": ("string", "Path of the test's source file"),
    "source_line_option": ("string", "Line of the test in its source file"),
}

#: The fixed-name fields of a test-case need, in the order they are declared.
#: The counts belong to test-file and test-suite needs, which the converter
#: does not write -- declaring them would promise fields the file never has.
CASE_FIELDS: tuple[str, ...] = (
    "suite",
    "case",
    "case_name",
    "case_parameter",
    "classname",
    "time",
    "result",
    "result_text",
    "remote_url",
)

#: Declaration of the core need fields the converter writes, as sphinx-needs
#: declares them itself (``NeedsCoreFields``). Copied rather than imported:
#: this module may not import Sphinx. The wording is informational -- what has
#: to agree between the two writers is the type, and
#: ``TestImportIntoABuild.test_the_declared_types_match_the_extension_s``
#: checks that it does.
CORE_FIELDS: dict[str, dict[str, object]] = {
    "id": {"type": "string", "description": "ID of the data."},
    "type": {"type": "string", "description": "Type of the need.", "default": ""},
    "title": {"type": "string", "description": "Title of the need."},
    "content": {
        "type": "string",
        "description": "The main content of the need.",
        "default": "",
    },
    "tags": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of tags.",
        "default": [],
    },
    "external_url": {
        "type": ["string", "null"],
        "description": "URL of the need, if it is an external need.",
        "default": None,
    },
}

#: Names a renameable field may not be given: the fixed-name fields of this
#: package and the core fields every need has. Both writers set those on the
#: same need, so a rename onto one of them makes the directives pass one
#: keyword twice -- ``add_need`` fails with "multiple values for keyword
#: argument" -- and the converter write one value over the other. ``status``,
#: ``links``, ``collapse`` and ``style`` are core fields the directives set
#: without the converter declaring them.
RESERVED_NAMES: frozenset[str] = (
    frozenset(FIELDS)
    | frozenset(CORE_FIELDS)
    | frozenset({"status", "links", "collapse", "style"})
)

#: JSON schema draft the block declares itself against, as sphinx-needs does.
SCHEMA_DIALECT = "http://json-schema.org/draft-07/schema#"


def declaration(name: str, role: str | None = None) -> tuple[str, str]:
    """The JSON type and description of one field, as ``(type, description)``.

    A renameable field is looked up by its *role*, so that its description
    survives the rename; every other field by its name. A name the table does
    not know -- an entry of the configured extra options -- is a string field
    described by its own name.

    This is the lookup the extension registers its fields with and the one
    :func:`case_needs_schema` declares them with, so the two cannot disagree.
    """
    if role is not None:
        return RENAMEABLE_FIELDS[role]
    return FIELDS.get(name, ("string", name))


def extra_field(type_: str, description: str) -> dict[str, object]:
    """Declaration of one registered field, as sphinx-needs writes it.

    Registered fields are nullable and default to null, so a need that does
    not populate one carries no value for it rather than an empty one -- which
    is what keeps a strict sphinx-needs schema strict (see
    ``tests/test_schema_validation.py``).
    """
    return {
        "type": [type_, "null"],
        "description": description,
        "field_type": "extra",
        "default": None,
    }


def link_field(description: str = "Link field") -> dict[str, object]:
    """Declaration of one link field: a list of need IDs, empty by default."""
    return {
        "type": "array",
        "items": {"type": "string"},
        "description": description,
        "field_type": "links",
        "default": [],
    }


def case_needs_schema(
    names: Mapping[str, str],
    *,
    extra_options: Iterable[str] = (),
    link_fields: Iterable[str] = (),
) -> dict[str, object]:
    """The ``needs_schema`` of a ``needs.json`` holding test-case needs.

    *names* maps the roles of :data:`RENAMEABLE_FIELDS` to the field names the
    configuration selected. *extra_options* are the XML properties exported
    under their own names, which the build registers as string options.
    *link_fields* are the fields mapped XML properties become; a mapping onto
    the name of a built-in field replaces its declaration, because the value
    written replaces the built-in value too.
    """
    properties: dict[str, object] = {
        name: dict(declaration) | {"field_type": "core"}
        for name, declaration in CORE_FIELDS.items()
    }
    for role in RENAMEABLE_FIELDS:
        properties[names[role]] = extra_field(*declaration(names[role], role))
    for name in CASE_FIELDS:
        properties[name] = extra_field(*declaration(name))
    for name in extra_options:
        # Declared a string because that is what the converter writes for an
        # exported property, whatever the name. A property named like a
        # built-in field is not exported at all (the built-in value wins, see
        # ``build_need``), so `setdefault` leaves the built-in declaration.
        properties.setdefault(name, extra_field("string", str(name)))
    for name in link_fields:
        properties[name] = link_field()
    return {
        "$schema": SCHEMA_DIALECT,
        "type": "object",
        "properties": properties,
    }
