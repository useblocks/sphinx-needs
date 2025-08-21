import json
from pathlib import Path

from docutils.nodes import document
import pytest
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

from sphinx_codelinks.config import OneLineCommentStyle

pytest_plugins = "sphinx.testing.fixtures"

TEST_DIR = Path(__file__).parent
DATA_DIR = TEST_DIR / "data"
SRC_TRACE_TOML = TEST_DIR / "data" / "sphinx" / "src_trace.toml"
RECURSIVE_DIR_analyse_TOML = TEST_DIR / "doc_test" / "recursive_dirs" / "src_trace.toml"
ONELINE_COMMENT_STYLE = OneLineCommentStyle(
    start_sequence="[[",
    end_sequence="]]",
    field_split_char=",",
    needs_fields=[
        {"name": "id"},
        {"name": "title"},
        {"name": "type", "default": "impl"},
        {"name": "links", "type": "list[str]", "default": []},
        {"name": "status", "default": "open"},
        {"name": "priority", "default": "low"},
    ],
)

ONELINE_COMMENT_STYLE_DEFAULT = OneLineCommentStyle()


@pytest.fixture(scope="session")
def source_directory() -> Path:
    tests_dir = Path(__file__).parent
    source_directory = tests_dir / "data" / "dcdc"
    return source_directory


@pytest.fixture(scope="session")
def source_paths(source_directory: Path) -> list[Path]:
    source_paths = [
        source_directory / "charge" / "demo_1.cpp",
        source_directory / "charge" / "demo_2.cpp",
        source_directory / "discharge" / "demo_3.cpp",
        source_directory / "supercharge.cpp",
    ]
    return source_paths


@pytest.fixture(scope="session", autouse=True)
def temporary_gitignore(source_directory: Path):
    gitignore_path = source_directory / ".gitignore"
    gitignore_path.write_text("demo_1.cpp\n", encoding="utf-8")
    yield
    gitignore_path.unlink()


class DoctreeSnapshotExtension(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    _file_extension = "doctree.xml"

    def serialize(self, data, **_kwargs):
        if not isinstance(data, document):
            raise TypeError(f"Expected document, got {type(data)}")
        doc = data.deepcopy()
        doc["source"] = "<source>"  # this will be a temp path
        doc.attributes.pop("translation_progress", None)  # added in sphinx 7.1
        return doc.pformat()


@pytest.fixture
def snapshot_doctree(snapshot):
    """Snapshot fixture for doctrees.

    Here we try to sanitize the doctree, to make the snapshots reproducible.
    """
    try:
        return snapshot.with_defaults(extension_class=DoctreeSnapshotExtension)
    except AttributeError:
        # fallback for older versions of pytest-snapshot
        return snapshot.use_extension(DoctreeSnapshotExtension)


class AnchorsSnapshotExtension(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    _file_extension = "anchors.json"

    def serialize(self, data, **_kwargs):
        if not isinstance(data, list):
            raise TypeError(f"Expected list, got {type(data)}")
        anchors = data

        return json.dumps(anchors, indent=2)


@pytest.fixture
def snapshot_marks(snapshot):
    """Snapshot fixture for reqif.

    Sanitize the reqif, to make the snapshots reproducible.
    """
    return snapshot.with_defaults(extension_class=AnchorsSnapshotExtension)
