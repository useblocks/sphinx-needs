"""``need:<directive>``, and which directive a need type's bare name is.

Every need type is written ``.. need:<directive>::`` (```` ```{need:<directive>} ```` in
MyST), served by sphinx-needs' ``need`` domain. Whether the bare ``.. <directive>::`` is
the need, where another directive has the same name, is ``needs_directive_name`` and a
need type's ``directive_name``:

========== ============================================== ======================
value      bare ``.. step::``                             ``.. need:step::``
========== ============================================== ======================
unset      the need, over the other directive; reported   the need
claim      the need, over the other directive             the need
yield      the other directive (the need when none has    the need
           the name)
qualified  never the need                                 the need
========== ============================================== ======================

The clash is reported (``needs.directive_name_clash``) only while the mode is unset,
and not where ``app.add_directive`` is suppressed, which silenced Sphinx's own warning
for the same clash before. The other directive here is a stub extension that registers
``step`` in its ``setup()``, as sphinx-design 0.8 does.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.api import add_need_type
from sphinx_needs.exceptions import NeedsApiConfigException
from sphinx_needs.logging import WarningSubTypeDescription, WarningSubTypes
from sphinx_needs_testkit import build_warnings

#: a stub of another extension: ``step`` registered in ``setup()``, as sphinx-design's
STEP_EXTENSION = """\
from docutils import nodes
from docutils.parsers.rst import Directive


class StepDirective(Directive):
    has_content = True
    optional_arguments = 1
    final_argument_whitespace = True

    def run(self):
        return [nodes.paragraph(text="OTHER-STEP " + " ".join(self.arguments))]


def setup(app):
    app.add_directive("step", StepDirective)
    return {"parallel_read_safe": True}
"""

#: the stub's warning text, as a clash names it
STEP_OWNER = "the directive dname_step_ext.StepDirective"

CONF = """\
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
extensions = {extensions!r}
needs_build_json = True
# sphinx 7 does not append `[type.subtype]` to a warning by default; 8 and 9 do
show_warning_types = True
needs_types = [
    {{"directive": "req", "title": "Requirement", "prefix": "R_"}},
    {{"directive": "step", "title": "Step", "prefix": "ST_"{step_keys}}},
]
{extra}
"""

INDEX = """\
Index
=====

.. step:: bare RST

.. need:step:: qualified RST
   :id: ST_Q_RST

.. need:req:: a requirement
   :id: R_001

.. toctree::

   page
"""

PAGE = """\
# Page

```{need:step} qualified MyST
:id: ST_Q_MD
```

```{step} bare MyST
```
"""


def _project(
    extra: str = "",
    *,
    step_keys: str = "",
    other: bool = True,
    other_first: bool = True,
    parallel: int = 0,
) -> dict[str, Any]:
    """A project with need types ``req`` and ``step``, an RST and a MyST page each
    writing ``step`` bare and qualified, and (``other``) another extension's ``step``."""
    extensions = ["myst_parser", "sphinx_needs"]
    if other:
        extensions.insert(0 if other_first else 2, "dname_step_ext")
    return {
        "buildername": "html",
        "parallel": parallel,
        "files": [
            (
                Path("conf.py"),
                CONF.format(extensions=extensions, step_keys=step_keys, extra=extra),
            ),
            (Path("dname_step_ext.py"), STEP_EXTENSION),
            (Path("index.rst"), INDEX),
            (Path("page.md"), PAGE),
        ],
    }


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _bare(app: Any) -> tuple[str, str]:
    """What the bare ``step`` of each page is: ``need``, ``other`` or ``unknown``."""
    needs = _needs(app)
    found = []
    for page, title in (("index", "bare RST"), ("page", "bare MyST")):
        html = Path(app.outdir, f"{page}.html").read_text(encoding="utf-8")
        if any(n["title"] == title and n["type"] == "step" for n in needs.values()):
            found.append("need")
        elif f"OTHER-STEP {title}" in html:
            found.append("other")
        else:
            found.append("unknown")
    return found[0], found[1]


def _qualified_ok(app: Any) -> None:
    """Both qualified needs exist, of the bare type, at the line they are written on."""
    needs = _needs(app)
    assert needs["ST_Q_RST"]["type"] == "step"
    assert needs["ST_Q_MD"]["type"] == "step"
    assert needs["R_001"]["type"] == "req"
    assert (needs["ST_Q_RST"]["docname"], needs["ST_Q_RST"]["lineno"]) == ("index", 6)
    # the MyST fence ``{need:step}`` is located as a bare fence is
    assert (needs["ST_Q_MD"]["docname"], needs["ST_Q_MD"]["lineno"]) == ("page", 3)


