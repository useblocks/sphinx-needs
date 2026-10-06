"""Preparing one project's analysis, and turning its references into records.

Shared by the two places a build analyses a project: the ``src-trace`` directive (over
its scope, at read time) and the configuration pass of projects that no directive
traces (over the whole source directory, in the main process; see
``sphinx_extension/rediscovery.py``). Nothing here needs the docutils state or the
environment, so both callers get the same paths, the same URLs and the same records --
the ``@need-ids:`` references, and the :class:`SourcePage` of each file a local URL
names. Nothing here writes a file: the copies and their pages are made by every HTML
build, from the pages recorded in the environment (``source_tracing.generate_code_page``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePath

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.references import NeedIdRef, need_id_ref_records
from sphinx_codelinks.config import (
    CodeLinksConfig,
    CodeLinksProjectConfigType,
    SourceAnalyseConfig,
    anchor_preproc_paths,
    config_base_dir,
    git_root_problem,
    git_root_warning,
    locate_src_dir,
)
from ub_project import anchor


def fill_remote_url(
    remote_url_pattern: str, commit: str | None, remote_path: PurePath, line: int | str
) -> str:
    """A project's ``remote_url_pattern`` filled in for one file and line.

    ``{path}`` is POSIX on every platform, as a URL path is. The one place both a
    created need's ``remote-url`` and a reference's remote URL are formed.
    """
    return remote_url_pattern.format(
        commit=commit, path=remote_path.as_posix(), line=line
    )


def _checked_git_root(
    confdir: str | Path,
    codelinks_config: CodeLinksConfig,
    project_config: CodeLinksProjectConfigType,
) -> tuple[Path | None, str | None]:
    """A project's configured ``git_root``, anchored and resolved, and why it is
    ignored: ``(root, None)``, ``(None, None)`` when none is configured, or
    ``(None, <the problem>)``."""
    discover = project_config.get("source_discover_config")
    analyse = project_config.get("analyse_config")
    if discover is None or analyse is None or analyse.git_root is None:
        return None, None
    base_dir = config_base_dir(confdir, codelinks_config)
    root = anchor(analyse.git_root, base_dir).resolve()
    src_dir = locate_src_dir(confdir, codelinks_config, discover)
    problem = git_root_problem(root, src_dir)
    return (None, problem) if problem is not None else (root, None)


def configured_git_root(
    confdir: str | Path,
    codelinks_config: CodeLinksConfig,
    project_config: CodeLinksProjectConfigType,
) -> Path | None:
    """The git root a project configures, or ``None`` -- the ONE place it is decided.

    The ``git_root`` setting anchored at the configuration file's directory (see
    :func:`~sphinx_codelinks.config.config_base_dir`) and resolved; ``None`` when none
    is set, AND when :func:`~sphinx_codelinks.config.git_root_problem` finds one: it
    names no readable directory, or one that is neither ``src_dir`` nor above it (#2062): every record's ``path`` is relative to the git root, so it
    must contain the sources. A rejected value is treated as unset -- the analysis
    detects the repository from ``src_dir`` -- and :func:`git_root_warnings` says so
    once, at ``config-inited``. The analysis (:func:`prepare_analyse_config`) and the
    attach's root (``need_id_refs.project_root``) both take it from here, so the
    records and the attach agree on the root.
    """
    return _checked_git_root(confdir, codelinks_config, project_config)[0]


def git_root_warnings(
    confdir: str | Path, codelinks_config: CodeLinksConfig
) -> list[str]:
    """One message per project whose configured ``git_root`` is ignored (see
    :func:`configured_git_root`)."""
    projects = codelinks_config.projects
    if not isinstance(projects, dict):
        return []
    warnings = []
    for name, project_config in projects.items():
        if not isinstance(project_config, dict):
            continue
        _root, problem = _checked_git_root(confdir, codelinks_config, project_config)
        if problem is not None:
            warnings.append(git_root_warning(name, problem))
    return warnings


def prepare_analyse_config(
    confdir: str | Path,
    codelinks_config: CodeLinksConfig,
    project_config: CodeLinksProjectConfigType,
    *,
    src_dir: Path,
    src_files: Sequence[Path],
) -> SourceAnalyseConfig:
    """The analysis configuration for ``src_files`` of a project in ``src_dir``.

    ``git_root`` is :func:`configured_git_root`'s, and the preprocessor paths are
    anchored at the configuration file's directory, as ``src_dir`` is. A copy: the
    configured object is stored in the ``src_trace_projects`` config value, which is
    pickled with the environment, and mutating it would make every next build report
    ``[config changed]``.
    """
    base_analyse_config = project_config["analyse_config"]
    base_dir = config_base_dir(confdir, codelinks_config)
    git_root = configured_git_root(confdir, codelinks_config, project_config)
    preprocessor = base_analyse_config.preprocessor
    if preprocessor is not None:
        preprocessor = anchor_preproc_paths(preprocessor, base_dir)
    return replace(
        base_analyse_config,
        src_dir=src_dir,
        src_files=list(src_files),
        git_root=git_root,
        preprocessor=preprocessor,
    )


@dataclass(frozen=True)
class UrlContext:
    """Where an analysed project's files are copied, and how its URLs are formed."""

    dirs: dict[str, Path]
    """``src_dir``, ``out_dir``, ``target_dir`` (the copies), and ``remote_src_dir``
    (the source directory below the git root) when remote URLs are on."""
    local_url_field: str | None
    """The local URL field, when local URLs are on."""
    remote_url_field: str | None
    """The remote URL field, when remote URLs are on and the project has a pattern."""
    remote_url_pattern: str | None
    """The pattern, or ``None`` when no remote URL can be formed (#2045)."""


def url_context(
    codelinks_config: CodeLinksConfig,
    project_config: CodeLinksProjectConfigType,
    src_analyse: SourceAnalyse,
    src_dir: Path,
    out_dir: Path,
) -> UrlContext:
    """The URL rules of one analysed project, as the created needs and references use them."""
    dirs = {
        "src_dir": src_dir,
        "out_dir": out_dir,
        "target_dir": out_dir / src_dir.name,
    }
    local_url_field = None
    remote_url_field = None
    remote_url_pattern = None
    if codelinks_config.set_local_url:
        local_url_field = codelinks_config.local_url_field
    if codelinks_config.set_remote_url and project_config["remote_url_pattern"]:
        remote_url_field = codelinks_config.remote_url_field
        remote_url_pattern = project_config["remote_url_pattern"]
        if not src_analyse.git_root:
            # No git root found, use the source directory as the remote source directory
            dirs["remote_src_dir"] = src_dir
        else:
            dirs["remote_src_dir"] = src_dir.relative_to(src_analyse.git_root)
        if src_analyse.git_root is None or src_analyse.git_commit_rev is None:
            # no git root, or a repository without a commit: no remote URL (#2045)
            # -- the pattern would be filled with commit None (and, without a git
            # root, the build machine's absolute path). ubCode writes none either;
            # the analysis has already warned (codelinks.git_root / git_ref).
            remote_url_pattern = None
    return UrlContext(dirs, local_url_field, remote_url_field, remote_url_pattern)


@dataclass(frozen=True)
class SourcePage:
    """A source file a local URL names: copied into the HTML output, and paged beside
    its copy (``<target stem>.html``), by every HTML build whose output lacks them or
    holds them out of date.

    Recorded in the environment when a document is read (by host document) or a project
    without a directive is scanned (in its ``ConfigOnlyScan``); the copy and the page are
    made from the record at ``html-collect-pages``, never at read time.
    """

    source: str
    """The analysed file's absolute path (the environment is build-local)."""
    target: str
    """The copy's path relative to the output directory, POSIX (``src/refs.cpp``)."""
    anchors: tuple[tuple[int, str, str], ...]
    """``(line, docname, need id)`` of each one-line need created from the file, for
    its page's ``[docs]`` links; ``()`` for a file only references name."""


def page_target(context: UrlContext, filepath: Path) -> str:
    """Where ``filepath`` (absolute, under the project's ``src_dir``) is copied: its
    path relative to the output directory, POSIX on every platform."""
    dirs = context.dirs
    copy = dirs["target_dir"] / filepath.relative_to(dirs["src_dir"])
    return copy.relative_to(dirs["out_dir"]).as_posix()


def collect_need_id_refs(
    src_analyse: SourceAnalyse, project: str, context: UrlContext
) -> tuple[list[NeedIdRef], list[SourcePage]]:
    """The analysis' ``@need-ids:`` references, as records, and the pages of the files
    their local URLs name.

    Their URLs follow the created needs' rules: the remote one fills the project's
    ``remote_url_pattern`` exactly as a created need's does. The local one -- only
    when it is the value, i.e. there is no remote URL -- names the source's copy in
    the build output, beside which its page is written; with a remote URL no page is
    recorded, so no orphan copy or page is left in the output.
    """
    dirs = context.dirs
    src_dir = dirs["src_dir"]
    remote_url_pattern = context.remote_url_pattern

    def remote_url(filepath: Path, line: int) -> str | None:
        if remote_url_pattern is None:
            return None
        return fill_remote_url(
            remote_url_pattern,
            src_analyse.git_commit_rev,
            dirs["remote_src_dir"] / filepath.relative_to(src_dir),
            line,
        )

    pages: dict[str, SourcePage] = {}

    def local_url(filepath: Path, line: int) -> str | None:
        if context.local_url_field is None or remote_url_pattern is not None:
            return None
        target = page_target(context, filepath)
        # the file is copied and paged, as a file with a created need is
        pages.setdefault(target, SourcePage(str(filepath), target, ()))
        return f"{target}#L{line}"

    records = need_id_ref_records(
        src_analyse.need_id_refs,
        project=project,
        root=src_analyse.git_root or src_dir,
        root_kind="git" if src_analyse.git_root else "src_dir",
        remote_url=remote_url,
        local_url=local_url,
    )
    return records, list(pages.values())
