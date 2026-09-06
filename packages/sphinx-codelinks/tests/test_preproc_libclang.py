from pathlib import Path

import pytest

clang = pytest.importorskip("clang.cindex")

from sphinx_codelinks.analyse.preproc import libclang_parser, loader


def test_load_clang_cindex_returns_module():
    mod = loader.load_clang_cindex()
    assert hasattr(mod, "Index")


def test_parse_options_is_combination():
    # INCOMPLETE | SKIP_FUNCTION_BODIES | DETAILED_PROCESSING_RECORD
    import clang.cindex as cx

    expected = (
        cx.TranslationUnit.PARSE_INCOMPLETE
        | cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
        | cx.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
    )
    assert loader.PARSE_OPTIONS == expected


def test_skipped_ranges_on_simple_ifdef(tmp_path: Path):
    import clang.cindex as cx

    src = tmp_path / "s.cpp"
    src.write_text("#ifdef OFF\n// inactive\n#endif\n// active\n")
    idx = cx.Index.create()
    tu = idx.parse(str(src), args=["-std=c++17"], options=loader.PARSE_OPTIONS)
    skipped = loader.get_all_skipped_ranges(tu)
    # The #ifdef OFF block is skipped; its range covers line 2.
    assert any(
        sr.start_line <= 2 <= sr.end_line and sr.file == Path(str(src))
        for sr in skipped
    )


FIXTURE = Path(__file__).parent / "data" / "preproc" / "variants_branching.cpp"


def _titles(comments):
    out = []
    for c in comments:
        text = c.text.decode("utf-8")
        if "@" in text:
            out.append(text)
    return out


def test_extract_active_comments_variant_a_active():
    args = [
        "-std=c++17",
        "-DVARIANT_A=1",
        "-DPLATFORM_LINUX=1",
        "-DPROTOCOL_VERSION=3",
    ]
    comments = libclang_parser.extract_active_comments(FIXTURE, args)
    titles = _titles(comments)
    joined = "\n".join(titles)
    assert "IMPL_ALWAYS" in joined
    assert "IMPL_VAR_A" in joined  # active branch
    assert "IMPL_VAR_B" not in joined  # inactive #else -> EXCLUDED
    assert "IMPL_PROTO_3" in joined  # PROTOCOL_VERSION >= 3 active
    assert "IMPL_LINUX_A" in joined  # both defined


def test_extract_active_comments_variant_b_active():
    args = ["-std=c++17", "-DPROTOCOL_VERSION=1"]  # VARIANT_A undefined
    comments = libclang_parser.extract_active_comments(FIXTURE, args)
    joined = "\n".join(_titles(comments))
    assert "IMPL_VAR_B" in joined  # #else branch now active
    assert "IMPL_VAR_A" not in joined  # inactive -> EXCLUDED
    assert "IMPL_PROTO_3" not in joined  # version < 3 -> EXCLUDED
    assert "IMPL_LINUX_A" not in joined  # VARIANT_A undefined -> EXCLUDED


def test_extract_active_comments_normalizes_crlf(tmp_path: Path):
    """A block comment from a CRLF-saved source must not carry embedded CR into
    the extracted text (it would corrupt e.g. multi-line reST-block content),
    the tree-sitter path's CRLF->LF normalization."""
    src = tmp_path / "crlf.cpp"
    src.write_bytes(b"/* line1\r\n@rst\r\nbody\r\n@endrst\r\n*/\r\nint x = 0;\r\n")
    comments = libclang_parser.extract_active_comments(src, ["-x", "c++", "-std=c++17"])
    assert comments, "expected the block comment to be extracted"
    for c in comments:
        assert b"\r" not in c.text, f"CR leaked into extracted comment: {c.text!r}"


def test_extract_active_comments_tolerates_non_utf8(tmp_path: Path):
    """A non-UTF-8 byte (past is_text_file's 2 KB sample) must not raise
    UnicodeDecodeError and abort the whole run; the marker must still extract."""
    src = tmp_path / "latin1.cpp"
    src.write_bytes(
        b'// @Marker, IMPL_LATIN1, impl, [REQ]\nconst char* s = "caf\xe9";\n'
    )
    comments = libclang_parser.extract_active_comments(src, ["-x", "c++", "-std=c++17"])
    assert comments, "non-UTF-8 source must still yield comments, not raise"


def test_extract_active_comments_tolerates_non_utf8_inside_comment(tmp_path: Path):
    """A non-UTF-8 byte INSIDE a comment must not raise UnicodeDecodeError.

    ``tok.spelling`` decodes the comment token as strict UTF-8 and raises on the
    0xE9 byte; slicing the text from the raw source bytes and decoding lossily
    keeps the (ASCII) marker id intact.
    """
    src = tmp_path / "latin1_comment.cpp"
    # 0xE9 (Latin-1 'é') lives in the marker comment's title, not the code.
    src.write_bytes(b"// @Caf\xe9 need, IMPL_CMT, impl, [REQ]\nint x;\n")
    comments = libclang_parser.extract_active_comments(src, ["-x", "c++", "-std=c++17"])
    assert comments, "a non-UTF-8 byte in a comment must not drop the comment"
    joined = b" ".join(c.text for c in comments)
    assert b"IMPL_CMT" in joined, f"marker id lost: {joined!r}"
