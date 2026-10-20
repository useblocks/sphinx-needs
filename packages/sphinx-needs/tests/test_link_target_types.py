"""The ``target_types`` of a link type: which need types its links may point to.

The shared behaviour is pinned by the ``link-target-types-*`` cases of the conformance
corpus (``tests/fixtures/field_declaration_conformance.toml``), which compare codes,
needs, link types and types. These tests pin what the corpus does not: the words of
every warning (the configuration's, and the link check's), the narrowing rule as a pure
function, the external-need path and its own suppression, and the refusal of
``target_types`` on ``links`` while a link type copies into it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs._wording import joined, title_hint
from sphinx_needs.derive import DeriveRule
from sphinx_needs.needs import _type_descendants
from sphinx_needs.needs_schema import (
    LinkDisplayConfig,
    LinkSchema,
    LinkTargetTypes,
    narrowing_problems,
)
from sphinx_needs_testkit import build_warnings

CONF_PY = 'extensions = ["sphinx_needs"]\nneeds_from_toml = "ubproject.toml"\n'

TYPES = """\
[needs.types.req]
title = "Requirement"
prefix = "R_"

[needs.types.safety_req]
title = "Safety requirement"
prefix = "SR_"
inherits = "req"

[needs.types.spec]
title = "Specification"
prefix = "S_"

[needs.types.test]
title = "Test"
prefix = "T_"
"""


def _project(
    toml: str, index: str, *, conf: str = CONF_PY, **files: str
) -> dict[str, Any]:
    """A ``test_app`` parameter: a project of ``conf.py``, ``ubproject.toml``, ``index.rst``."""
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), conf),
            (Path("ubproject.toml"), toml),
            (Path("index.rst"), "Case\n====\n\n" + index),
            *((Path(name), text) for name, text in files.items()),
        ],
    }


CONFIG_TOML = (
    TYPES
    + """
[needs.links.verifies]
target_types = ["req", "Specification", "nope"]

[needs.links.checks]
target_types = "req"

[needs.links.mentions]
target_types = []

[needs.links.cites]
target_types = ["req", 1]

[needs.links.blanks]
target_types = ["req", ""]

[needs.links.covers]
derive = { kind = "links", where = "type == 'spec'" }
target_types = ["req"]

[needs.links.traces]
derive_by_type = { test = { kind = "links", where = "type == 'req'" } }
target_types = ["req"]

[needs.links.relates]
target_types = ["rq"]

[needs.types.test.links.verifies]
target_types = ["safety_req", "spec"]

[needs.types.spec.links.covers]
target_types = ["req"]

[needs.types.req.links.checks]
target_types = ["sepc", "tset"]
"""
)


@pytest.mark.parametrize(
    "test_app", [_project(CONFIG_TOML, "Nothing.\n")], indirect=True
)
def test_what_the_configuration_reports(test_app: SphinxTestApp) -> None:
    """Every configuration finding of a ``target_types``, word for word.

    Not of its shape -- a bare string, an empty list, an item that is not a name (an
    empty string among names included, so the whole key is ignored) -- is a
    ``needs.config`` finding (an entry's at ``config-inited``, a ``needs_links`` one's
    where the schema is built), the key ignored. A name that is no need type is one
    finding per declaration, a title pointed at its directive; when no name is left,
    the key is ignored. Beside a rule it is a ``needs.derive_invalid`` (``derive`` and
    ``derive_by_type`` alike), and in a need type's entry of a derived link type a
    ``needs.type_conflict``. A need type's entry naming a type the global ones do not
    accept widens them.
    """
    test_app.build()
    assert build_warnings(test_app) == [
        "WARNING: needs_links['verifies'] has a 'target_types' naming 'Specification' "
        "(did you mean 'spec'?) and 'nope', which are not need types; the names "
        "are ignored [needs.config]",
        "WARNING: needs_links['checks'] has a 'target_types' that is not a non-empty "
        "list of need type names (got str); the key is ignored [needs.config]",
        "WARNING: needs_links['mentions'] has a 'target_types' that is not a "
        "non-empty list of need type names (got an empty list); the key is ignored "
        "[needs.config]",
        "WARNING: needs_links['cites'] has a 'target_types' that is not a non-empty "
        "list of need type names (got a list with an item that is not a non-empty "
        "string); the key is ignored [needs.config]",
        "WARNING: needs_links['blanks'] has a 'target_types' that is not a non-empty "
        "list of need type names (got a list with an item that is not a non-empty "
        "string); the key is ignored [needs.config]",
        "WARNING: needs_links['relates'] has a 'target_types' naming 'rq', which is "
        "not a need type; the key is ignored [needs.config]",
        "WARNING: Invalid derive of link type 'covers': kind 'links': 'target_types' "
        "cannot be given beside derive, and is ignored; the rule applies "
        "[needs.derive_invalid]",
        "WARNING: Invalid derive of link type 'traces': 'target_types' cannot be "
        "given beside derive_by_type, and is ignored; the rules apply "
        "[needs.derive_invalid]",
        "WARNING: needs_types['req'].links['checks'] has a 'target_types' naming "
        "'sepc' and 'tset', which are not need types; the key is ignored "
        "[needs.config]",
        "WARNING: needs_types['spec'].links['covers'] sets 'target_types', but "
        "'covers' is derived (kind 'links'): a need type declares only its "
        "description and schema; the entry is ignored [needs.type_conflict]",
        "WARNING: needs_types['test'].links['verifies'] widens the field: Child "
        "'target_types' accept 'spec', which parent 'target_types' ['req'] (or a type "
        "inheriting from it) do not. [needs.type_widening]",
    ]


LINKS_TOML = (
    TYPES
    + """