def _clash(name: str = "step", owner: str = STEP_OWNER) -> str:
    return (
        f"WARNING: need type {name!r}: the directive name {name!r} is also {owner}; "
        f"a bare '.. {name}::' is the need. Set needs_directive_name (or the type's "
        "directive_name) to 'claim' to keep it so, or to 'yield' to leave the bare name "
        f"to the other directive and write '.. need:{name}::' for the need "
        "[needs.directive_name_clash]"
    )


#: Sphinx's own warning for the clash, which sphinx-needs' replaces
SPHINX_TEXT = "is already registered and will not be overridden"


def test_the_subtype_is_registered() -> None:
    """The clash has a subtype of its own, so it is suppressed without the others."""
    assert "directive_name_clash" in WarningSubTypes.__args__
    assert WarningSubTypeDescription["directive_name_clash"] == (
        "A need type's directive name is another directive's too, and "
        "needs_directive_name does not say which one the bare name is"
    )


# --- the semantics table, with another directive named ``step`` -----------------------


@pytest.mark.parametrize(
    ("test_app", "bare", "warnings"),
    [
        pytest.param(_project(), ("need", "need"), [_clash()], id="unset"),
        pytest.param(
            _project('needs_directive_name = "claim"'), ("need", "need"), [], id="claim"
        ),
        pytest.param(
            _project('needs_directive_name = "yield"'),
            ("other", "other"),
            [],
            id="yield",
        ),
        pytest.param(
            _project('needs_directive_name = "qualified"'),
            ("other", "other"),
            [],
            id="qualified",
        ),
    ],
    indirect=["test_app"],
)
def test_a_clash_in_each_mode(
    test_app: Any, bare: tuple[str, str], warnings: list[str]
) -> None:
    """Each row of the table, RST and MyST: what a bare ``step`` is, the qualified
    spelling always the need, and the one warning while the mode is unset (never
    Sphinx's misleading ``app.add_directive`` text)."""
    app = test_app
    app.build()
    assert build_warnings(app) == warnings
    assert _bare(app) == bare
    _qualified_ok(app)


@pytest.mark.parametrize(
    ("test_app", "bare", "warnings"),
    [
        pytest.param(_project(other=False), ("need", "need"), [], id="unset"),
        pytest.param(
            _project('needs_directive_name = "claim"', other=False),
            ("need", "need"),
            [],
            id="claim",
        ),
        pytest.param(
            _project('needs_directive_name = "yield"', other=False),
            ("need", "need"),
            [],
            id="yield",
        ),
        pytest.param(
            _project('needs_directive_name = "qualified"', other=False),
            ("unknown", "unknown"),
            [
                '<srcdir>/index.rst:4: ERROR: Unknown directive type "step".\n\n'
                ".. step:: bare RST [docutils]",
                "<srcdir>/page.md:7: WARNING: Unknown directive type: 'step' "
                "[myst.directive_unknown]",
            ],
            id="qualified",
        ),
    ],
    indirect=["test_app"],
)
def test_no_clash_in_each_mode(
    test_app: Any, bare: tuple[str, str], warnings: list[str]
) -> None:
    """Without another ``step``: the bare name is the need but under ``qualified``,
    where it is no directive at all; nothing is reported but the unknown directive."""
    app = test_app
    app.build()
    # the myst-parser of the sphinx-7 cell locates a MyST page's warning as ``.md.rst``
    assert [w.replace(".md.rst:", ".md:") for w in build_warnings(app)] == warnings
    assert _bare(app) == bare
    _qualified_ok(app)


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(_project(other_first=True), id="other-first"),
        pytest.param(_project(other_first=False), id="other-last"),
    ],
    indirect=True,
)
def test_the_extension_order_does_not_matter(test_app: Any) -> None:
    """The need's directive is registered at ``config-inited``, after every ``setup()``:
    the other extension is seen whichever comes first in ``extensions``."""
    app = test_app
    app.build()
    assert build_warnings(app) == [_clash()]
    assert _bare(app) == ("need", "need")


