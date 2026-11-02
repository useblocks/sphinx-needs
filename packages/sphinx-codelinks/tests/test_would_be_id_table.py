"""The ids :func:`would_be_id` predicts, pinned byte for byte over a table of shapes.

``would_be_id`` is the id the duplicate check and the ``[docs]`` link use for a need
whose marker gives none: the one Sphinx-Needs generates. Every row of :data:`SHAPES` is a
need as ``render_needs`` passes it (a one-line marker's fields, or a multi-line need's
record), and every column of :data:`CONFIGS` a project setting that shapes a generated
id. :data:`EXPECTED` is what each pair gave when the prediction was derived through
Sphinx-Needs' private ``_make_hashed_id``: moving the derivation to the public
``generate_need_id`` must not move a single id (#2407). One row moved since, on purpose:
a multi-line need's record with a declared ``full_title`` is predicted, as the record
path generates it, from its title (#2410); its twin through the one-line route keeps
the full title's hash.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_codelinks.sphinx_extension.directives.src_trace import would_be_id

LONG = (
    "A long title, well past the needs_max_title_length a project sets, "
    "so the directive would trim it"
)
UNICODE = "Prüfung der Größe — 測試 ß"

#: a need as ``render_needs`` passes it to :func:`would_be_id`
SHAPES: dict[str, dict[str, Any]] = {
    "title": {"type": "impl", "title": "Short"},
    "title_other_type": {"type": "req", "title": "Short"},
    "title_and_content": {"type": "impl", "title": "Titled", "content": "body text"},
    "long_title": {"type": "impl", "title": LONG},
    "long_full_title": {"type": "impl", "title": "Short", "full_title": LONG},
    "unicode_title": {"type": "impl", "title": UNICODE},
    "unicode_full_title": {"type": "impl", "title": "Short", "full_title": UNICODE},
    "no_title": {"type": "impl"},
    "empty_title_content": {"type": "impl", "title": "", "content": "body text"},
    "empty_title_unicode_content": {"type": "impl", "title": "", "content": UNICODE},
    "empty_title_no_content": {"type": "impl", "title": ""},
    # a ``None`` content is hashed as the text ``"None"``, as on master
    "empty_title_content_none": {"type": "impl", "title": "", "content": None},
    "empty_full_title_content": {
        "type": "impl",
        "title": "Titled",
        "full_title": "",
        "content": "body text",
    },
    "id_none": {"type": "impl", "title": "Short", "id": None},
    # a multi-line need's record with a declared ``full_title`` field, through the
    # record route (:data:`RECORDS`): hashed from the title (#2410) ...
    "record_declared_full_title": {
        "type": "req",
        "title": "Short title",
        "full_title": "A much longer title",
        "content": "The body.",
        "status": "open",
    },
    # ... whatever ``full_title`` it holds: with an empty title, from the content ...
    "record_declared_full_title_empty_title": {
        "type": "req",
        "title": "",
        "full_title": "A much longer title",
        "content": "The body.",
    },
    # ... and with an empty ``full_title``, from the title
    "record_declared_empty_full_title": {
        "type": "req",
        "title": "Short title",
        "full_title": "",
        "content": "The body.",
    },
    # ... and the same mapping as a one-line marker's: hashed from the full title (#2406)
    "marker_declared_full_title": {
        "type": "req",
        "title": "Short title",
        "full_title": "A much longer title",
        "content": "The body.",
        "status": "open",
    },
    # the sibling's own rules: a given id is the id; no id exists for a need
    # Sphinx-Needs refuses before generating one
    "given_id": {"type": "impl", "title": "Short", "id": "IMPL_GIVEN"},
    "given_empty_id": {"type": "impl", "title": "Short", "id": ""},
    "given_non_str_id": {"type": "impl", "title": "Short", "id": ["IMPL_X"]},
    "unknown_type": {"type": "nosuchtype", "title": "Short"},
    "no_type": {"title": "Short"},
}

#: the shapes that are a multi-line need's record, passed with ``route="record"``; every
#: other is a one-line marker's fields, passed as the default ``"marker"`` route
RECORDS = frozenset(
    {
        "record_declared_full_title",
        "record_declared_full_title_empty_title",
        "record_declared_empty_full_title",
    }
)

#: a project setting that shapes a generated id: its configuration overrides
CONFIGS: dict[str, dict[str, Any]] = {
    "default": {},
    "id_length_10": {"needs_id_length": 10},
    "id_from_title": {"needs_id_from_title": True, "needs_id_length": 40},
    "max_title_length": {"needs_max_title_length": 10},
    "declared_full_title": {"needs_fields": {"full_title": {"nullable": True}}},
    "id_required": {"needs_id_required": True},
}

#: every pair's id at ``c1562e058``, through ``_make_hashed_id``
EXPECTED: dict[str, dict[str, str | None]] = {
    "default": {
        "title": "I_0FE7D",
        "title_other_type": "R_0FE7D",
        "title_and_content": "I_9B65B",
        "long_title": "I_CAF23",
        "long_full_title": "I_CAF23",
        "unicode_title": "I_7D3A6",
        "unicode_full_title": "I_7D3A6",
        "no_title": "I_6EEF6",
        "empty_title_content": "I_8FE8C",
        "empty_title_unicode_content": "I_7D3A6",
        "empty_title_no_content": "I_DA39A",
        "empty_title_content_none": "I_6EEF6",
        "empty_full_title_content": "I_8FE8C",
        "id_none": "I_0FE7D",
        "record_declared_full_title": "R_D1C3C",
        "record_declared_full_title_empty_title": "R_66A3B",
        "record_declared_empty_full_title": "R_D1C3C",
        "marker_declared_full_title": "R_F2895",
        "given_id": "IMPL_GIVEN",
        "given_empty_id": None,
        "given_non_str_id": None,
        "unknown_type": None,
        "no_type": None,
    },
    "id_length_10": {
        "title": "I_0FE7D82F25",
        "title_other_type": "R_0FE7D82F25",
        "title_and_content": "I_9B65BAB658",
        "long_title": "I_CAF23D086D",
        "long_full_title": "I_CAF23D086D",
        "unicode_title": "I_7D3A62473F",
        "unicode_full_title": "I_7D3A62473F",
        "no_title": "I_6EEF664840",
        "empty_title_content": "I_8FE8C3D40E",
        "empty_title_unicode_content": "I_7D3A62473F",
        "empty_title_no_content": "I_DA39A3EE5E",
        "empty_title_content_none": "I_6EEF664840",
        "empty_full_title_content": "I_8FE8C3D40E",
        "id_none": "I_0FE7D82F25",
        "record_declared_full_title": "R_D1C3C0E37D",
        "record_declared_full_title_empty_title": "R_66A3B2458F",
        "record_declared_empty_full_title": "R_D1C3C0E37D",
        "marker_declared_full_title": "R_F28951319D",
        "given_id": "IMPL_GIVEN",
        "given_empty_id": None,
        "given_non_str_id": None,
        "unknown_type": None,
        "no_type": None,
    },
    "id_from_title": {
        "title": "I_SHORT_0FE7D82F25A3015040A206E54F9C1D3A97",
        "title_other_type": "R_SHORT_0FE7D82F25A3015040A206E54F9C1D3A97",
        "title_and_content": "I_TITLED_9B65BAB65820ABB6A6658EEC8FFDBF5AB",
        "long_title": "I_A_LONG_TITLE,_WELL_PAST_THE_NEEDS_MAX_TI",
        "long_full_title": "I_A_LONG_TITLE,_WELL_PAST_THE_NEEDS_MAX_TI",
        "unicode_title": "I_PRÜFUNG_DER_GRÖSSE_—_測試_SS_7D3A62473FC0B",
        "unicode_full_title": "I_PRÜFUNG_DER_GRÖSSE_—_測試_SS_7D3A62473FC0B",
        "no_title": "I_NONE_6EEF6648406C333A4035CD5E60D0BF2ECF2",
        "empty_title_content": "I__8FE8C3D40E967714951A71B824A0471440AA3D5",
        "empty_title_unicode_content": "I__7D3A62473FC0BE55A1E6258A36932FD0331141B",
        "empty_title_no_content": "I__DA39A3EE5E6B4B0D3255BFEF95601890AFD8070",
        "empty_title_content_none": "I__6EEF6648406C333A4035CD5E60D0BF2ECF2606D",
        "empty_full_title_content": "I__8FE8C3D40E967714951A71B824A0471440AA3D5",
        "id_none": "I_SHORT_0FE7D82F25A3015040A206E54F9C1D3A97",
        "record_declared_full_title": "R_SHORT_TITLE_D1C3C0E37D5B4504455812AFAC23",
        "record_declared_full_title_empty_title": "R__66A3B2458F6FFE6F68365FAD1103A9BEF14D534",
        "record_declared_empty_full_title": "R_SHORT_TITLE_D1C3C0E37D5B4504455812AFAC23",
        "marker_declared_full_title": "R_A_MUCH_LONGER_TITLE_F28951319D48DD2AD57B",
        "given_id": "IMPL_GIVEN",
        "given_empty_id": None,
        "given_non_str_id": None,
        "unknown_type": None,
        "no_type": None,
    },
    "max_title_length": {
        "title": "I_0FE7D",
        "title_other_type": "R_0FE7D",
        "title_and_content": "I_9B65B",
        "long_title": "I_CAF23",
        "long_full_title": "I_CAF23",
        "unicode_title": "I_7D3A6",
        "unicode_full_title": "I_7D3A6",
        "no_title": "I_6EEF6",
        "empty_title_content": "I_8FE8C",
        "empty_title_unicode_content": "I_7D3A6",
        "empty_title_no_content": "I_DA39A",
        "empty_title_content_none": "I_6EEF6",
        "empty_full_title_content": "I_8FE8C",
        "id_none": "I_0FE7D",
        "record_declared_full_title": "R_D1C3C",
        "record_declared_full_title_empty_title": "R_66A3B",
        "record_declared_empty_full_title": "R_D1C3C",
        "marker_declared_full_title": "R_F2895",
        "given_id": "IMPL_GIVEN",
        "given_empty_id": None,
        "given_non_str_id": None,
        "unknown_type": None,
        "no_type": None,
    },
    "declared_full_title": {
        "title": "I_0FE7D",
        "title_other_type": "R_0FE7D",
        "title_and_content": "I_9B65B",
        "long_title": "I_CAF23",
        "long_full_title": "I_CAF23",
        "unicode_title": "I_7D3A6",
        "unicode_full_title": "I_7D3A6",
        "no_title": "I_6EEF6",
        "empty_title_content": "I_8FE8C",
        "empty_title_unicode_content": "I_7D3A6",
        "empty_title_no_content": "I_DA39A",
        "empty_title_content_none": "I_6EEF6",
        "empty_full_title_content": "I_8FE8C",
        "id_none": "I_0FE7D",
        "record_declared_full_title": "R_D1C3C",
        "record_declared_full_title_empty_title": "R_66A3B",
        "record_declared_empty_full_title": "R_D1C3C",
        "marker_declared_full_title": "R_F2895",
        "given_id": "IMPL_GIVEN",
        "given_empty_id": None,
        "given_non_str_id": None,
        "unknown_type": None,
        "no_type": None,
    },
    "id_required": {
        "title": None,
        "title_other_type": None,
        "title_and_content": None,
        "long_title": None,
        "long_full_title": None,
        "unicode_title": None,
        "unicode_full_title": None,
        "no_title": None,
        "empty_title_content": None,
        "empty_title_unicode_content": None,
        "empty_title_no_content": None,
        "empty_title_content_none": None,
        "empty_full_title_content": None,
        "id_none": None,
        "record_declared_full_title": None,
        "record_declared_full_title_empty_title": None,
        "record_declared_empty_full_title": None,
        "marker_declared_full_title": None,
        "given_id": "IMPL_GIVEN",
        "given_empty_id": None,
        "given_non_str_id": None,
        "unknown_type": None,
        "no_type": None,
    },
}


def _app(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp], overrides: dict[str, Any]
) -> SphinxTestApp:
    src = tmp_path / "docs"
    src.mkdir()
    (src / "conf.py").write_text('extensions = ["sphinx_needs"]\n', encoding="utf-8")
    (src / "index.rst").write_text("Index\n=====\n", encoding="utf-8")
    return make_app(srcdir=src, confoverrides=overrides, freshenv=True)


@pytest.mark.parametrize("config", list(CONFIGS))
def test_would_be_id_is_pinned_for_every_shape(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp], config: str
) -> None:
    app = _app(tmp_path, make_app, CONFIGS[config])
    got = {
        name: would_be_id(app, need, route="record" if name in RECORDS else "marker")
        for name, need in SHAPES.items()
    }
    assert got == EXPECTED[config]
