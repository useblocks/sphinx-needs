import json
import shutil
import subprocess
from pathlib import Path

import pytest
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

from sphinx_codelinks.config import OneLineCommentStyle

# The workspace's shared test layer, `packages/sphinx-needs-testkit`, which carries the
# doctree snapshot extension this file used to hold a byte-for-byte copy of -- and, imported
# by name in the test modules rather than through this line, the warning normalisation the
# suite's build assertions go through. A line that resolves to nothing is a collection
# ERROR, not a silent loss of fixtures, which is what makes this the fence that the kit is
# importable in every cell this suite runs in.
# The order matters where both plugins define a fixture -- see the note in the testkit's
# `fixtures` module -- so the testkit always comes last.
#
# This suite also INHERITS the kit's `test_app`, its `sphinx_test_tempdir` and the
# `--sn-build-dir` option, and uses none of them: it builds through sphinx's `make_app`,
# which does not depend on `sphinx_test_tempdir`. So they are inert here -- and the day a
# test here uses sphinx's `app` fixture instead, it will need a `tests_dir` fixture in this
# file, which the kit deliberately leaves to each suite. That arrives as
# `fixture 'tests_dir' not found`, which is loud rather than wrong.
pytest_plugins = ["sphinx.testing.fixtures", "sphinx_needs_testkit.fixtures"]

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
def source_directory(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A worker-local copy of ``tests/data/dcdc``: a git repository whose ``.gitignore``
    hides ``demo_1.cpp``.

    The copy lives under pytest's base temp directory -- one per xdist worker -- so no test
    writes into the checkout and no worker can remove another's ``.gitignore``. The
    ``git init`` is load-bearing: the ``ignore`` crate discovery walks with honours a
    ``.gitignore`` only inside a repository, so without it the ``--gitignore`` cases see all
    four files.
    """
    source_directory = tmp_path_factory.mktemp("dcdc")
    shutil.copytree(TEST_DIR / "data" / "dcdc", source_directory, dirs_exist_ok=True)
    subprocess.run(["git", "init", "--quiet"], cwd=source_directory, check=True)
    (source_directory / ".gitignore").write_text("demo_1.cpp\n", encoding="utf-8")
    return source_directory


# `DoctreeSnapshotExtension` and `snapshot_doctree` are NOT here any more: they were a
# byte-for-byte copy of sphinx-needs' pair (one character apart), and both now come from
# the plugin above. The two below stay -- they serialise this package's own data
# structures, and a snapshot extension with one consumer is that suite's code.


class AnchorsSnapshotExtension(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    file_extension = "anchors.json"

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


class ExtractionSnapshotExtension(SingleFileSnapshotExtension):
    """Single-file JSON snapshots for the declarative extraction tests."""

    _write_mode = WriteMode.TEXT
    file_extension = "json"

    def serialize(self, data, **_kwargs):
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict, got {type(data)}")
        return json.dumps(data, indent=2)


@pytest.fixture
def snapshot_extraction(snapshot):
    """Snapshot fixture for the normalized extraction output (one JSON per case)."""
    return snapshot.with_defaults(extension_class=ExtractionSnapshotExtension)
