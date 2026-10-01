"""Declarative project configuration for sphinx-test-reports.

Reads the ``[test_reports]`` section of a project's ``ubproject.toml`` -- the
declarative file shared with the other useblocks tooling (sphinx-needs,
sphinx-codelinks, sphinx-mounts, ubCode) -- so that a project is described once
instead of being restated in every tool that acts on it.

**Nothing in this module may import Sphinx.** The section describes the project,
not this extension, and the ``test-reports build needs`` command reads it as a
build action without the documentation toolchain installed.

Keys fall into two groups:

* the Sphinx-facing configuration (:data:`BRIDGE_KEYS`), spelled like the
  ``tr_*`` config values without the prefix, which the extension applies at
  ``config-inited``. The converter reads the three field-name keys among them
  (:data:`FIELD_NAME_KEYS`) and ``extra_options``, so the needs it writes have
  the shape of the needs the build creates and carry exactly the fields the
  build accepts;
* the ``[test_reports.build.needs]`` sub-table (:data:`CONVERSION_KEYS`): how test
  reports are turned into a ``needs.json``. The Sphinx bridge never applies it
  to a ``tr_*`` value, but the build validates it like every other key, so a
  typo is caught by whichever consumer reads the file first.

Any other sub-table is an unknown key like any other.

**Error policy.** A known key carrying the wrong type is fatal: that is the
typo class this validation exists to catch, and letting it through would
silently change what gets produced. An *unknown* key is only reported. The
file is shared with tools on independent release cadences, so a key this
reader does not model is routine rather than a mistake -- and aborting on it
would take down every build of the project on every older sphinx-test-reports,
including builds the key would not have changed. This is the same posture
sphinx-mounts takes for ``[[source.mounts]]``.

**Finding, loading and anchoring are ub-project's**, the shared reader every
useblocks tool uses for the file: :func:`find_project_config` is its walk,
re-exported unchanged, and the file is parsed and relative paths joined by its
``load_toml`` and ``anchor``. Everything about ``[test_reports]`` -- the keys,
their types, the normalisation, the error policy above -- is this package's.
ub-project's ``ProjectConfigError`` never leaves this module: it is re-raised
as :class:`TomlConfigError` with the same message, the one exception both
consumers handle.
"""

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import NoReturn

from ub_project import DEFAULT_FILENAME, ProjectConfigError, anchor, load_toml

# Re-exported: the Sphinx bridge, the converter and the tests import the walk
# from here. It raises nothing of its own, so it needs no wrapper.
from ub_project import find_project_config as find_project_config
from ub_test_reports.fields import RESERVED_NAMES

#: Default file the configuration is read from. Looked up by walking up from
#: the ``confdir`` (Sphinx) or the working directory (a converter); see
#: :func:`find_project_config`. ``ubproject.toml`` is the convention shared
#: with other useblocks tooling so a single declarative file describes the
#: project to every downstream consumer -- Sphinx, ubCode, a converter --
#: without any of them having to execute Python. ub-project's
#: ``DEFAULT_FILENAME``, under the name this package has always exported.
DEFAULT_TOML_FILENAME = DEFAULT_FILENAME

#: The section this extension owns inside the shared file. Spelled
#: ``snake_case`` like every other section of ``ubproject.schema.json``
#: (``build_tags``, ``format_rst``, ``needs_json``, ``rst_lint``, ...); note
#: that ``[reports]`` is already taken, and means report *templates*.
SECTION = "test_reports"

#: Section keys bridged onto their ``tr_*`` Sphinx config values.
BRIDGE_KEYS = (
    "file",
    "suite",
    "case",
    "file_option",
    "source_file_option",
    "source_line_option",
    "rootdir",
    "report_template",
    "suite_id_length",
    "case_id_length",
    "import_encoding",
    "extra_options",
    "property_link_types",
    "json_mapping",
    "deterministic_case_ids",
)