[needs.types.unit_test]
title = "Unit test"
prefix = "UT_"
inherits = "test"

[needs.links.verifies]
target_types = ["req", "spec"]

[needs.types.test.links.verifies]
target_types = ["safety_req"]

[needs.types.unit_test.links.verifies]
description = "What a unit test verifies"

[needs.types.impl]
title = "Implementation"
prefix = "I_"

[needs.types.impl.links.verifies]
description = "What an implementation verifies"
"""
)

LINKS_INDEX = """\
.. req:: Requirement
   :id: REQ_1

   A part: :np:`(p1) of it`.

.. safety_req:: Safety requirement
   :id: SREQ_1

.. spec:: Specification
   :id: SPEC_1

.. test:: Narrowed by its type
   :id: TEST_1
   :verifies: REQ_1.p1, SREQ_1, SPEC_1[status == 'open']

.. unit_test:: Inherits the narrowing
   :id: UTEST_1
   :verifies: SREQ_1, TEST_1

.. spec:: The global target types
   :id: SPEC_2
   :verifies: SPEC_1, TEST_1, REQ_404

.. impl:: An entry that gives no target types
   :id: IMPL_1
   :verifies: TEST_1
"""


@pytest.mark.parametrize("test_app", [_project(LINKS_TOML, LINKS_INDEX)], indirect=True)
def test_what_the_link_check_reports(test_app: SphinxTestApp) -> None:
    """The ``needs.link_target_type`` warning, word for word: at the source need,
    naming the link as written (a part by its own id, its condition included), the
    field, the target's type, and the declared names, never their expansion; plural for
    several; and the need type that declares them, where one does -- an ancestor's for
    a type inheriting the declaration, also through an entry of its own that gives
    other keys but no target types (``unit_test``), and none for such an entry under
    the global ones (``impl``). A link failing its condition too is reported for each;
    a dead link only as a dead link."""
    test_app.build()
    assert build_warnings(test_app) == [
        "<srcdir>/index.rst:15: WARNING: Need 'TEST_1' link 'REQ_1.p1' in field "
        "'verifies': target need type 'req' is not one of 'safety_req' (or a type "
        "inheriting from it), as need type 'test' declares it "
        "[needs.link_target_type]",
        "<srcdir>/index.rst:15: WARNING: Need 'TEST_1' link "
        "'SPEC_1[status == 'open']' in field "
        "'verifies': target need type 'spec' is not one of 'safety_req' (or a type "
        "inheriting from it), as need type 'test' declares it "
        "[needs.link_target_type]",
        "<srcdir>/index.rst:15: WARNING: Need 'TEST_1' link 'SPEC_1' in field "
        "'verifies': condition \"status == 'open'\" not satisfied by target need "
        "'SPEC_1' [needs.link_condition_failed]",
        "<srcdir>/index.rst:19: WARNING: Need 'UTEST_1' link 'TEST_1' in field "
        "'verifies': target need type 'test' is not one of 'safety_req' (or a type "
        "inheriting from it), as need type 'test' declares it "
        "[needs.link_target_type]",
        "<srcdir>/index.rst:23: WARNING: Need 'SPEC_2' link 'TEST_1' in field "
        "'verifies': target need type 'test' is not one of 'req' or 'spec' (or a type "
        "inheriting from them) [needs.link_target_type]",
        "<srcdir>/index.rst:23: WARNING: Need 'SPEC_2' has unknown outgoing link "
        "'REQ_404' in field 'verifies' [needs.link_outgoing]",
        "<srcdir>/index.rst:27: WARNING: Need 'IMPL_1' link 'TEST_1' in field "
        "'verifies': target need type 'test' is not one of 'req' or 'spec' (or a type "
        "inheriting from them) [needs.link_target_type]",
    ]


EXTERNAL_TOML = (
    TYPES
    + """
