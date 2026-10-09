# @Test suite for source file discovery with gitignore support, TEST_DISC_1, test, [IMPL_DISC_1]
import json
import subprocess
from pathlib import Path

import pytest

from sphinx_codelinks.source_discover.config import (
    COMMENT_FILETYPE,
    SourceDiscoverConfig,
    SourceDiscoverConfigType,
)
from sphinx_codelinks.source_discover.source_discover import SourceDiscover

FIXTURES_PATH = Path(__file__).parent / "data" / "discover_fixtures.json"


def test_source_directory_is_worker_local(
    source_directory: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    assert source_directory.is_relative_to(tmp_path_factory.getbasetemp())
    assert (source_directory / "charge" / "demo_1.cpp").is_file()
    assert (source_directory / ".gitignore").read_text(
        encoding="utf-8"
    ) == "demo_1.cpp\n"


@pytest.mark.parametrize(
    ("config", "msgs"),
    [
        (
            {
                "src_dir": 123,
                "exclude": ["exclude1", "exclude2"],
                "include": ["include1", "include2"],
                "gitignore": True,
                "comment_type": "cpp",
            },
            ["Schema validation error in field 'src_dir': 123 is not of type 'string'"],
        ),
        (
            {
                "src_dir": "/path/to/root",
                "exclude": ["exclude1", "exclude2"],
                "include": ["include1", "include2"],
                "gitignore": "TrueAsString",
                "comment_type": "cpp",
            },
            [
                "Schema validation error in field 'gitignore': 'TrueAsString' is not of type 'boolean'"
            ],
        ),
        (
            {
                "src_dir": "/path/to/root",
                "exclude": ["exclude1", "exclude2"],
                "include": ["include1", "include2"],
                "gitignore": True,
                "comment_type": "java",
            },
            [
                "Schema validation error in field 'comment_type': 'java' is not one of ['bash', 'cpp', 'cs', 'go', 'jsonc', 'python', 'rust', 'ts', 'yaml']"
            ],
        ),
        (
            {
                "src_dir": "/path/to/root",
                "exclude": ["exclude1", "exclude2"],
                "include": ["include1", "include2"],
                "gitignore": True,
                "comment_type": ["cpp", "hpp"],
            },
            [
                "Schema validation error in field 'comment_type': ['cpp', 'hpp'] is not of type 'string'"
            ],
        ),
        (
            {
                "src_dir": "/path/to/root",
                "follow_links": "not_a_bool",
            },
            [
                "Schema validation error in field 'follow_links': 'not_a_bool' is not of type 'boolean'"
            ],
        ),
    ],
)
def test_schema_negative(config, msgs):
    source_discover_config = SourceDiscoverConfig(**config)
    errors = source_discover_config.check_schema()
    assert sorted(errors) == sorted(msgs)


@pytest.mark.parametrize(
    "config",
    [
        {},
        {
            "src_dir": "/path/to/root",
            "exclude": ["exclude1", "exclude2"],
            "include": ["include1", "include2"],
            "gitignore": True,
            "comment_type": "cpp",
        },
        {
            "src_dir": "/path/to/root",
            "exclude": ["exclude1", "exclude2"],
            "include": ["include1", "include2"],
            "gitignore": True,
            "comment_type": "python",
        },
        {
            "src_dir": "/path/to/root",
            "exclude": ["exclude1", "exclude2"],
            "include": ["include1", "include2"],
            "gitignore": True,
            "comment_type": "ts",
        },
        {
            "src_dir": "/path/to/root",
            "follow_links": True,
        },
    ],
)
def test_schema_positive(config):
    source_discover_config = SourceDiscoverConfig(**config)
    errors = source_discover_config.check_schema()
    assert len(errors) == 0


@pytest.mark.parametrize(
    ("config", "num_files", "suffix"),
    [
        (
            {
                "gitignore": False,
            },
            4,
            "",
        ),
        (
            {
                "gitignore": True,
            },
            3,
            "",
        ),
        (
            {
                "gitignore": True,
                "exclude": ["charge/*.cpp"],
                "include": ["**/*.cpp"],
            },
            # With ignore-python, include patterns whitelist files (overriding
            # gitignore) and exclude patterns are applied after, so both
            # charge/*.cpp files are excluded resulting in 2 instead of 4.
            2,
            "",
        ),
        (
            {
                "gitignore": True,
                "exclude": ["charge/*.cpp"],
            },
            2,
            "",
        ),
        (
            {"gitignore": False, "comment_type": "cpp"},
            4,
            "cpp",
        ),
    ],
)
def test_source_discover(
    config: SourceDiscoverConfigType,
    num_files: int,
    suffix: str,
    source_directory: Path,
) -> None:
    config["src_dir"] = source_directory
    src_discover_config = SourceDiscoverConfig(**config)
    source_discover = SourceDiscover(src_discover_config)
    assert len(source_discover.source_paths) == num_files
    if suffix:
        assert all(path.suffix == ".cpp" for path in source_discover.source_paths)


@pytest.fixture(scope="function")
def create_source_files(tmp_path: Path) -> Path:
    for file_types in COMMENT_FILETYPE.values():
        for ext in file_types:
            (tmp_path / f"file.{ext}").touch()
    return tmp_path


@pytest.mark.parametrize(
    ("comment_type", "nums_files"),
    [
        ("cpp", len(COMMENT_FILETYPE["cpp"])),
        ("python", len(COMMENT_FILETYPE["python"])),
        ("ts", len(COMMENT_FILETYPE["ts"])),
        ("bash", len(COMMENT_FILETYPE["bash"])),
    ],
)
def test_comment_filetype(
    comment_type: str, nums_files: int, create_source_files: Path
) -> None:
    src_dir = create_source_files

    config = SourceDiscoverConfig(
        src_dir=src_dir, comment_type=comment_type, gitignore=False
    )
    source_discover = SourceDiscover(config)
    assert len(source_discover.source_paths) == nums_files


def test_jsonc_discover_gate() -> None:
    """`.jsonc` is always discovered; `.json` only when it opens with a comment."""
    jsonc_dir = Path(__file__).parent / "data" / "jsonc"
    config = SourceDiscoverConfig(
        src_dir=jsonc_dir, comment_type="jsonc", gitignore=False
    )
    discovered = {p.name for p in SourceDiscover(config).source_paths}
    assert "demo.jsonc" in discovered
    assert "with_modeline.json" in discovered
    assert "plain.json" not in discovered


def _make_generated_output_tree(tmp_path: Path) -> Path:
    """Lay out a source file alongside checked-in generated output.

    Mirrors a ``tsc``/bundler output tree: ``src/app.ts`` is the real source,
    while ``dist/``, ``build/``, ``out/``, ``coverage/`` and ``node_modules/``
    stand in for generated or vendored output that carries the same marker;
    ``lib/app.js`` and the declaration file ``types/x.d.ts`` are not in the
    default and stay discovered.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.ts").write_text(
        "// @Feature A, IMPL_1, impl\n", encoding="utf-8"
    )
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "app.js").write_text(
        "// @Feature A, IMPL_1, impl\n", encoding="utf-8"
    )
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "app.js").write_text(
        "// @Feature A, IMPL_1, impl\n", encoding="utf-8"
    )
    for output in ("build", "out", "coverage"):
        (tmp_path / output).mkdir()
        (tmp_path / output / "app.js").write_text(
            "// @Feature A, IMPL_1, impl\n", encoding="utf-8"
        )
    (tmp_path / "types").mkdir()
    (tmp_path / "types" / "x.d.ts").write_text(
        "/** @Feature A, IMPL_1, impl */\nexport declare function a(): void;\n",
        encoding="utf-8",
    )
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text(
        "// vendored\n", encoding="utf-8"
    )
    return tmp_path


def test_default_exclude_skips_generated_output(tmp_path: Path) -> None:
    """The ``ts``-derived default ``exclude`` keeps generated/vendored JS out
    of discovery, while ``lib/`` — deliberately not in ``TS_DEFAULT_EXCLUDE``
    — is still discovered (see the constant's docstring for why)."""
    src_dir = _make_generated_output_tree(tmp_path)
    config = SourceDiscoverConfig(src_dir=src_dir, comment_type="ts", gitignore=False)

    discover = SourceDiscover(config)
    discovered = sorted(str(p.relative_to(src_dir)) for p in discover.source_paths)
    assert discovered == [
        str(Path("lib") / "app.js"),
        str(Path("src") / "app.ts"),
        str(Path("types") / "x.d.ts"),
    ]


def test_cpp_project_default_exclude_is_empty_and_finds_lib_marker(
    tmp_path: Path,
) -> None:
    """The ``ts`` default ``exclude`` is ``ts``'s alone: a ``cpp`` project's is ``[]``, and
    its hand-written ``lib/`` source is discovered."""
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "widget.cpp").write_text(
        "// @Feature A, IMPL_1, impl\n", encoding="utf-8"
    )

    config = SourceDiscoverConfig(src_dir=tmp_path, comment_type="cpp", gitignore=False)
    assert config.exclude == []

    discover = SourceDiscover(config)
    discovered = sorted(str(p.relative_to(tmp_path)) for p in discover.source_paths)
    assert discovered == [str(Path("lib") / "widget.cpp")]


def test_explicit_exclude_replaces_default(tmp_path: Path) -> None:
    """An explicit ``exclude`` (even ``[]``) fully replaces the default list."""
    src_dir = _make_generated_output_tree(tmp_path)
    config = SourceDiscoverConfig(
        src_dir=src_dir, comment_type="ts", gitignore=False, exclude=[]
    )
    assert config.exclude == []

    discover = SourceDiscover(config)
    discovered = sorted(str(p.relative_to(src_dir)) for p in discover.source_paths)
    assert discovered == [
        str(Path("build") / "app.js"),
        str(Path("coverage") / "app.js"),
        str(Path("dist") / "app.js"),
        str(Path("lib") / "app.js"),
        str(Path("node_modules") / "pkg" / "index.js"),
        str(Path("out") / "app.js"),
        str(Path("src") / "app.ts"),
        str(Path("types") / "x.d.ts"),
    ]


def test_follow_links(tmp_path: Path) -> None:
    """Test that follow_links controls whether symbolic links are followed."""
    # Create a project directory with a real directory the walk excludes, holding a
    # source file: inside the project, since a file outside it is never discovered
    # (#2062, ``test_a_link_to_outside_the_root_is_not_listed``)
    project_dir = tmp_path / "project"
    real_dir = project_dir / "real"
    real_dir.mkdir(parents=True)
    (real_dir / "source.cpp").write_text("// test")
    (project_dir / "direct.cpp").write_text("// direct")
    # and a symlink to the real directory
    link = project_dir / "linked"
    link.symlink_to(real_dir)

    # Without follow_links, symlinked files should not be discovered
    config_no_follow = SourceDiscoverConfig(
        src_dir=project_dir, gitignore=False, exclude=["real/**"], follow_links=False
    )
    discover_no_follow = SourceDiscover(config_no_follow)
    discovered_names = {p.name for p in discover_no_follow.source_paths}
    assert "direct.cpp" in discovered_names
    assert "source.cpp" not in discovered_names

    # With follow_links, symlinked files should be discovered
    config_follow = SourceDiscoverConfig(
        src_dir=project_dir, gitignore=False, exclude=["real/**"], follow_links=True
    )
    discover_follow = SourceDiscover(config_follow)
    discovered_names = {p.name for p in discover_follow.source_paths}
    assert "direct.cpp" in discovered_names
    assert "source.cpp" in discovered_names


def _load_discover_fixtures() -> list[dict]:
    with FIXTURES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "case",
    _load_discover_fixtures(),
    ids=lambda c: c["name"],
)
def test_discover_fixture(case: dict, tmp_path: Path) -> None:
    """Run portable discovery test cases from the shared JSON fixture."""
    # Create files
    for rel_path, content in case["files"].items():
        file_path = tmp_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    # Optionally initialise a git repo (required for .gitignore support)
    if case.get("git_init", False):
        subprocess.run(
            ["git", "init"],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )

    cfg = case["config"]
    src_dir = tmp_path / cfg["src_dir"]

    config = SourceDiscoverConfig(
        src_dir=src_dir,
        include=cfg.get("include", []),
        exclude=cfg.get("exclude", []),
        gitignore=cfg.get("gitignore", True),
        comment_type=cfg.get("comment_type", "cpp"),
    )

    discover = SourceDiscover(config)

    # Convert discovered paths to paths relative to tmp_path for comparison
    discovered_relative = sorted(
        str(p.relative_to(tmp_path)) for p in discover.source_paths
    )

    # Normalise expected paths to use the OS path separator
    expected = sorted(str(Path(p)) for p in case["expected"])

    assert discovered_relative == expected, (
        f"Case '{case['name']}': expected {expected}, got {discovered_relative}"
    )