#: Keys holding a path. Relative values are anchored against the directory
#: containing the TOML file, not against ``confdir`` or the process working
#: directory: the file is self-describing, and moving it as a unit keeps its
#: relative paths meaningful. It also makes every consumer resolve a
#: relative path identically.
PATH_KEYS = ("rootdir", "report_template")

#: The keys whose need-type setting accepts both the positional ``conf.py``
#: list and a named table; :func:`_normalise_type_entry` reduces both to the
#: list form. ``None`` in :data:`_KEY_TYPES` marks exactly these.
_DUAL_SPELLING_KEYS = ("file", "suite", "case")

#: The sub-table holding what the ``test-reports build`` command line
#: produces, one table per artifact and named after it, as ubCode spells
#: ``ubc build needs``. Not a bridge key: the build never maps any of it onto
#: a ``tr_*`` value. It is validated like everything else, so that the build
#: rejects the same typos the command line would -- one file, one verdict.
BUILD_TABLE = "build"

#: The artifact ``test-reports build needs`` produces, and its table under
#: :data:`BUILD_TABLE`.
NEEDS_TABLE = "needs"

#: How the table is spelled in diagnostics.
NEEDS_TABLE_PATH = f"{SECTION}.{BUILD_TABLE}.{NEEDS_TABLE}"

#: Keys of ``[test_reports.build.needs]``, in the order the command documents
#: them. The CLI's flag merge iterates this, so a key cannot be added here
#: without the CLI being taught a default for it.
CONVERSION_KEYS = (
    "project",
    "version",
    "need_type",
    "tags",
    "link_properties",
    "remote_url",
    "commit",
    "url_pattern",
)

#: The three renameable need fields and their default names -- the field
#: carrying the XML *report* path, and the two carrying the test's *source*
#: location. The build registers these names (``tr_file_option``,
#: ``tr_source_file_option``, ``tr_source_line_option``) and the converter
#: writes them, so an imported need and a locally created one have the same
#: shape. Both sides take the defaults from here.
FIELD_NAME_KEYS = ("file_option", "source_file_option", "source_line_option")
DEFAULT_FIELD_NAMES: dict[str, str] = {
    "file_option": "file",
    "source_file_option": "case_file",
    "source_line_option": "case_line",
}

#: Need type of a test case when neither consumer is told otherwise: the
#: converter's ``need_type`` default and the ``type`` of the build's default
#: ``case`` entry. Both defaults live here so they cannot drift apart.
DEFAULT_NEED_TYPE = "testcase"

#: Expected Python type per ``[test_reports.build.needs]`` key.
_NEEDS_KEY_TYPES: dict[str, type[object]] = {
    "project": str,
    "version": str,
    "need_type": str,
    "tags": list,
    "link_properties": dict,
    "remote_url": str,
    "commit": str,
    "url_pattern": str,
}

#: Expected Python type per key. ``bool`` must be checked *before* ``int``
#: (bool is an int subclass). ``None`` marks the dual-spelling keys, which are
#: normalised separately; path keys are validated as ``str`` and anchored
#: afterwards.
_KEY_TYPES: dict[str, type[object] | None] = {
    "file": None,
    "suite": None,
    "case": None,
    "file_option": str,
    "source_file_option": str,
    "source_line_option": str,
    "rootdir": str,
    "report_template": str,
    "suite_id_length": int,
    "case_id_length": int,
    "import_encoding": str,
    "extra_options": list,
    "property_link_types": dict,
    "json_mapping": dict,
    "deterministic_case_ids": bool,
    "build": dict,
}

#: Required type of the *values* inside a table-valued key. Without this a
#: table passes validation on its outer shape alone, and a mistake such as
#: ``property_link_types = { request = ["req"] }`` reaches the directives,
#: which fail with a bare ``TypeError`` on an unhashable field name.
#: ``None`` means the nested shape is free-form -- ``json_mapping`` mirrors an
#: arbitrary parser mapping -- so only the outer table is checked.
_DICT_VALUE_TYPES: dict[str, type[object] | None] = {
    "property_link_types": str,
    "json_mapping": None,
    "link_properties": str,
}