[needs]
external_needs = [{ base_url = "http://example.org", json_path = "other.json", id_prefix = "E_" }]

[needs.links.verifies]
target_types = ["req"]
"""
)

EXTERNAL_JSON = """\
{"current_version": "1.0", "versions": {"1.0": {"needs": {
  "TEST_1": {"id": "TEST_1", "type": "test", "title": "External", "verifies": ["SPEC_1"]}
}}}}
"""

EXTERNAL_INDEX = """\
.. spec:: Specification
   :id: SPEC_1

.. test:: Local
   :id: TEST_2
   :verifies: SPEC_1
"""

EXTERNAL_WARNING = (
    "WARNING: http://example.org/__error__.html#TEST_1: Need 'E_TEST_1' link 'SPEC_1' "
    "in field 'verifies': target need type 'spec' is not one of 'req' (or a type "
    "inheriting from it) [needs.external_link_target_type]"
)
LOCAL_WARNING = (
    "<srcdir>/index.rst:7: WARNING: Need 'TEST_2' link 'SPEC_1' in field 'verifies': "
    "target need type 'spec' is not one of 'req' (or a type inheriting from it) "
    "[needs.link_target_type]"
)


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        pytest.param(
            _project(EXTERNAL_TOML, EXTERNAL_INDEX, **{"other.json": EXTERNAL_JSON}),
            [EXTERNAL_WARNING, LOCAL_WARNING],
            id="both",
        ),
        pytest.param(
            _project(
                EXTERNAL_TOML,
                EXTERNAL_INDEX,
                conf=CONF_PY + 'suppress_warnings = ["needs.link_target_type"]\n',
                **{"other.json": EXTERNAL_JSON},
            ),
            [EXTERNAL_WARNING],
            id="local-suppressed",
        ),
        pytest.param(
            _project(
                EXTERNAL_TOML,
                EXTERNAL_INDEX,
                conf=CONF_PY
                + 'suppress_warnings = ["needs.external_link_target_type"]\n',
                **{"other.json": EXTERNAL_JSON},
            ),
            [LOCAL_WARNING],
            id="external-suppressed",
        ),
    ],
    indirect=["test_app"],
)
def test_an_external_source_has_its_own_subtype(
    test_app: SphinxTestApp, expected: list[str]
) -> None:
    """The links of a need from ``needs_external_needs`` are checked as a local need's,
    reported at its URL with no location, as ``needs.external_link_target_type``, which
    ``suppress_warnings`` reaches apart from ``needs.link_target_type``."""
    test_app.build()
    assert build_warnings(test_app) == expected


IMPORT_INDEX = """\
.. spec:: Specification
   :id: SPEC_1

.. needimport:: other.json
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            TYPES + '\n[needs.links.verifies]\ntarget_types = ["req"]\n',
            IMPORT_INDEX,
            **{"other.json": EXTERNAL_JSON},
        )
    ],
    indirect=True,
)
def test_an_imported_source_is_reported_at_the_needimport(
    test_app: SphinxTestApp,
) -> None:
    """An imported need's link is checked by its type, and reported at the
    ``needimport`` that imports it, naming the imported need."""
    test_app.build()
    assert build_warnings(test_app) == [
        "<srcdir>/index.rst:7: WARNING: Need 'TEST_1' link 'SPEC_1' in field "
        "'verifies': target need type 'spec' is not one of 'req' (or a type "
        "inheriting from it) [needs.link_target_type]",
    ]


REFUSAL_TOML = (
    TYPES
    + """
[needs.links.links]
target_types = ["spec"]

[needs.links.verifies]
copy = true

[needs.links.implements]
copy = true

[needs.types.test.links.links]
target_types = ["spec"]
schema = { maxItems = 1 }
"""
)