def _links_tree(tmp_path: Path) -> Path:
    """``root/{a.cpp, sub/b.cpp}`` with four links: a file and a directory link inside
    the root (``b_link.cpp`` -> ``sub/b.cpp``, ``dirlink_in`` -> ``sub``), and a file
    and a directory link to outside it (``ext_link.cpp`` -> ``outside/ext.cpp``,
    ``dirlink_out`` -> ``outside/odir``). Returns the root."""
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (tmp_path / "outside" / "odir").mkdir(parents=True)
    (root / "a.cpp").write_text("// a\n", encoding="utf-8")
    (root / "sub" / "b.cpp").write_text("// b\n", encoding="utf-8")
    (tmp_path / "outside" / "ext.cpp").write_text("// ext\n", encoding="utf-8")
    (tmp_path / "outside" / "odir" / "o.cpp").write_text("// o\n", encoding="utf-8")
    (root / "b_link.cpp").symlink_to(root / "sub" / "b.cpp")
    (root / "dirlink_in").symlink_to(root / "sub", target_is_directory=True)
    (root / "ext_link.cpp").symlink_to(tmp_path / "outside" / "ext.cpp")
    (root / "dirlink_out").symlink_to(
        tmp_path / "outside" / "odir", target_is_directory=True
    )
    return root