#: Field order of the positional ``tr_file``-style lists, and the table keys
#: that spell the same thing readably.
_TYPE_ENTRY_FIELDS = ("directive", "type", "name", "prefix", "color", "style")

#: Index of ``type`` within :data:`_TYPE_ENTRY_FIELDS`, i.e. of the need type
#: inside a normalised entry.
_TYPE_FIELD_INDEX = _TYPE_ENTRY_FIELDS.index("type")


class TomlConfigError(Exception):
    """Raised when the declarative config cannot be parsed or is malformed.

    Deliberately *not* a ``SphinxError``: this module must stay importable
    without Sphinx. The Sphinx-side bridge re-raises it as an
    ``InvalidConfigurationError`` to abort the build; a non-Sphinx consumer
    reports it and exits non-zero.
    """


def load_project_config(
    path: Path, warn: Callable[[str], None] | None = None
) -> dict[str, object] | None:
    """Read and normalise the ``[test_reports]`` section of a TOML file.

    :param path: Absolute path to the TOML file (``ubproject.toml`` or whatever
        the caller resolved).
    :param warn: Called with a message for every non-fatal problem -- today,
        an unknown key. Callers pass their own logger so this module stays
        Sphinx-free; ``None`` discards the reports.
    :return: The normalised section as a plain dict; ``None`` when the file
        does not exist (an absence is not an error -- callers decide whether
        that is fine, e.g. neither consumer minds a missing *default* file but
        both complain about an explicitly given one). An existing file without
        the section yields ``{}``.
    :raises TomlConfigError: If the file cannot be read, is not valid TOML, the
        section has the wrong shape, or a known key has the wrong type.
    """
    if not path.is_file():
        return None
    try:
        # ``is_file()`` succeeding does not mean the read will: the file may be
        # unreadable, not UTF-8, or replaced between the check and the open.
        data = load_toml(path)
    except ProjectConfigError as error:
        # Both consumers handle TomlConfigError and nothing else, and
        # ub-project's exception is not part of this package's surface.
        raise TomlConfigError(str(error)) from error

    section = data.get(SECTION)
    if section is None:
        return {}
    if not isinstance(section, dict):
        msg = f"{path}: [{SECTION}] must be a table, got {type(section).__name__}"
        raise TomlConfigError(msg)

    return _normalise_section(section, path, warn)


def _normalise_section(
    section: Mapping[str, object], path: Path, warn: Callable[[str], None] | None
) -> dict[str, object]:
    """Validate every key and return a normalised copy of *section*.

    Normalisation: relative paths become absolute (anchored at the TOML file's
    directory), the ``file``/``suite``/``case`` need-type settings accept both
    the positional-list spelling of ``conf.py`` and a named table.

    Unknown keys are reported through *warn* and dropped -- see the module
    docstring for why they are not fatal.
    """
    unknown = sorted(set(section) - set(_KEY_TYPES))
    if unknown and warn is not None:
        warn(
            f"{path}: ignoring unknown key(s) in [{SECTION}]: "
            f"{', '.join(unknown)}. Supported keys: "
            f"{', '.join(sorted(_KEY_TYPES))}"
        )

    normalised: dict[str, object] = {}
    for key, value in section.items():
        if key in unknown:
            continue
        expected = _KEY_TYPES[key]
        # bool first: bool is an int subclass, and for int keys a TOML
        # ``true`` must be rejected, not silently accepted.
        if expected is int and isinstance(value, bool):
            _wrong_type(key, value, expected, path)
        if expected is not None and not isinstance(value, expected):
            _wrong_type(key, value, expected, path)
        if key == BUILD_TABLE:
            normalised[key] = _normalise_build_table(value, path, warn)
        elif key in _DUAL_SPELLING_KEYS:
            normalised[key] = _normalise_type_entry(key, value, path)
        else:
            if expected is list:
                _check_list_items(key, value, path)
            elif expected is dict:
                _check_table_values(key, value, path)
            normalised[key] = value

    _check_need_type_agreement(normalised, path)
    _check_field_name_collisions(normalised, path)
    return _anchor_paths(normalised, path.parent)