@pytest.mark.parametrize(
    "test_app",
    [_project('needs_directive_name = "yield"', parallel=2)],
    indirect=True,
)
def test_a_parallel_read(test_app: Any) -> None:
    """The ``need`` domain holds no data, so a parallel read merges nothing."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _bare(app) == ("other", "other")
    _qualified_ok(app)


# --- the per-type key -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("test_app", "bare"),
    [
        pytest.param(
            _project(
                'needs_directive_name = "yield"',
                step_keys=', "directive_name": "claim"',
            ),
            ("need", "need"),
            id="claim-over-yield",
        ),
        pytest.param(
            _project(
                'needs_directive_name = "qualified"',
                step_keys=', "directive_name": "claim"',
            ),
            ("need", "need"),
            id="claim-over-qualified",
        ),
        pytest.param(
            _project(
                'needs_directive_name = "claim"',
                step_keys=', "directive_name": "yield"',
            ),
            ("other", "other"),
            id="yield-over-claim",
        ),
        pytest.param(
            _project(step_keys=', "directive_name": "yield"'),
            ("other", "other"),
            id="yield-over-unset",
        ),
        pytest.param(
            _project(step_keys=', "directive_name": "claim"'),
            ("need", "need"),
            id="claim-over-unset",
        ),
    ],
    indirect=["test_app"],
)
def test_the_type_key_wins(test_app: Any, bare: tuple[str, str]) -> None:
    """A type's ``directive_name`` wins over ``needs_directive_name``, and a type that
    gives one is never reported, whatever the global value."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _bare(app) == bare
    _qualified_ok(app)


TOML = """\
[needs]
directive_name = "{mode}"

[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.step]
title = "Step"
prefix = "ST_"
{step_line}
"""


def _toml_project(mode: str, step_line: str = "") -> dict[str, Any]:
    project = _project()
    conf = (
        "import os, sys\n"
        "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        "extensions = ['dname_step_ext', 'myst_parser', 'sphinx_needs']\n"
        "needs_build_json = True\n"
        "needs_from_toml = 'ubproject.toml'\n"
    )
    project["files"] = [
        (Path("conf.py"), conf),
        (Path("ubproject.toml"), TOML.format(mode=mode, step_line=step_line)),
        *project["files"][1:],
    ]
    return project


@pytest.mark.parametrize(
    ("test_app", "bare"),
    [
        pytest.param(_toml_project("yield"), ("other", "other"), id="global"),
        pytest.param(
            _toml_project("yield", 'directive_name = "claim"'),
            ("need", "need"),
            id="per-type",
        ),
    ],
    indirect=["test_app"],
)
def test_the_keys_in_ubproject_toml(test_app: Any, bare: tuple[str, str]) -> None:
    """``[needs] directive_name`` and a ``[needs.types.<type>]`` entry's
    ``directive_name``, the keys ubCode reads from the same file."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _bare(app) == bare
    _qualified_ok(app)


# --- what is reported, and its suppression --------------------------------------------


@pytest.mark.parametrize(
    ("test_app", "warnings"),
    [
        pytest.param(
            _project('suppress_warnings = ["app.add_directive"]'),
            [],
            id="app.add_directive",
        ),
        pytest.param(_project('suppress_warnings = ["app"]'), [], id="app"),
        pytest.param(_project('suppress_warnings = ["app.*"]'), [], id="app.*"),
        pytest.param(
            _project('suppress_warnings = ["needs.directive_name_clash"]'),
            [],
            id="needs.directive_name_clash",
        ),
        pytest.param(
            _project('suppress_warnings = ["app.add_node", "needs.config"]'),
            [_clash()],
            id="other-entries",
        ),
    ],
    indirect=["test_app"],
)
def test_the_warning_is_silent_where_sphinx_s_was(
    test_app: Any, warnings: list[str]
) -> None:
    """A project that silenced Sphinx's ``app.add_directive`` warning for this clash
    (``app.add_directive``, ``app`` or ``app.*``) stays silent: the new warning does not
    fail its ``-W`` build. ``needs.directive_name_clash`` silences it alone, and other
    entries do not. The need keeps the bare name either way."""
    app = test_app
    app.build()
    assert build_warnings(app) == warnings
    assert _bare(app) == ("need", "need")


SHADOWED_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
# sphinx 7 does not append `[type.subtype]` to a warning by default; 8 and 9 do
show_warning_types = True
needs_types = [
    {{"directive": "data", "title": "Data", "prefix": "D_"}},
    {{"directive": "glossary", "title": "Glossary", "prefix": "G_"}},
]
{extra}
"""

SHADOWED_INDEX = """\
Index
=====

.. need:data:: qualified data
   :id: D_001

.. need:glossary:: qualified glossary
   :id: G_001
"""


def _shadowed(extra: str = "") -> dict[str, Any]:
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), SHADOWED_CONF.format(extra=extra)),
            (Path("index.rst"), SHADOWED_INDEX),
        ],
    }


