"""Configuration in ``conf.py`` (contract §2.5, Sphinx only).

Four confvals mirror the ``ubproject.toml`` tables. A key the file's ``[parse]`` table sets
replaces the confval whole, unless the confval was given with ``-D``; a ``conf.py`` value
must be one TOML could have written, and is then handled exactly as that TOML would be.
"""

from __future__ import annotations

import datetime
import functools
import math
import re
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.errors import ConfigError
from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings
from sphinx_ub_directives import _config

from .corpus import CONF_PY

ROW = ".. req:: Owned by {{ options.owner }}\n   :id: {{ argument }}\n"


def _project(
    root: Path,
    *,
    conf: str = "",
    toml: str | None = None,
    page: str = "",
    files: dict[str, str] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "conf.py").write_text(CONF_PY + conf, encoding="utf-8", newline="")
    if toml is not None:
        (root / "ubproject.toml").write_text(toml, encoding="utf-8", newline="")
    (root / "index.rst").write_text(
        "Case\n====\n\n" + page, encoding="utf-8", newline=""
    )
    for relative, text in (files or {}).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")
    return root


def _build(
    make_app: Callable[..., SphinxTestApp], root: Path, **kwargs: Any
) -> SphinxTestApp:
    app = make_app("html", srcdir=root, freshenv=True, **kwargs)
    app.build()
    return app


def _html(app: SphinxTestApp) -> str:
    return (Path(app.outdir) / "index.html").read_text(encoding="utf-8")


# --- each confval alone renders as the same TOML ----------------------------------------