def field_names(section: Mapping[str, object]) -> dict[str, str]:
    """The report-path and source-location field names the section selects.

    Keys are :data:`FIELD_NAME_KEYS`; a key the section does not set falls
    back to :data:`DEFAULT_FIELD_NAMES`, which is also the build's default.
    """
    names = dict(DEFAULT_FIELD_NAMES)
    for key in FIELD_NAME_KEYS:
        value = section.get(key)
        if isinstance(value, str) and value:
            names[key] = value
    return names


def _check_field_name_collisions(section: Mapping[str, object], path: Path) -> None:
    """The report-path and source-location fields must have names of their own.

    Two options naming one field, or one of them naming a fixed field such as
    ``case`` or ``result``, would make ``add_need`` receive the same keyword
    twice (a bare ``TypeError`` inside a directive) and the converter write one
    value over the other. The build checks its ``conf.py`` values the same way;
    this covers the declarative spelling for both consumers.
    """
    names = field_names(section)
    seen: dict[str, str] = {}
    for key, name in names.items():
        if name in RESERVED_NAMES:
            msg = (
                f"{path}: [{SECTION}] {key} = {name!r}: {name!r} is a field every "
                f"test-case need has already; the report path and the source "
                f"location must live in fields of their own"
            )
            raise TomlConfigError(msg)
        if name in seen:
            msg = (
                f"{path}: [{SECTION}] {seen[name]} and {key} both name the need "
                f"field {name!r}; the report path and the source location must "
                f"live in different fields"
            )
            raise TomlConfigError(msg)
        seen[name] = key


def _normalise_build_table(
    value: object, path: Path, warn: Callable[[str], None] | None
) -> dict[str, object]:
    """Validate ``[test_reports.build]``: one known sub-table per artifact.

    Only ``needs`` is modelled today. An unknown sub-table is reported and
    dropped like an unknown key anywhere else -- the command line may grow
    artifacts this version does not know, and a file naming one must not take
    a build down.
    """
    if not isinstance(value, Mapping):
        return {}
    table: dict[str, object] = {str(name): item for name, item in value.items()}
    unknown = sorted(set(table) - {NEEDS_TABLE})
    if unknown and warn is not None:
        warn(
            f"{path}: ignoring unknown key(s) in [{SECTION}.{BUILD_TABLE}]: "
            f"{', '.join(unknown)}. Supported keys: {NEEDS_TABLE}"
        )
    normalised: dict[str, object] = {}
    if NEEDS_TABLE in table:
        artifact = table[NEEDS_TABLE]
        if not isinstance(artifact, dict):
            _wrong_type(f"{BUILD_TABLE}.{NEEDS_TABLE}", artifact, dict, path)
        normalised[NEEDS_TABLE] = _normalise_needs_table(artifact, path, warn)
    return normalised


def _normalise_needs_table(
    value: object, path: Path, warn: Callable[[str], None] | None
) -> dict[str, object]:
    """Validate ``[test_reports.build.needs]`` under the section's own policy.

    Same rules as the section: a known key with the wrong type is fatal, an
    unknown key is reported and dropped, table values are checked. The caller
    has already established that *value* is a table.
    """
    if not isinstance(value, Mapping):
        return {}
    table: dict[str, object] = {str(name): item for name, item in value.items()}
    unknown = sorted(set(table) - set(_NEEDS_KEY_TYPES))
    if unknown and warn is not None:
        warn(
            f"{path}: ignoring unknown key(s) in [{NEEDS_TABLE_PATH}]: "
            f"{', '.join(unknown)}. Supported keys: "
            f"{', '.join(CONVERSION_KEYS)}"
        )
    normalised: dict[str, object] = {}
    for key, item in table.items():
        if key in unknown:
            continue
        label = f"{BUILD_TABLE}.{NEEDS_TABLE}.{key}"
        expected = _NEEDS_KEY_TYPES[key]
        if not isinstance(item, expected):
            _wrong_type(label, item, expected, path)
        if expected is list:
            _check_list_items(label, item, path)
        elif expected is dict:
            _check_table_values(key, item, path, label)
            if key == "link_properties":
                _check_link_properties(item, path)
        normalised[key] = item
    return normalised