def _domain_clash(name: str, domain: str) -> str:
    return (
        f"WARNING: need type {name!r}: the directive name {name!r} is also the "
        f"{domain} domain's directive '{domain}:{name}'; a bare '.. {name}::' runs it, "
        f"as Sphinx looks it up first. Write '.. need:{name}::' for the need, and set "
        "needs_directive_name (or the type's directive_name) to 'yield' to say so "
        "[needs.directive_name_clash]"
    )


@pytest.mark.parametrize(
    ("test_app", "warnings"),
    [
        pytest.param(
            _shadowed(),
            [_domain_clash("data", "py"), _domain_clash("glossary", "std")],
            id="unset",
        ),
        pytest.param(
            _shadowed('suppress_warnings = ["app.add_directive"]'), [], id="suppressed"
        ),
        pytest.param(_shadowed('needs_directive_name = "yield"'), [], id="yield"),
        pytest.param(_shadowed('needs_directive_name = "claim"'), [], id="claim"),
        pytest.param(
            _shadowed('primary_domain = "c"'),
            [_domain_clash("glossary", "std")],
            id="primary-domain-c",
        ),
    ],
    indirect=["test_app"],
)
def test_a_name_a_domain_shadows(test_app: Any, warnings: list[str]) -> None:
    """A need type named as a directive of the ``std`` or the primary domain was never
    usable bare (Sphinx looks a domain up first), and nothing said so: it is reported
    while the mode is unset, gated as the other clashes are, and ``need:<directive>``
    is the need. ``data`` is the ``py`` domain's only while ``py`` is primary."""
    app = test_app
    app.build()
    assert build_warnings(app) == warnings
    needs = _needs(app)
    assert (needs["D_001"]["type"], needs["G_001"]["type"]) == ("data", "glossary")


# --- validation -----------------------------------------------------------------------


INVALID_CONF = """\
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
extensions = ["dname_step_ext", "sphinx_needs"]
needs_build_json = True
# sphinx 7 does not append `[type.subtype]` to a warning by default; 8 and 9 do
show_warning_types = True
needs_directive_name = "nope"
needs_types = {types}
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    INVALID_CONF.format(
                        types=[
                            {"directive": "req", "title": "R", "prefix": "R_"},
                            {
                                "directive": "step",
                                "title": "S",
                                "prefix": "ST_",
                                "directive_name": "Yield",
                            },
                            {"directive": "a:b", "title": "AB", "prefix": "AB_"},
                        ]
                    ),
                ),
                (Path("dname_step_ext.py"), STEP_EXTENSION),
                (Path("index.rst"), "Index\n=====\n\n.. step:: bare\n"),
            ],
        }
    ],
    indirect=True,
)
def test_invalid_values_are_reported_and_unset(test_app: Any) -> None:
    """A value none of the three is a ``needs.config`` warning naming them, and is
    unset (so the clash is reported); a directive with a ``:`` drops its entry."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types entry 2 ('step') has a 'directive_name' that is not one "
        "of 'claim', 'yield' and 'qualified' (got 'Yield'); the key is ignored "
        "[needs.config]",
        "WARNING: needs_types entry 3 ('a:b') has directive = 'a:b', which has a ':': "
        "a directive name of a need type cannot (its needs are written "
        "'.. need:<directive>::' too); the entry is ignored [needs.config]",
        "WARNING: needs_directive_name is 'nope', which is not one of 'claim', 'yield' "
        "and 'qualified'; it is ignored (a need type's bare directive name is the "
        "need's, and a clash is reported) [needs.config]",
        _clash(),
    ]
    assert [n["type"] for n in _needs(app).values()] == ["step"]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\n'
                    "show_warning_types = True\n"
                    'needs_types = {"a:b": {"title": "AB", "prefix": "AB_"}}\n',
                ),
                (Path("index.rst"), "Index\n=====\n"),
            ],
        }
    ],
    indirect=True,
)
def test_a_colon_in_a_mapping_key(test_app: Any) -> None:
    """The mapping shape refuses a ``:`` in its key as the list shape does."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "WARNING: needs_types['a:b'] has directive = 'a:b', which has a ':': a "
        "directive name of a need type cannot (its needs are written "
        "'.. need:<directive>::' too); the entry is ignored [needs.config]",
    ]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [(Path("conf.py"), ""), (Path("index.rst"), "")],
        }
    ],
    indirect=True,
)
def test_add_need_type_refuses_a_colon(test_app: Any) -> None:
    """``add_need_type`` refuses a directive with a ``:``, as a configured entry is."""
    with pytest.raises(NeedsApiConfigException, match="has a ':'"):
        add_need_type(test_app, "x:y", "XY", "XY_")


# --- a need type an extension adds ----------------------------------------------------


ADDED_CONF = """\
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
extensions = ["dname_step_ext", "myst_parser", "sphinx_needs"]
needs_build_json = True
# sphinx 7 does not append `[type.subtype]` to a warning by default; 8 and 9 do
show_warning_types = True
needs_types = [
    {{"directive": "req", "title": "Requirement", "prefix": "R_"}},
    {narrowing}
]