def _listing(root: Path, *, follow_links: bool) -> list[str]:
    """What discovery lists under ``root``, POSIX and relative to ``root``'s parent
    (``root.parent`` resolved: the listing is of canonical paths)."""
    config = SourceDiscoverConfig(
        src_dir=root, gitignore=False, follow_links=follow_links
    )
    base = root.parent.resolve()
    return [
        path.relative_to(base).as_posix()
        for path in SourceDiscover(config).source_paths
    ]


def test_a_file_link_inside_the_root_is_listed_once(tmp_path: Path) -> None:
    """``b_link.cpp`` is ``sub/b.cpp``: one entry, the target's, not one per path to it.

    A symlinked file is listed even with ``follow_links = false`` (``is_file()``
    follows the link) -- ubCode skips it; a parity gap kept as it is. A link to a file
    OUTSIDE the root is not listed (#2062).
    """
    assert _listing(_links_tree(tmp_path), follow_links=False) == [
        "root/a.cpp",
        "root/sub/b.cpp",
    ]


def test_a_followed_directory_link_inside_the_root_lists_each_file_once(
    tmp_path: Path,
) -> None:
    """With ``follow_links = true`` ``sub/b.cpp`` is reached three ways (``sub/``,
    ``b_link.cpp`` and ``dirlink_in/``): still one entry. The followed link to outside
    the root lists nothing (#2062)."""
    assert _listing(_links_tree(tmp_path), follow_links=True) == [
        "root/a.cpp",
        "root/sub/b.cpp",
    ]