def _check_link_properties(value: object, path: Path) -> None:
    """Every ``PROPERTY = "LINK_FIELD"`` pair must have two non-empty names.

    Checked here rather than only in the converter, so the build and the
    converter give one verdict on the file: a silently dropped pair would send
    a link field into ``needs.json`` as a plain field instead.
    """
    if not isinstance(value, Mapping):
        return
    for name, field in value.items():
        if not str(name).strip() or not (isinstance(field, str) and field.strip()):
            msg = (
                f"{path}: [{NEEDS_TABLE_PATH}] link_properties expects "
                f'PROPERTY = "LINK_FIELD" with both names non-empty, got '
                f"{name!r} = {field!r}"
            )
            raise TomlConfigError(msg)


def needs_settings(section: Mapping[str, object]) -> Mapping[str, object] | None:
    """The ``[test_reports.build.needs]`` table, or ``None`` when unset.

    The one place that knows how the table is nested, so a consumer never
    spells the path itself.
    """
    build = section.get(BUILD_TABLE)
    if not isinstance(build, Mapping):
        return None
    needs = build.get(NEEDS_TABLE)
    return needs if isinstance(needs, Mapping) else None


def _check_need_type_agreement(section: Mapping[str, object], path: Path) -> None:
    """``build.needs.need_type`` and ``case``'s type name the same need type.

    They are separate keys with separate consumers -- the converter derives the
    need type and the deterministic-ID prefix from ``need_type``, the Sphinx
    build from ``case``'s ``type`` -- and both default to
    :data:`DEFAULT_NEED_TYPE`. Letting them disagree produces exactly the
    divergence this file exists to prevent: a ``needs.json`` full of needs the
    build neither registers nor cross-links.

    A side that is not set is compared at its default, not skipped: a
    customised ``case`` next to a ``build.needs`` table without ``need_type``
    is a disagreement too. The check only applies when that table exists -- a
    project that only builds documentation may name its case type freely.
    """
    needs = needs_settings(section)
    if needs is None:
        return
    need_type: object = needs.get("need_type", DEFAULT_NEED_TYPE)
    case_type = case_need_type(section) or DEFAULT_NEED_TYPE
    if case_type != need_type:
        msg = (
            f"{path}: [{NEEDS_TABLE_PATH}] need_type is {need_type!r} but "
            f"[{SECTION}] case's type is {case_type!r} (each defaulting to "
            f"{DEFAULT_NEED_TYPE!r} when not set). Both name the need type of a "
            f"test case -- need_type for `build needs`, case for the Sphinx "
            f"build -- so they must agree, or the produced needs.json and the "
            f"build describe different need types."
        )
        raise TomlConfigError(msg)


def _check_list_items(key: str, value: object, path: Path) -> None:
    """Every element of an array-valued key must be a string."""
    if not isinstance(value, Sequence):
        return
    for item in value:
        if not isinstance(item, str):
            _wrong_type(key, value, list, path)


def _check_table_values(
    key: str, value: object, path: Path, label: str | None = None
) -> None:
    """Every value of a table-valued key must have the declared type.

    Skipped for keys whose nested shape is free-form (:data:`_DICT_VALUE_TYPES`
    maps them to ``None``). *label* is how the key is spelled in messages when
    it sits in a sub-table.
    """
    expected = _DICT_VALUE_TYPES.get(key)
    if expected is None or not isinstance(value, Mapping):
        return
    for name, item in value.items():
        if not isinstance(item, expected):
            msg = (
                f"{path}: [{SECTION}] {label or key}.{name} must be "
                f"{_type_label(expected)}, got {type(item).__name__}: {item!r}"
            )
            raise TomlConfigError(msg)