def _add_step(app, *_args):
    from sphinx_needs.api import add_need_type
    add_need_type(app, "step", "Step", "ST_")


def setup(app):
    app.connect("config-inited", _add_step, priority=500)
"""


@pytest.mark.parametrize(
    ("test_app", "bare", "warnings"),
    [
        pytest.param(
            {
                **_project(),
                "files": [
                    (Path("conf.py"), ADDED_CONF.format(narrowing="")),
                    *_project()["files"][1:],
                ],
            },
            ("need", "need"),
            [_clash()],
            id="unset",
        ),
        pytest.param(
            {
                **_project(),
                "files": [
                    (
                        Path("conf.py"),
                        ADDED_CONF.format(
                            narrowing='{"directive": "step", "directive_name": "yield"},'
                        ),
                    ),
                    *_project()["files"][1:],
                ],
            },
            ("other", "other"),
            [],
            id="narrowed-yield",
        ),
    ],
    indirect=["test_app"],
)
def test_a_type_an_extension_adds(
    test_app: Any, bare: tuple[str, str], warnings: list[str]
) -> None:
    """A type added with ``add_need_type`` is ``need:``-qualified too, and the
    project's entry narrowing it gives its ``directive_name``."""
    app = test_app
    app.build()
    assert build_warnings(app) == warnings
    assert _bare(app) == bare
    _qualified_ok(app)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    'extensions = ["sphinx_needs"]\nshow_warning_types = True\n',
                ),
                (
                    Path("index.rst"),
                    textwrap.dedent("""\
                        Index
                        =====

                        .. need:nope:: not a need type
                    """),
                ),
            ],
        }
    ],
    indirect=True,
)
def test_an_unknown_qualified_name(test_app: Any) -> None:
    """``need:<name>`` naming no need type is docutils' ordinary unknown directive."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        '<srcdir>/index.rst:4: ERROR: Unknown directive type "need:nope".\n\n'
        ".. need:nope:: not a need type [docutils]",
    ]


BUILTIN_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
# sphinx 7 does not append `[type.subtype]` to a warning by default; 8 and 9 do
show_warning_types = True
needs_types = [{{"directive": "image", "title": "Image", "prefix": "IM_"}}]
{extra}
"""

BUILTIN_INDEX = """\
Index
=====

.. image:: picture.png

.. need:image:: qualified image
   :id: IM_001
"""


@pytest.mark.parametrize(
    ("test_app", "bare_is_need"),
    [
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (Path("conf.py"), BUILTIN_CONF.format(extra="")),
                    (Path("index.rst"), BUILTIN_INDEX),
                ],
            },
            True,
            id="unset",
        ),
        pytest.param(
            {
                "buildername": "html",
                "files": [
                    (
                        Path("conf.py"),
                        BUILTIN_CONF.format(extra='needs_directive_name = "yield"'),
                    ),
                    (Path("index.rst"), BUILTIN_INDEX),
                ],
            },
            False,
            id="yield",
        ),
    ],
    indirect=["test_app"],
)
def test_a_docutils_directive_sphinx_has_not_registered(
    test_app: Any, bare_is_need: bool
) -> None:
    """docutils' ``image``, which Sphinx does not register itself: a need type of that
    name takes it silently, as before (Sphinx's warning never saw it), and under
    ``yield`` leaves it to docutils."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    needs = _needs(app)
    assert needs["IM_001"]["type"] == "image"
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    if bare_is_need:
        assert warnings == []
        assert sorted(n["title"] for n in needs.values()) == [
            "picture.png",
            "qualified image",
        ]
        assert "<img" not in html
    else:
        # the picture does not exist: docutils' image is what reports it
        assert [w for w in warnings if "picture.png" not in w] == []
        assert list(needs) == ["IM_001"]
        assert 'src="picture.png"' in html or "<img" in html
