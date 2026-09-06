"""`fetch_plantuml.py`: what it downloads, what it refuses, and what it never downloads.

Every rendering task in this workspace depends on this script, so its contract is the thing
that decides whether a fresh clone can render at all. Four parts of it are load-bearing and
none of them is visible from a green test run elsewhere:

* a cached jar is **re-hashed**, so a truncated download is caught here rather than inside a
  render minutes later -- and re-fetched rather than refused, because an interrupted download
  is the likely cause and the pin is still the authority;
* a checksum mismatch on a fresh download is **refused**, with both hashes named and nothing
  written. That is the entire point of pinning;
* `PLANTUML_JAR` short-circuits the whole thing, so a machine that has already made an
  explicit choice never pays for a 30 MB download it will not use -- including when the
  network is down, which is exactly when that machine most needs the run to work;
* the failure messages name the two routes that need no network.

Nothing here reaches the network: `urllib.request.urlopen` is monkeypatched, the way the rest
of `tools/tests` monkeypatches PyPI and git. A fence that needed the network to be tested
would not be run often enough to be a fence.
"""

from __future__ import annotations

import hashlib
import io
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from sn_tools import fetch_plantuml

pytestmark = pytest.mark.filterwarnings("error")

PAYLOAD = b"not really a jar, but it hashes like one"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
VERSION = "1.2026.8"

PIN = """\
version = "{version}"
sha256 = "{sha256}"
url = "https://example.invalid/plantuml/v{{version}}/plantuml-{{version}}.jar"
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A checkout-shaped directory carrying a pin and no jar."""
    vendor = tmp_path / "vendor" / "plantuml"
    vendor.mkdir(parents=True)
    (vendor / "pin.toml").write_text(
        PIN.format(version=VERSION, sha256=DIGEST), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture(autouse=True)
def _no_inherited_jar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every case from an unset `PLANTUML_JAR`.

    CI sets it for the sphinx-mounts cells and the release workflow's build job, and a
    developer may well have it exported, so a case that means "unset" has to say so.
    """
    monkeypatch.delenv("PLANTUML_JAR", raising=False)


@pytest.fixture
def urlopen(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve `PAYLOAD` for any URL, and record every URL asked for.

    The returned list is the assertion "nothing was downloaded" is made against: a script
    whose whole purpose is to avoid a 30 MB transfer has to be tested on the transfer it did
    NOT make, and an exit code cannot show that.
    """
    asked: list[str] = []

    def fake(url: str) -> io.BytesIO:
        asked.append(url)
        return io.BytesIO(PAYLOAD)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return asked


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every download fails, the way a sandbox or a broken connection makes it fail."""
    asked: list[str] = []

    def fake(url: str) -> io.BytesIO:
        asked.append(url)
        raise urllib.error.URLError("nodename nor servname provided")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return asked


def run(root: Path, *args: str) -> int:
    return fetch_plantuml.main([*args, "--root", str(root)])


def jar_of(root: Path) -> Path:
    return root / "vendor" / "plantuml" / f"plantuml-{VERSION}.jar"


def test_downloads_and_verifies(root: Path, urlopen: list[str], capsys) -> None:
    """The ordinary first run: fetch, check the hash, put it in place, print the path."""
    assert run(root) == 0

    assert urlopen == [
        f"https://example.invalid/plantuml/v{VERSION}/plantuml-{VERSION}.jar"
    ]
    assert jar_of(root).read_bytes() == PAYLOAD
    assert capsys.readouterr().out.strip() == str(jar_of(root))
    # nothing half-written is left behind for the next run to trip over
    assert sorted(p.name for p in (root / "vendor" / "plantuml").iterdir()) == [
        "pin.toml",
        f"plantuml-{VERSION}.jar",
    ]


def test_a_cached_jar_is_not_fetched_again(
    root: Path, urlopen: list[str], capsys
) -> None:
    """A jar already there and matching the pin costs one hash and no network."""
    jar_of(root).write_bytes(PAYLOAD)

    assert run(root) == 0

    assert urlopen == []
    assert capsys.readouterr().out.strip() == str(jar_of(root))


def test_a_corrupt_cached_jar_is_fetched_again(
    root: Path, urlopen: list[str], capsys
) -> None:
    """A cached jar whose hash does not match is replaced, not trusted and not refused.

    An interrupted download is the likely cause -- and it is the failure mode that would
    otherwise surface as a broken render, far from the file that caused it.
    """
    jar_of(root).write_bytes(b"truncated")

    assert run(root) == 0

    assert len(urlopen) == 1
    assert jar_of(root).read_bytes() == PAYLOAD
    assert "does not match the pin" in capsys.readouterr().err


def test_a_checksum_mismatch_is_refused(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A download that is not what the pin names writes nothing and names both hashes."""
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda url: io.BytesIO(b"something else entirely")
    )

    assert run(root) == 1

    err = capsys.readouterr().err
    assert DIGEST in err
    assert hashlib.sha256(b"something else entirely").hexdigest() in err
    assert not jar_of(root).exists()
    # and no `.part` file survives either
    assert [p.name for p in (root / "vendor" / "plantuml").iterdir()] == ["pin.toml"]