def case_need_type(section: Mapping[str, object]) -> str | None:
    """The need type the build gives test cases, if the section sets ``case``.

    Shared by the loader's own agreement check and by the converter, which has
    to re-check after merging command-line flags: a ``--need-type`` given on
    the command line is not in the file and so escapes the loader.
    """
    case = section.get("case")
    if not isinstance(case, Sequence):
        return None
    value: object = case[_TYPE_FIELD_INDEX]
    return value if isinstance(value, str) else None


def _wrong_type(
    key: str, value: object, expected: type[object] | None, path: Path
) -> NoReturn:
    msg = (
        f"{path}: [{SECTION}] {key} must be "
        f"{_type_label(expected)}, got {type(value).__name__}: {value!r}"
    )
    raise TomlConfigError(msg)


def _type_label(expected: type[object] | None) -> str:
    if expected is None:
        return "a 6-element array or a table"
    if expected is int:
        return "an integer"
    if expected is bool:
        return "a boolean"
    if expected is str:
        return "a string"
    if expected is list:
        return "an array of strings"
    if expected is dict:
        return "a table"
    return expected.__name__


def _normalise_type_entry(key: str, value: object, path: Path) -> list[str]:
    """The ``file``/``suite``/``case`` settings in one of two spellings.

    Positional (exactly what ``conf.py`` accepts)::

        file = ["test-file", "testfile", "Test-File", "TF_", "#ffffff", "node"]

    Named -- the recommended TOML spelling, since six bare strings in a row
    cannot be told apart::

        [test_reports.file]
        directive = "test-file"
        type = "testfile"
        name = "Test-File"
        prefix = "TF_"
        color = "#ffffff"
        style = "node"
    """
    if isinstance(value, list):
        entry = [item for item in value if isinstance(item, str)]
        if len(entry) != len(_TYPE_ENTRY_FIELDS) or len(entry) != len(value):
            msg = (
                f"{path}: [{SECTION}] {key} as an array must hold exactly "
                f"{len(_TYPE_ENTRY_FIELDS)} strings "
                f"({'/'.join(_TYPE_ENTRY_FIELDS)}), got {value!r}"
            )
            raise TomlConfigError(msg)
        return entry

    if isinstance(value, Mapping):
        table: dict[str, object] = {str(name): item for name, item in value.items()}
        missing = [field for field in _TYPE_ENTRY_FIELDS if field not in table]
        unknown = sorted(set(table) - set(_TYPE_ENTRY_FIELDS))
        wrong = sorted(
            field
            for field in _TYPE_ENTRY_FIELDS
            if field in table and not isinstance(table[field], str)
        )
        problems = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        if wrong:
            problems.append(f"non-string {', '.join(wrong)}")
        if problems:
            msg = (
                f"{path}: [{SECTION}] [{SECTION}.{key}]: "
                f"{'; '.join(problems)}. Expected the keys "
                f"{'/'.join(_TYPE_ENTRY_FIELDS)}."
            )
            raise TomlConfigError(msg)
        return [str(table[field]) for field in _TYPE_ENTRY_FIELDS]

    msg = (
        f"{path}: [{SECTION}] {key} must be a 6-element array or a table, "
        f"got {type(value).__name__}"
    )
    raise TomlConfigError(msg)


def _anchor_paths(section: dict[str, object], base: Path) -> dict[str, object]:
    """Anchor :data:`PATH_KEYS` at *base* (the TOML file's directory).

    Through ub-project's ``anchor``, which joins and deliberately never calls
    ``resolve()``: *base* is already absolute, and this module does not
    touch the filesystem to second-guess the form of the path it was handed.
    Whether symlinks in it are collapsed is the consumer's decision -- Sphinx
    resolves its ``confdir`` before the bridge ever runs, a converter may pass
    its working directory as is -- and the loader must not make that decision
    behind their back. An absolute value is left as the string it was, not
    round-tripped through ``Path``.
    """
    for key in PATH_KEYS:
        value = section.get(key)
        if isinstance(value, str) and not Path(value).is_absolute():
            section[key] = str(anchor(value, base))
    return section
