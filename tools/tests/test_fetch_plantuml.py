"""`fetch_plantuml.py`: the fence, what it downloads, what it refuses, and what it never downloads.

The jar is committed, so the load-bearing half of this script is `--verify`: CI's Lint job and
`uv run poe lint` run it, and it is the only thing standing between a bumped `pin.toml` and a
repository whose pin and jar disagree. Its contract is short and every clause of it is tested
below -- above all that **it never reaches the network**, which is asserted by making the
network raise rather than by trusting the code path.

The download half is the bump step, and its own contract decides whether a bump lands clean.
Five parts of it are load-bearing and none of them is visible from a green test run elsewhere:

* a cached jar is **re-hashed**, so a truncated download is caught here rather than inside a
  render minutes later -- and re-fetched rather than refused, because an interrupted download
  is the likely cause and the pin is still the authority;
* a checksum mismatch on a fresh download is **refused**, with both hashes named and nothing
  written. That is the entire point of pinning;
* `PLANTUML_JAR` short-circuits the whole thing, so a machine that has already made an
  explicit choice never pays for a 30 MB download it will not use -- including when the
  network is down, which is exactly when that machine most needs the run to work; and a value
  that names NO file stops the run here rather than being fetched around, because every
  consumer refuses that same value seconds later;
* a 404 is reported as a pin error, not as a network failure: the network worked, and the
  offline alternatives are not the answer to an asset that was never published;
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


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any use of the network is an error.

    `--verify` runs in CI's Lint job, on an offline developer's `uv run poe lint`, and in
    every sandbox whose allowlist this repository does not control -- so "it did not download"
    is part of its contract rather than an implementation detail, and the way to test a
    contract like that is to make the forbidden thing explode. A `--verify` that fell through
    to the fetch would raise `AssertionError` here instead of quietly passing.
    """

    def fake(url: str) -> None:
        raise AssertionError("network")

    monkeypatch.setattr(urllib.request, "urlopen", fake)


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


