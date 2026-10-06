"""Preparing one project's analysis, and turning its references into records.

Shared by the two places a build analyses a project: the ``src-trace`` directive (over
its scope, at read time) and the configuration pass of projects that no directive
traces (over the whole source directory, in the main process; see
``sphinx_extension/rediscovery.py``). Nothing here needs the docutils state or the
environment, so both callers get the same paths, the same URLs and the same records.
"""

from __future__ import annotations

import shutil
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
    file_lineno_href,
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


def prepare_analyse_config(
    confdir: str | Path,
    codelinks_config: CodeLinksConfig,
    base_analyse_config: SourceAnalyseConfig,
    *,
    src_dir: Path,
    src_files: Sequence[Path],
) -> SourceAnalyseConfig:
    """The analysis configuration for ``src_files`` of a project in ``src_dir``.

    ``git_root`` and the preprocessor paths are anchored at the configuration file's
    directory, as ``src_dir`` is. A copy: the configured object is stored in the
    ``src_trace_projects`` config value, which is pickled with the environment, and
    mutating it would make every next build report ``[config changed]``.
    """
    base_dir = config_base_dir(confdir, codelinks_config)
    git_root = base_analyse_config.git_root
    if git_root:
        git_root = anchor(git_root, base_dir).resolve()
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


def collect_need_id_refs(
    src_analyse: SourceAnalyse, project: str, context: UrlContext
) -> list[NeedIdRef]:
    """The analysis' ``@need-ids:`` references, as records.

    Their URLs follow the created needs' rules: the remote one fills the project's
    ``remote_url_pattern`` exactly as a created need's does. The local one -- only
    when it is the value, i.e. there is no remote URL -- names the source copied
    into the build output, beside which its page is generated; with a remote URL
    nothing is copied, so no orphan copy or page is left in the output.
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

    def local_url(filepath: Path, line: int) -> str | None:
        if context.local_url_field is None or remote_url_pattern is not None:
            return None
        target_filepath = dirs["target_dir"] / filepath.relative_to(src_dir)
        if str(target_filepath) not in file_lineno_href.mappings:
            # copy the file and have its page generated, as for a created need
            target_filepath.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(filepath, target_filepath)
            file_lineno_href.mappings[str(target_filepath)] = {}
        relative = target_filepath.relative_to(dirs["out_dir"]).as_posix()
        return f"{relative}#L{line}"

    return need_id_ref_records(
        src_analyse.need_id_refs,
        project=project,
        root=src_analyse.git_root or src_dir,
        root_kind="git" if src_analyse.git_root else "src_dir",
        remote_url=remote_url,
        local_url=local_url,
    )