def test_a_preset_in_conf_py_alone(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """C1/K8: ``ub_directive_presets`` alone, with no ubproject.toml, is a preset."""
    root = _project(
        tmp_path,
        conf="ub_directive_presets = {'callout': {'base': 'note', 'append_options': {'class': 'cp'}}}\n",
        page=".. callout::\n\n   Body.\n",
    )
    assert '<div class="cp admonition note">' in _html(_build(make_app, root))


def test_a_declared_template_and_context_in_conf_py_alone(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """C1/K8: ``ub_directive_templates`` and ``ub_template_contexts`` alone render as the
    same TOML tables would."""
    conf = (
        "ub_template_contexts = {'team': {'lead': 'Ada'}}\n"
        "ub_directive_templates = {'lead': {'body': 'Lead: {{ contexts.team.lead }}.'}}\n"
    )
    root = _project(tmp_path, conf=conf, page=".. lead::\n")
    assert "Lead: Ada." in _html(_build(make_app, root))


def test_ub_template_enabled_in_conf_py_alone(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """C1/K8: ``ub_template_enabled = True`` alone switches ``ub-template`` on."""
    root = _project(
        tmp_path,
        conf="ub_template_enabled = True\n",
        page=".. ub-template::\n\n   Two is {{ 1 + 1 }}.\n",
    )
    app = _build(make_app, root)
    assert "Two is 2." in _html(app)
    assert not [w for w in build_warnings(app) if "template_switched_off" in w]


# --- precedence (C2) -----------------------------------------------------------------


def test_a_toml_key_wins_whole_over_conf_py(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """C2/K1/K2: a key the file's [parse] sets replaces the conf.py value WHOLE: the TOML's
    preset is used, and conf.py's other entry is not merged in."""
    conf = (
        "ub_directive_presets = {'callout': {'base': 'note', 'append_options': {'class': 'from-conf'}},"
        " 'other': {'base': 'tip'}}\n"
    )
    toml = '[parse.directive_presets.callout]\nbase = "note"\nappend_options = { class = "from-toml" }\n'
    root = _project(
        tmp_path,
        conf=conf,
        toml=toml,
        page=".. callout::\n\n   Body.\n\n.. other::\n\n   Other.\n",
    )
    app = _build(make_app, root)
    html = _html(app)
    assert '<div class="from-toml admonition note">' in html
    assert "from-conf" not in html
    assert [w for w in build_warnings(app) if 'Unknown directive type "other"' in w], (
        build_warnings(app)
    )


def test_a_key_the_toml_does_not_set_stays_with_conf_py(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """C2/K4: a mixed project -- presets in the TOML, contexts in conf.py: the key the
    file does not set is conf.py's, even though the file exists and has other keys."""
    conf = (
        "ub_template_contexts = {'team': {'lead': 'Ada'}}\n"
        "ub_directive_templates = {'lead': {'body': 'Lead: {{ contexts.team.lead }}.'}}\n"
    )
    toml = '[parse.directive_presets.callout]\nbase = "note"\n'
    root = _project(
        tmp_path, conf=conf, toml=toml, page=".. lead::\n\n.. callout::\n\n   Body.\n"
    )
    html = _html(_build(make_app, root))
    assert "Lead: Ada." in html
    assert 'class="admonition note"' in html


def test_an_empty_toml_table_still_wins(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """C2: a key PRESENT in [parse], even as an empty table, replaces the conf.py value."""
    conf = "ub_directive_presets = {'callout': {'base': 'note'}}\n"
    root = _project(
        tmp_path,
        conf=conf,
        toml="[parse.directive_presets]\n",
        page=".. callout::\n\n   Body.\n",
    )
    app = _build(make_app, root)
    assert [
        w for w in build_warnings(app) if 'Unknown directive type "callout"' in w
    ], build_warnings(app)


def test_a_dash_d_override_beats_the_toml(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """C2/K3: a confval given with -D keeps its value: the TOML's true does not win."""
    root = _project(
        tmp_path,
        toml="[parse]\nub_template_enabled = true\n",
        page=".. ub-template::\n\n   Rendered.\n",
    )
    app = _build(make_app, root, confoverrides={"ub_template_enabled": "0"})
    assert [
        w for w in build_warnings(app) if "ub_directives.template_switched_off" in w
    ], build_warnings(app)
    assert "Rendered." not in _html(app)


# --- the value rule (C3) -------------------------------------------------------------


def test_a_tuple_is_a_list(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """C3/K5: a tuple is the TOML array it could have been."""
    conf = (
        "ub_template_contexts = {'team': {'members': ('Bob', 'Cy')}}\n"
        "ub_directive_templates = {'m': {'body': '{{ contexts.team.members }}'}}\n"
    )
    root = _project(tmp_path, conf=conf, page=".. m::\n")
    app = _build(make_app, root)
    members = app.config.ub_directives_resolved["template_contexts"]["team"]["members"]
    assert members == ["Bob", "Cy"] and type(members) is list
    assert "Bob" in _html(app)


@pytest.mark.parametrize(
    ("confval", "value", "expected"),
    [
        (
            "ub_template_contexts",
            "{'site': {'data': {'owner': None}}}",
            "ub_template_contexts['site']['data']['owner']: None is not a value",
        ),
        (
            "ub_template_contexts",
            "{'site': {'tags': {1, 2}}}",
            "ub_template_contexts['site']['tags']",
        ),
        (
            "ub_template_contexts",
            "{'site': {'raw': b'x'}}",
            "ub_template_contexts['site']['raw']",
        ),
        (
            "ub_template_contexts",
            "{'site': {'where': __import__('pathlib').Path('x')}}",
            "ub_template_contexts['site']['where']",
        ),
        ("ub_template_contexts", "{'site': {'fn': len}}", "data only"),
        (
            "ub_template_contexts",
            "{'site': {'obj': object()}}",
            "Migrating from sphinx-jinja2",
        ),
        (
            "ub_template_contexts",
            "{'site': {'big': 2**63}}",
            "ub_template_contexts['site']['big']: 9223372036854775808 is outside the signed 64-bit range",
        ),
        ("ub_template_contexts", "{'site': {1: 'x'}}", "the key 1 is not a string"),
        (
            "ub_directive_presets",
            "['not', 'a', 'dict']",
            "ub_directive_presets: ['not', 'a', 'dict'] must be a dict",
        ),
        (
            "ub_template_enabled",
            "'yes'",
            "ub_template_enabled: 'yes' must be True or False",
        ),
    ],
)
def test_a_value_toml_could_not_have_written_is_refused(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    confval: str,
    value: str,
    expected: str,
) -> None:
    """C3/K5: anything TOML could not have written is a ConfigError naming the confval and
    the key path; a callable or an object says contexts are data only."""
    root = _project(tmp_path, conf=f"{confval} = {value}\n")
    with pytest.raises(ConfigError, match=None) as raised:
        make_app("html", srcdir=root, freshenv=True)
    assert expected in str(raised.value), str(raised.value)


def test_the_i64_bounds_themselves_are_accepted() -> None:
    """C3/K5: the bound is the signed 64-bit range, both ends included."""
    value = {"site": {"hi": 2**63 - 1, "lo": -(2**63)}}
    assert _config._toml_value(value, "ub_template_contexts") == value


@pytest.mark.parametrize(
    ("toml_value", "python_value"),
    [
        ("inf", "float('inf')"),
        ("nan", "float('nan')"),
        ("2024-01-02", "__import__('datetime').date(2024, 1, 2)"),
    ],
)
@pytest.mark.parametrize("form", ["toml", "conf.py"])
def test_a_conf_py_context_is_checked_as_the_toml_one(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    form: str,
    toml_value: str,
    python_value: str,
) -> None:
    """C3: after conversion a conf.py value is handled EXACTLY as the same TOML: a
    non-finite float or a date in a context is the same finding either way."""
    body = "{{ contexts.c.v }}"
    if form == "toml":
        root = _project(
            tmp_path,
            toml=f'[parse.template_contexts.c]\nv = {toml_value}\n\n[parse.directive_templates.u]\nbody = "{body}"\n',
            page=".. u::\n",
        )
    else:
        root = _project(
            tmp_path,
            conf=f"ub_template_contexts = {{'c': {{'v': {python_value}}}}}\nub_directive_templates = {{'u': {{'body': '{body}'}}}}\n",
            page=".. u::\n",
        )
    found = [
        w
        for w in build_warnings(_build(make_app, root))
        if "ub_directives.template_context_invalid" in w
    ]
    assert len(found) == 1, build_warnings(_build(make_app, root))


def test_python_datetime_and_math_are_what_toml_reads() -> None:
    """C3: the Python types the conversion accepts are the ones tomllib produces."""
    import tomllib

    data = tomllib.loads(
        "d = 2024-01-02\nt = 10:00:00\ndt = 2024-01-02T10:00:00\nf = inf\n"
    )
    assert isinstance(data["d"], datetime.date) and isinstance(data["t"], datetime.time)
    assert math.isinf(data["f"])
    assert _config._toml_value(data, "x") == data


# --- a subclass is its exact base type (F1-F3) -----------------------------------------

#: Subclasses a conf.py can hold where TOML has only the base types.
_SUBCLASSES = """\
import enum
from markupsafe import Markup
class IE(enum.IntEnum):
    A = 7
class ME(int, enum.Enum):
    A = 7
class SE(str, enum.Enum):
    A = "a"
class F(float):
    def __repr__(self):
        return "F(%s)" % float.__repr__(self)
"""

_ON = "[parse]\nub_template_enabled = true\n\n"


@pytest.mark.parametrize(
    ("conf", "toml", "page"),
    [
        pytest.param(
            "ub_directive_presets = {'numbered': {'base': 'code-block', 'options': {'lineno-start': IE.A}}}\n",
            '[parse.directive_presets.numbered]\nbase = "code-block"\noptions = { lineno-start = 7 }\n',
            ".. numbered:: python\n\n   a = 1\n",
            id="intenum-preset-option",
        ),
        pytest.param(
            "ub_directive_presets = {'numbered': {'base': 'code-block', 'options': {'lineno-start': ME.A}}}\n",
            '[parse.directive_presets.numbered]\nbase = "code-block"\noptions = { lineno-start = 7 }\n',
            ".. numbered:: python\n\n   a = 1\n",
            id="int-enum-mixin-preset-option",
        ),
        pytest.param(
            "ub_template_enabled = True\nub_template_contexts = {'c': {'nums': [IE.A, 3]}}\n",
            _ON + "[parse.template_contexts.c]\nnums = [7, 3]\n",
            ".. ub-template:: c\n\n   C {{ nums }}\n",
            id="intenum-context-array",
        ),
        pytest.param(
            "ub_template_enabled = True\nub_template_contexts = {'c': {'nums': [ME.A, 3]}}\n",
            _ON + "[parse.template_contexts.c]\nnums = [7, 3]\n",
            ".. ub-template:: c\n\n   C {{ nums }}\n",
            id="int-enum-mixin-context-array",
        ),
        pytest.param(
            "ub_directive_presets = {'scaled': {'base': 'image', 'options': {'width': F(1.5)}}}\n",
            '[parse.directive_presets.scaled]\nbase = "image"\noptions = { width = 1.5 }\n',
            ".. scaled:: x.png\n",
            id="float-subclass-preset-option",
        ),
        pytest.param(
            "ub_template_enabled = True\nub_template_contexts = {'c': {'tags': [Markup('a'), 'b']}}\n",
            _ON + '[parse.template_contexts.c]\ntags = ["a", "b"]\n',
            ".. ub-template:: c\n\n   C {{ tags }}\n",
            id="markup-in-a-mixed-array",
        ),
        pytest.param(
            "ub_template_enabled = True\nub_template_contexts = {'c': {'solo': [Markup('x')]}}\n",
            _ON + '[parse.template_contexts.c]\nsolo = ["x"]\n',
            ".. ub-template:: c\n\n   C {{ solo }}\n",
            id="markup-alone-in-an-array",
        ),
        pytest.param(
            "ub_template_enabled = True\nub_template_contexts = {'c': {'s': SE.A, 'l': [SE.A, 'b']}}\n",
            _ON + '[parse.template_contexts.c]\ns = "a"\nl = ["a", "b"]\n',
            ".. ub-template:: c\n\n   C {{ s }} {{ l }}\n",
            id="str-enum-is-its-value",
        ),
    ],
)
def test_a_conf_py_subclass_renders_as_its_toml_twin(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    conf: str,
    toml: str,
    page: str,
) -> None:
    """F1-F3 (C3 parity): TOML has only the base types, so an ``IntEnum``, an ``int``
    mixin, a ``str`` Enum, a ``Markup`` or a float with its own ``repr`` is read as its
    exact base value -- the page renders, and warns, exactly as its TOML twin. (Before:
    an int subclass hung the build, the float crashed it, the array was refused.)"""
    if "IE." in conf or "ME." in conf:
        # an int subclass hangs an in-process build if the bound ever scans again: fail
        # by the probe's timeout instead of hanging the suite
        _bound_probe()

    def built(root: Path) -> tuple[str, list[str]]:
        app = _build(make_app, root)
        html = _html(app)
        found = re.findall(r"\[(\w+\.\w+)\]$", "\n".join(build_warnings(app)), re.M)
        # the next build's directives must not meet this one's
        app.cleanup()
        return html[
            html.index('<section id="case">') : html.index("</section>")
        ], sorted(found)

    ours = built(_project(tmp_path / "conf", conf=_SUBCLASSES + conf, page=page))
    twin = built(_project(tmp_path / "toml", toml=toml, page=page))
    assert ours == twin


def test_a_subclass_value_comes_back_as_its_exact_base_type() -> None:
    """F1-F3: the conversion's result holds base types only, read through the base type's
    own method -- an Enum's ``__str__``, ``__float__`` or ``repr`` cannot change it; a
    dict or list subclass is a plain dict or list; a date subclass keeps its tzinfo."""
    import collections
    import enum

    from markupsafe import Markup

    class IE(enum.IntEnum):
        A = 7

    # the mixin itself, not StrEnum: its __str__ is overridden to prove it is not used
    class SE(str, enum.Enum):  # noqa: UP042
        A = "a"

        def __str__(self) -> str:
            return "not the value"

    class F(float):
        def __float__(self) -> float:
            return 99.0

    class D(datetime.datetime):
        pass

    class L(list):
        pass

    zone = datetime.timezone(datetime.timedelta(hours=2))
    value = collections.OrderedDict(
        i=IE.A, s=SE.A, m=Markup("<b>"), f=F(1.5), l=L([IE.A]),
        d=D(2024, 1, 2, 10, 0, tzinfo=zone),
    )  # fmt: skip
    out = _config._toml_value(value, "x")
    assert out == {"i": 7, "s": "a", "m": "<b>", "f": 1.5, "l": [7],
                   "d": datetime.datetime(2024, 1, 2, 10, 0, tzinfo=zone)}  # fmt: skip
    assert type(out) is dict and type(out["l"]) is list
    assert [type(out[k]) for k in "ismfd"] == [int, str, str, float, datetime.datetime]
    assert out["d"].tzinfo is zone


#: The bound probe, run in a subprocess so a regression to a scan fails by timeout.
_BOUND_PROBE = textwrap.dedent(
    """\
    import enum, time
    from sphinx.errors import ConfigError
    from sphinx_ub_directives import _config
    class Big(enum.IntEnum):
        PAST = 2**63
        LAST = 2**63 - 1
    start = time.perf_counter()
    try:
        _config._toml_value({"c": {"n": Big.PAST}}, "ub_template_contexts")
        refused = ""
    except ConfigError as error:
        refused = str(error)
    kept = _config._toml_value({"c": {"n": [Big.LAST]}}, "ub_template_contexts")
    print(time.perf_counter() - start)
    print(refused)
    print(type(kept["c"]["n"][0]).__name__, kept["c"]["n"][0])
    """
)


@functools.cache
def _bound_probe() -> tuple[str, ...]:
    """The probe's three lines; a ``subprocess.TimeoutExpired`` when the bound scans."""
    run = subprocess.run(
        [sys.executable, "-c", _BOUND_PROBE],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return tuple(run.stdout.splitlines())


def test_an_int_subclass_past_the_bound_is_refused_promptly() -> None:
    """F1: the i64 bound is checked by comparison, so an ``IntEnum`` -- in range or just
    past it -- returns at once (``in range(...)`` scans an int subclass element by element,
    a hang). Run in a subprocess with a timeout, so a regression fails instead of hanging."""
    elapsed, refused, kept = _bound_probe()
    assert float(elapsed) < 1
    assert refused == (
        "ub_template_contexts['c']['n']: 9223372036854775808 is outside the signed "
        "64-bit range ubproject.toml integers have"
    )
    assert kept == f"int {2**63 - 1}"


# --- the command line (F4) -------------------------------------------------------------


def test_a_dotted_dash_d_cannot_give_a_table_entry(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """F4 (§2.5): only ``ub_template_enabled`` can be switched with ``-D``; the three
    tables cannot be given on the command line. Sphinx writes a dotted
    ``-D ub_directive_presets.x=...`` into the conf.py dict as a STRING: when the TOML sets
    the key it is lost with the rest of conf.py's value, and without one it is an entry
    that is not a table."""
    dotted = {"ub_directive_presets.dnote": "note"}
    with_key = _project(
        tmp_path / "with",
        conf="ub_directive_presets = {'callout': {'base': 'note'}}\n",
        toml='[parse.directive_presets.box]\nbase = "note"\n',
    )
    app = _build(make_app, with_key, confoverrides=dotted)
    assert list(app.config.ub_directives_resolved["directive_presets"]) == ["box"]
    assert not [w for w in build_warnings(app) if "directive_preset" in w]
    without = _project(tmp_path / "without")
    found = [
        w
        for w in build_warnings(_build(make_app, without, confoverrides=dotted))
        if "ub_directives.directive_preset_invalid_value" in w
    ]
    assert len(found) == 1 and "'dnote' is not a table" in found[0], found


# --- where findings are located (C4) and the extend warning (C5) ---------------------


def test_a_bad_preset_is_located_at_its_source(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """C4/K6: a load-time finding locates at its table's source: conf.py for a conf.py
    table, the TOML for a TOML one, in one mixed project."""
    conf = "ub_directive_templates = {'note': {'body': 'x'}}\n"
    toml = '# comment\n\n[parse.directive_presets.x]\nbase = "no-such"\n'
    root = _project(tmp_path, conf=conf, toml=toml)
    warnings = build_warnings(_build(make_app, root))
    preset = [w for w in warnings if "directive_preset_unknown_base" in w]
    declared = [w for w in warnings if "directive_template_invalid" in w]
    assert preset and preset[0].startswith("<srcdir>/ubproject.toml:3:"), preset
    assert declared and declared[0].startswith("<srcdir>/conf.py:"), declared


#: The line number in a test project's conf.py of the first line after the common head.
_FIRST = CONF_PY.count("\n") + 1

#: A late extension that registers ``note`` over the self-preset after ``builder-inited``.
_LATE = (
    "from docutils.parsers.rst.directives.admonitions import Note\n"
    "class Late(Note):\n    pass\n"
    "def _late(app):\n    app.add_directive('note', Late, override=True)\n"
    "def setup(app):\n    app.connect('builder-inited', _late, priority=900)\n"
)


def test_a_conf_py_finding_is_at_the_assigning_line(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """F5: a conf.py finding is at the LAST line that assigns its confval -- here the
    ``.update`` -- never a longer name it prefixes (``..._shared``) nor an earlier, empty
    assignment."""
    conf = (
        "ub_directive_presets_shared = {'box': {'base': 'note'}}\n"
        "ub_directive_presets = {}\n"
        "ub_directive_presets.update({'bad': {'base': 'no-such'}})\n"
    )
    root = _project(tmp_path, conf=conf)
    found = [
        w
        for w in build_warnings(_build(make_app, root))
        if "directive_preset_unknown_base" in w
    ]
    assert found and found[0].startswith(f"<srcdir>/conf.py:{_FIRST + 2}:"), found


def test_a_reserved_var_context_in_conf_py_is_located_there(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """F5/C4: the reserved ``var`` context from conf.py is located at the line that sets
    ``ub_template_contexts``, not at the project file (which exists, with other keys)."""
    root = _project(
        tmp_path,
        conf="ub_template_contexts = {'var': {'a': 1}}\n",
        toml='[parse.directive_presets.box]\nbase = "note"\n',
    )
    found = [
        w
        for w in build_warnings(_build(make_app, root))
        if "template_context_reserved" in w
    ]
    assert found and found[0].startswith(f"<srcdir>/conf.py:{_FIRST}:"), found


def test_a_replaced_self_preset_from_conf_py_is_located_there(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """F5/C4: a conf.py self-preset that another extension replaces is reported at the
    line that sets ``ub_directive_presets``, not at the project file (which exists)."""
    head = "import os, sys\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
    conf = (
        "extensions = [*extensions, 'late']\n"
        "ub_directive_presets = {'note': {'base': 'note', 'options': {'class': 'd'}}}\n"
    )
    root = _project(
        tmp_path,
        conf=conf,
        toml="[parse.template_contexts.t]\na = 1\n",
        page=".. note::\n\n   Body.\n",
        files={"late.py": _LATE},
    )
    text = (root / "conf.py").read_text(encoding="utf-8")
    (root / "conf.py").write_text(head + text, encoding="utf-8", newline="")
    found = [
        w for w in build_warnings(_build(make_app, root)) if "preset_base_replaced" in w
    ]
    assert found and found[0].startswith(f"<srcdir>/conf.py:{_FIRST + 3}:"), found


def test_no_extend_warning_from_conf_py_tables(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """C5/K7: the extend warning is about the FILE's tables only: a conf.py table beside a
    file with an extend key and no tables of its own does not warn."""
    root = _project(
        tmp_path,
        conf="ub_directive_presets = {'callout': {'base': 'note'}}\n",
        toml='extend = "../base.toml"\n',
    )
    assert not [
        w for w in build_warnings(_build(make_app, root)) if "extend_unsupported" in w
    ]


# --- rebuild ---------------------------------------------------------------------------


@pytest.mark.parametrize("confval", sorted(_config.CONFVALS.values()))
def test_the_confvals_re_read_every_document(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, confval: str
) -> None:
    """K9: each confval is ``rebuild="env"``, so a change re-reads every document."""
    app = make_app("html", srcdir=_project(tmp_path), freshenv=True)
    assert app.config.values[confval].rebuild == "env"


def test_editing_a_confval_re_reads_the_page(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """K9 (behaviour): a second build with an edited conf.py context re-reads the page,
    although no document changed."""
    conf = "ub_template_contexts = {{'c': {{'v': '{v}'}}}}\nub_directive_templates = {{'u': {{'body': 'Value {{{{ contexts.c.v }}}}.'}}}}\n"
    root = _project(tmp_path, conf=conf.format(v="AAAA"), page=".. u::\n")
    first = make_app("html", srcdir=root, freshenv=True)
    first.build()
    assert "Value AAAA." in _html(first)
    first.cleanup()  # as a new process would: the first build's directives are gone
    (root / "conf.py").write_text(
        CONF_PY + conf.format(v="BBBB"), encoding="utf-8", newline=""
    )
    second = make_app("html", srcdir=root, freshenv=False)
    second.build()
    assert "Value BBBB." in _html(second)