REFUSAL_INDEX = """\
.. req:: Requirement
   :id: REQ_1

.. test:: Verifies a req, and links two
   :id: TEST_1
   :verifies: REQ_1
   :links: REQ_1, SPEC_404
"""


@pytest.mark.parametrize(
    "test_app", [_project(REFUSAL_TOML, REFUSAL_INDEX)], indirect=True
)
def test_target_types_on_links_beside_a_copy_are_refused(
    test_app: SphinxTestApp,
) -> None:
    """While a link type copies into ``links``, a ``target_types`` on ``links`` is one
    ``needs.config`` warning per declaration, naming the copying link types, and is
    ignored (the rest of a need type's entry applies: its ``maxItems`` reports the
    two links, the copy and the written one being one); no link of ``links`` is
    checked."""
    test_app.build()
    warnings = build_warnings(test_app)
    assert warnings[:4] == [
        _deprecated_copy("needs_links['verifies']", "verifies"),
        _deprecated_copy("needs_links['implements']", "implements"),
        "WARNING: needs_links['links'] has a 'target_types', but 'verifies' and "
        "'implements' copy into links (copy = true); the key is ignored until copy is "
        "replaced [needs.config]",
        "WARNING: needs_types['test'].links['links'] has a 'target_types', but "
        "'verifies' and 'implements' copy into links (copy = true); the key is ignored "
        "until copy is replaced [needs.config]",
    ]
    assert not any("needs.link_target_type" in warning for warning in warnings)
    assert any("maxItems" in warning for warning in warnings)


NO_REFUSAL_TOML = (
    TYPES
    + """
[needs.links.links]
copy = true
target_types = ["spec"]

[needs.links.covers]
derive = { kind = "links", where = "type == 'req'" }
copy = true
"""
)


NO_REFUSAL_INDEX = """\
.. req:: Requirement
   :id: REQ_1

.. test:: Links two
   :id: TEST_1
   :links: REQ_1, SPEC_404
"""


@pytest.mark.parametrize(
    "test_app", [_project(NO_REFUSAL_TOML, NO_REFUSAL_INDEX)], indirect=True
)
def test_a_copy_that_copies_nothing_refuses_nothing(test_app: SphinxTestApp) -> None:
    """``copy`` on ``links`` itself, and on a derived link type (refused), copies
    nothing into ``links``: the ``target_types`` of ``links`` holds. On ``links`` the
    key is deprecated all the same; on the derived link type its refusal is the one
    finding."""
    test_app.build()
    assert build_warnings(test_app) == [
        "WARNING: needs_links['links'] sets 'copy = true', which is deprecated and "
        "will be removed in sphinx-needs 10.0; on links it copies nothing, so remove "
        "it [needs.deprecated]",
        "WARNING: Invalid derive of link type 'covers': kind 'links': 'copy' is not "
        "available on a derived link type in this release, and is ignored; the rule "
        "applies [needs.derive_invalid]",
        "<srcdir>/index.rst:7: WARNING: Need 'TEST_1' link 'REQ_1' in field 'links': "
        "target need type 'req' is not one of 'spec' (or a type inheriting from it) "
        "[needs.link_target_type]",
        "<srcdir>/index.rst:7: WARNING: Need 'TEST_1' has unknown outgoing link "
        "'SPEC_404' in field 'links' [needs.link_outgoing]",
    ]


def _deprecated_copy(where: str, name: str) -> str:
    """The ``needs.deprecated`` warning of a declaration writing ``copy = true``."""
    return (
        f"WARNING: {where} sets 'copy = true', which is deprecated and will be removed "
        "in sphinx-needs 10.0; declare a link type deriving the union instead, e.g. "
        f'derive = {{kind = "union", fields = ["links", "{name}"]}}, and read it where '
        "the copies in links were read [needs.deprecated]"
    )


def _link(**kwargs: Any) -> LinkSchema:
    return LinkSchema(
        name="verifies",
        schema={"type": "array", "items": {"type": "string"}},
        display=LinkDisplayConfig(incoming="is verified by", outgoing="verifies"),
        **kwargs,
    )


REQ = LinkTargetTypes(names=("req",), types=frozenset({"req", "safety_req"}))
SAFETY = LinkTargetTypes(
    names=("safety_req",), types=frozenset({"safety_req"}), declared_by="test"
)
REQ_SPEC = LinkTargetTypes(names=("req", "spec"), types=frozenset({"req", "spec"}))
SPEC_TEST = LinkTargetTypes(names=("spec", "test"), types=frozenset({"spec", "test"}))
TEST = LinkTargetTypes(names=("test",), types=frozenset({"test"}))