def test_a_network_failure_names_the_alternatives(
    root: Path, offline: list[str], capsys
) -> None:
    """Offline, with no jar and no `PLANTUML_JAR`: red, and it says what to do instead."""
    assert run(root) == 1

    err = capsys.readouterr().err
    assert offline  # it really did try
    assert "PLANTUML_JAR" in err
    assert "install a `plantuml` executable" in err
    assert not jar_of(root).exists()


def test_plantuml_jar_short_circuits_even_offline(
    root: Path,
    offline: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    """An explicit choice is never blocked by a fetch it does not need.

    This is the case that makes `deps = ["fetch-plantuml"]` safe to put on every rendering
    task: a machine with `PLANTUML_JAR` exported and no network still runs its tests.
    """
    named = tmp_path / "elsewhere" / "plantuml.jar"
    named.parent.mkdir()
    named.write_bytes(b"a jar of the caller's own")
    monkeypatch.setenv("PLANTUML_JAR", str(named))

    assert run(root) == 0

    captured = capsys.readouterr()
    assert offline == []  # not even attempted
    assert captured.out.strip() == str(named)
    assert "fetching nothing" in captured.err
    assert not jar_of(root).exists()


def test_an_empty_plantuml_jar_is_treated_as_unset(
    root: Path, urlopen: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty `PLANTUML_JAR` means "no jar", not "a jar named nothing".

    That is how the variable arrives from a shell with `PLANTUML_JAR=` exported and from a
    workflow that computes the value with an expression; both suites that read it agree, and
    each pins it on its own side.
    """
    monkeypatch.setenv("PLANTUML_JAR", "")

    assert run(root) == 0
    assert len(urlopen) == 1


def test_a_plantuml_jar_naming_no_file_is_reported_and_ignored(
    root: Path,
    urlopen: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    """A mistyped `PLANTUML_JAR` does not block the fetch, but it is said out loud.

    The consumers fail loudly on it -- `tests/conftest.py`'s chain refuses to fall through a
    variable that names no file -- so this script's job is to leave the machine able to run,
    with the mistake visible in the log above the failure that names it.
    """
    monkeypatch.setenv("PLANTUML_JAR", str(tmp_path / "gone.jar"))

    assert run(root) == 0

    assert len(urlopen) == 1
    assert "is not a file" in capsys.readouterr().err


def test_print_path_fetches_nothing(root: Path, urlopen: list[str], capsys) -> None:
    """`--print-path` answers "where does this workspace keep its jar" and stops."""
    assert run(root, "--print-path") == 0

    assert urlopen == []
    assert capsys.readouterr().out.strip() == str(jar_of(root))
    assert not jar_of(root).exists()


def test_print_path_ignores_plantuml_jar(
    root: Path,
    urlopen: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    """It is a question about the checkout, so the environment does not answer it."""
    named = tmp_path / "elsewhere.jar"
    named.write_bytes(b"a jar of the caller's own")
    monkeypatch.setenv("PLANTUML_JAR", str(named))

    assert run(root, "--print-path") == 0

    assert capsys.readouterr().out.strip() == str(jar_of(root))


def test_a_missing_pin_is_named(tmp_path: Path) -> None:
    """No pin file is a mistake about the tree, not a fetch failure."""
    with pytest.raises(SystemExit) as caught:
        run(tmp_path)

    assert "no pin file at" in str(caught.value)


def test_an_incomplete_pin_is_named(root: Path) -> None:
    """A pin missing a key says which -- a bump that edits one line and not the other."""
    (root / "vendor" / "plantuml" / "pin.toml").write_text(
        'version = "1.2026.8"\n', encoding="utf-8"
    )

    with pytest.raises(SystemExit) as caught:
        run(root)

    assert "missing sha256, url" in str(caught.value)
