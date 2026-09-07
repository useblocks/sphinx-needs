"""Materialising a Sphinx source directory for one test.

Two routes, and every suite in this workspace uses one of them: copy a checked-in project
into the session tempdir, or write a list of ``(path, text)`` pairs into a fresh one. Both
put the result under a random subdirectory so that parallel workers cannot collide.
"""

from __future__ import annotations

import secrets
import shutil
import string
from pathlib import Path


def generate_random_string() -> str:
    """
    Generate a random string of 10 characters consisting of letters (both uppercase and lowercase) and digits.

    :return: A random string.
    """
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for i in range(10))


def copy_srcdir_to_tmpdir(srcdir: Path, tmp: Path, *, relative_to: Path) -> Path:
    """
    Copy Source Directory to Temporary Directory.

    This function copies the contents of a source directory to a temporary
    directory. It generates a random subdirectory within the temporary directory
    to avoid conflicts and enable parallel processes to run without conflicts.

    :param srcdir: Path to the source directory.
    :param tmp: Path to the temporary directory.
    :param relative_to: What a relative ``srcdir`` is relative to -- the calling suite's
        own ``tests`` directory. It is passed rather than derived because this module no
        longer lives beside the projects it copies: it is shared by three suites, each
        with its own tree of them.

    :return: Path to the newly created directory in the temporary directory.
    """
    srcdir = relative_to.resolve() / srcdir
    tmproot = tmp.joinpath(generate_random_string()) / Path(srcdir).name
    shutil.copytree(srcdir, tmproot)
    return tmproot


def create_src_files_in_tmpdir(files: list[tuple[Path, str]], tmp: Path) -> Path:
    """Create source files in a temporary directory under the subdir src."""
    subdir = Path("src")
    tmproot = tmp.joinpath(generate_random_string()) / subdir
    tmproot.mkdir(exist_ok=True, parents=True)
    for file in files:
        file_path, content = file
        file_abs = tmproot.joinpath(str(file_path))
        file_abs.parent.mkdir(exist_ok=True)
        file_abs.write_text(content)
    return tmproot


def copy_test_utils(source: Path, destination: Path) -> None:
    """Copy a suite's ``tests/doc_test/utils`` into the session tempdir, if it is there.

    It no longer copies a jar, and for the suites in this repository it copies nothing:
    sphinx-needs' ``doc_test/utils`` held exactly one file -- a plantuml jar for that
    package alone -- and the workspace now carries one shared jar, committed at
    ``vendor/plantuml/`` at the version ``vendor/plantuml/pin.toml`` names, so the
    directory is gone and this call is a no-op. What remains is the GUARD, and it is the
    load-bearing half: ``copytree`` on a directory that is not there raises
    ``FileNotFoundError`` out of a session fixture every rendering test depends on, which
    would take out the suite before :func:`resolve_plantuml_command` -- the whole point of
    which is to let a tree with no jar be pointed at a PlantUML of its own -- was ever
    reached.

    It is kept rather than deleted because a fourth suite still has such a directory:
    sphinx-test-reports ships 12.9 MB under ``tests/doc_test/utils`` and copies it *per
    test function*; copying it once per session is the first thing this layer does for it.

    The destination is created only when there is something to put in it, so a caller
    that finds no ``<tempdir>/utils`` knows there was nothing to copy.

    :param source: The suite's own ``doc_test/utils`` directory.
    :param destination: Where it is copied to for this session.
    """
    if not source.is_dir():
        return
    destination.mkdir(exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)