@pytest.mark.parametrize(
    ("base", "overlay", "problems"),
    [
        pytest.param(None, None, [], id="unrestricted"),
        pytest.param(None, REQ, [], id="restricting-an-unrestricted-one"),
        pytest.param(REQ, REQ, [], id="the-same"),
        pytest.param(REQ, SAFETY, [], id="a-subtype"),
        pytest.param(
            REQ,
            REQ_SPEC,
            [
                "Child 'target_types' accept 'spec', which parent 'target_types' "
                "['req'] (or a type inheriting from it) do not."
            ],
            id="another-type",
        ),
        pytest.param(
            REQ,
            SPEC_TEST,
            [
                "Child 'target_types' accept 'spec' and 'test', which parent "
                "'target_types' ['req'] (or a type inheriting from it) do not."
            ],
            id="two-other-types",
        ),
        pytest.param(
            REQ_SPEC,
            TEST,
            [
                "Child 'target_types' accept 'test', which parent 'target_types' "
                "['req', 'spec'] (or a type inheriting from them) do not."
            ],
            id="under-two-types",
        ),
        pytest.param(
            SAFETY,
            REQ,
            [
                "Child 'target_types' accept 'req', which parent 'target_types' "
                "['safety_req'] (or a type inheriting from it) do not."
            ],
            id="a-supertype",
        ),
        pytest.param(
            REQ, None, ["Child drops parent 'target_types' ['req']."], id="dropped"
        ),
    ],
)
def test_target_types_only_narrow(
    base: LinkTargetTypes | None,
    overlay: LinkTargetTypes | None,
    problems: list[str],
) -> None:
    """Rule 11 of ``narrowing_problems``: the accepted types (the expansion, not the
    names) of a declaration are among those of the one before it; none before it
    restricts nothing."""
    assert (
        narrowing_problems(_link(target_types=base), _link(target_types=overlay))
        == problems
    )


def test_a_derived_link_type_takes_no_target_types() -> None:
    with pytest.raises(ValueError, match="A derived link type takes no target_types"):
        _link(
            target_types=REQ,
            derive=DeriveRule(kind="links", where="type == 'spec'"),
        )


@pytest.mark.parametrize(
    ("names", "types"),
    [
        pytest.param((), frozenset(), id="no-names"),
        pytest.param(("",), frozenset({""}), id="an-empty-name"),
        pytest.param(("req",), frozenset({"spec"}), id="a-name-not-accepted"),
    ],
)
def test_target_types_are_names_they_accept(
    names: tuple[str, ...], types: frozenset[str]
) -> None:
    with pytest.raises(ValueError):
        LinkTargetTypes(names=names, types=types)


def test_the_descendants_of_each_type() -> None:
    """Each type with every type inheriting from it, transitively, through the parents
    ``inherits`` leaves."""
    assert _type_descendants(
        ["req", "safety_req", "asil_req", "spec"],
        {"safety_req": "req", "asil_req": "safety_req"},
    ) == {
        "req": frozenset({"req", "safety_req", "asil_req"}),
        "safety_req": frozenset({"safety_req", "asil_req"}),
        "asil_req": frozenset({"asil_req"}),
        "spec": frozenset({"spec"}),
    }


@pytest.mark.parametrize(
    ("items", "word", "expected"),
    [
        (["'a'"], "and", "'a'"),
        (["'a'", "'b'"], "or", "'a' or 'b'"),
        (["'a'", "'b'", "'c'"], "and", "'a', 'b' and 'c'"),
    ],
)
def test_the_shared_join(items: list[str], word: str, expected: str) -> None:
    """The one "a, b and c" join every message uses."""
    assert joined(items, word) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param("Specification", " (did you mean 'spec'?)", id="a-title"),
        pytest.param("spec", "", id="a-need-type"),
        pytest.param("nope", "", id="neither"),
        pytest.param(
            "Requirement", " (did you mean 'safety_req'?)", id="a-shared-title"
        ),
    ],
)
def test_the_title_hint(name: str, expected: str) -> None:
    """The hint ``target_types`` and ``derive_by_type`` give for a title given where a
    directive name is meant; where two types share the title, the one given last."""
    types = {"req": "Requirement", "safety_req": "Requirement", "spec": "Specification"}
    assert title_hint(name, types) == expected