def test_a_plantuml_jar_naming_no_file_stops_the_run(
    root: Path,
    urlopen: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A mistyped `PLANTUML_JAR` is refused here, with the message its consumers give.

    Fetching around it would be worse than useless: `tests/conftest.py`, `docs/conf.py` and
    `performance_test.py` all raise on that same value, so the 30 MB would never be used and
    the note saying it was ignored would sit directly above the failure it caused. In CI,
    where this runs inside ``jar="$( … )"``, this is one red step naming the variable instead
    of a green step followed by every rendering test erroring.
    """
    missing = tmp_path / "gone.jar"
    monkeypatch.setenv("PLANTUML_JAR", str(missing))

    with pytest.raises(SystemExit) as caught:
        run(root)

    message = str(caught.value)
    assert repr(str(missing)) in message
    assert "is not a file" in message
    assert "Point it at a plantuml jar" in message
    # the ALTERNATIVE the message offers, asserted literally rather than as "unset it":
    # under this design the checkout puts the jar there and `--verify` fetches nothing, so a
    # message promising that `poe fetch-plantuml` "puts" it there described an action this
    # branch cannot take. The same clause is in `tests/conftest.py`, `docs/conf.py` and
    # `performance_test.py`, word for word -- `tests/test_plantuml_command.py` pins it there
    assert "unset it to render with the jar committed at vendor/plantuml/." in message
    assert urlopen == []  # and nothing was downloaded
    assert not jar_of(root).exists()


def test_a_404_is_reported_as_a_pin_error(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A missing asset is a mistake in `pin.toml`, not a connectivity problem.

    The offline alternatives are the wrong advice for it -- the network worked, and it said
    the file is not there -- so this case names the pin instead. A version that was never
    released gets here, and so does a release whose asset is named differently (before
    ~v1.2025.0 upstream ships only `plantuml-<version>.jar`, never a plain `plantuml.jar`).
    """

    def fake(url: str) -> io.BytesIO:
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", fake)

    assert run(root) == 1

    err = capsys.readouterr().err
    assert "HTTP 404" in err
    assert "vendor/plantuml/pin.toml" in err
    assert "Alternatives that need no download" not in err
    assert not jar_of(root).exists()
    # and no `.part` file survived
    assert [p.name for p in (root / "vendor" / "plantuml").iterdir()] == ["pin.toml"]


def test_any_other_http_error_keeps_the_offline_advice(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A 503 is not a pin error: the pin may be perfect and the server merely unwell."""

    def fake(url: str) -> io.BytesIO:
        raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", fake)

    assert run(root) == 1

    err = capsys.readouterr().err
    assert "503" in err
    assert "Alternatives that need no download" in err


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


def test_verify_accepts_the_committed_jar(root: Path, no_network: None, capsys) -> None:
    """The ordinary case: the jar is there, it hashes to the pin, its path goes to stdout."""
    jar_of(root).write_bytes(PAYLOAD)

    assert run(root, "--verify") == 0

    assert capsys.readouterr().out.strip() == str(jar_of(root))


def test_verify_refuses_a_missing_jar(root: Path, no_network: None, capsys) -> None:
    """A pin bumped without its jar. The fix is named, and nothing is downloaded.

    This is THE failure the fence exists for: `pin.toml` is two lines a bump has to edit and
    a ~30 MB file it has to replace, and the file is the half a reviewer cannot see in a diff.
    """
    assert run(root, "--verify") == 1

    err = capsys.readouterr().err
    assert str(jar_of(root)) in err
    assert "does not exist" in err
    assert VERSION in err
    assert DIGEST in err
    assert "uv run poe fetch-plantuml" in err
    assert f"vendor/plantuml/plantuml-{VERSION}.jar" in err
    assert not jar_of(root).exists()


def test_verify_refuses_a_jar_that_is_not_the_pin(
    root: Path, no_network: None, capsys
) -> None:
    """Both hashes named. A jar that does not match is never re-fetched under `--verify`.

    The default mode would download over it, which is right for a bump and wrong for a fence:
    a fence that repairs what it is checking cannot fail, and this one has to fail so that a
    pull request carrying a mismatched jar is red before anything renders.
    """
    jar_of(root).write_bytes(b"some other jar entirely")

    assert run(root, "--verify") == 1

    err = capsys.readouterr().err
    assert DIGEST in err
    assert hashlib.sha256(b"some other jar entirely").hexdigest() in err
    assert "uv run poe fetch-plantuml" in err
    # and it left the file alone: repairing it is the bump step's job, not the fence's
    assert jar_of(root).read_bytes() == b"some other jar entirely"


def test_verify_refuses_an_empty_jar(root: Path, no_network: None, capsys) -> None:
    """A zero-byte jar is a mismatch like any other, and the message names its hash.

    Its own case rather than a variant of the one above, because a zero-byte file is what
    the plausible accidents actually leave behind -- an interrupted checkout, a failed LFS
    smudge, a `: > vendor/plantuml/plantuml-<version>.jar` -- and because "has no content to
    hash" is the shape a short-circuit takes when someone optimises this function: a
    `st_size == 0` early return that accepted the file left the whole suite green
    (reviewer B's B1 mutation, 263/263 passing). The hash of nothing is a real, stable
    sha256, so the fence needs no special case to catch this -- it needs a test saying so.
    """
    jar_of(root).write_bytes(b"")

    assert run(root, "--verify") == 1

    err = capsys.readouterr().err
    assert DIGEST in err  # what the pin names
    # sha256 of the empty byte string, written out rather than computed: this is the digest
    # that appears in the log of a truncated checkout, and it is worth being able to grep
    assert "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in err
    assert "uv run poe fetch-plantuml" in err
    # and the fence left it alone, as it does for every other mismatch
    assert jar_of(root).read_bytes() == b""


def test_verify_honours_plantuml_jar(
    root: Path,
    no_network: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    """An explicit choice wins here too, and the committed jar is then beside the point.

    A machine that exports the variable renders with that jar, so whether the checkout's own
    jar matches its pin does not decide whether that machine can run -- and the CI step, which
    captures stdout into `PLANTUML_JAR`, has to hand back the value it was given.
    """
    named = tmp_path / "elsewhere" / "plantuml.jar"
    named.parent.mkdir()
    named.write_bytes(b"a jar of the caller's own")
    monkeypatch.setenv("PLANTUML_JAR", str(named))

    assert run(root, "--verify") == 0

    captured = capsys.readouterr()
    assert captured.out.strip() == str(named)
    assert "PLANTUML_JAR names" in captured.err


def test_verify_refuses_a_plantuml_jar_naming_no_file(
    root: Path, no_network: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The same refusal the fetch gives, so the two modes cannot disagree about a value."""
    jar_of(root).write_bytes(PAYLOAD)
    missing = tmp_path / "gone.jar"
    monkeypatch.setenv("PLANTUML_JAR", str(missing))

    with pytest.raises(SystemExit) as caught:
        run(root, "--verify")

    assert "is not a file" in str(caught.value)


def test_verify_names_a_missing_pin(tmp_path: Path, no_network: None) -> None:
    """No pin file at all is a mistake about the tree, in either mode."""
    with pytest.raises(SystemExit) as caught:
        run(tmp_path, "--verify")

    assert "no pin file at" in str(caught.value)