def test_a_link_free_listing_is_sorted_by_full_path(tmp_path: Path) -> None:
    """Without links nothing is deduplicated, and the order is the full path's: ``-``
    and ``.`` sort before the separator, ``_`` after it (on POSIX and on Windows)."""
    root = tmp_path / "root"
    for relative in [
        "b.cpp",
        "sub_x.cpp",
        "z/y/x.cpp",
        "sub/c.cpp",
        "a.cpp",
        "sub.cpp",
        "sub-x/d.cpp",
    ]:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("// x\n", encoding="utf-8")

    assert _listing(root, follow_links=False) == [
        "root/a.cpp",
        "root/b.cpp",
        "root/sub-x/d.cpp",
        "root/sub.cpp",
        "root/sub/c.cpp",
        "root/sub_x.cpp",
        "root/z/y/x.cpp",
    ]
    assert _listing(root, follow_links=True) == _listing(root, follow_links=False)


@pytest.mark.parametrize("follow_links", [False, True])
def test_a_link_to_outside_the_root_is_not_listed(
    tmp_path: Path, follow_links: bool
) -> None:
    """Neither a file link to outside the root nor a followed directory link's files
    are listed, either way (#2062): every record and copy is relative to the root."""
    listing = _listing(_links_tree(tmp_path), follow_links=follow_links)
    assert not any(path.startswith("outside/") for path in listing)
    assert not any("link" in path for path in listing)
