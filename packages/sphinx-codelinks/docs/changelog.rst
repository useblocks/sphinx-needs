.. _changelog:

Changelog
=========

Unreleased
----------

New and Improved
................

- 🔧 Sphinx-CodeLinks now lives in the Sphinx-Needs repository, as
  `packages/sphinx-codelinks <https://github.com/useblocks/sphinx-needs/tree/master/packages/sphinx-codelinks>`__.

  The whole of ``useblocks/sphinx-codelinks``' history came with it, rewritten so that
  every historical commit already places its files under that directory: ``git log`` and
  ``git blame`` read the full history there with no ``--follow``, and
  ``packages/sphinx-codelinks/design/import-commit-map.txt`` maps every hash the old
  repository had to its hash in the new one.

  Some of the move is mechanical and already true; the rest is a checklist being worked
  through, and this bullet says which is which.

  - **The repository** (done): https://github.com/useblocks/sphinx-needs. Pull requests
    and branches are opened there, under ``packages/sphinx-codelinks/``.
  - **The issue tracker** (in progress): https://github.com/useblocks/sphinx-needs/issues.
    The open issues are being transferred, keeping their labels; the issue form has a
    *Package* dropdown with ``sphinx-codelinks`` among its options, and issues and pull
    requests concerning this package get a ``pkg: sphinx-codelinks`` label. Old issue URLs
    redirect.
  - **The documentation** (in progress): https://codelinks.useblocks.com stays the address.
    It is served by GitHub Pages from the old repository until the Read the Docs project
    and the DNS move are done, and by Read the Docs afterwards; nothing changes for a
    reader of that URL.
  - **The old repository** will be archived rather than deleted, so every permalink and
    every ``git+https://…/sphinx-codelinks.git@<sha>`` pin keeps resolving. Repositories
    pinning ``@main`` will stop receiving updates and should re-point at PyPI or at
    ``git+https://github.com/useblocks/sphinx-needs.git@…#subdirectory=packages/sphinx-codelinks``.
  - **Release tags** are prefixed: ``sphinx-codelinks-v1.4.0`` rather than ``1.4.0``. The
    bare namespace in that repository is Sphinx-Needs' own, and three of this project's
    seven released version numbers name existing Sphinx-Needs releases.
  - **An open pull request** can be moved across without losing its commits or their
    authorship: clone the old repository, fetch your branch, run the same
    ``git filter-repo --to-subdirectory-filter packages/sphinx-codelinks`` the import ran,
    and cherry-pick the range onto ``master`` in the monorepo. The import pull request's
    description carries the exact recipe.

- ✨ ``@need-ids:`` references are attached during the build to the needs they name, under each
  project's ``ref_url_field`` (default ``code_url``, ubCode's key), as a list of links; a
  reference to an unknown need warns ``codelinks.need_id_ref``; ``codelinks write rst`` is
  deprecated (`#2041 <https://github.com/useblocks/sphinx-needs/issues/2041>`__).

  The ``src-trace`` directive analysed every ``@need-ids:`` marker in its files and threw
  the result away: reaching the needs took ``codelinks analyse``, ``codelinks write rst``
  and an ``include`` of the generated ``needextend`` file. The references are now kept with
  the document hosting the directive and attached once every need is known, wherever it is
  defined. Each referenced need gets one entry per reference, in source order -- once,
  even when two directives or two projects scan the same file (files under different
  roots are different files, each kept): the project's
  ``remote_url_pattern`` filled in for the marker's line, or the local link when remote
  URLs are off. With local URLs only, a file referenced by ``@need-ids:`` is copied into
  the output and gets a source page, as a file with a one-line need is. ``needs.json``
  declares the field as a list; a need nothing references carries ``null``, which a
  strict ``unevaluatedProperties: false`` schema never sees. The references replace a
  value the need's own directive or a default gave the field; a user's ``needextend`` of
  the field wins. The unknown-id warning points at the source line (``src/refs.cpp:5``),
  and each project reports ``N references attached, M unknown``. The attach is on when
  local or remote URLs are, as in ubCode; ``ref_url_field = ""`` switches it off for a
  project. A changed source file updates ``needs.json`` and the referenced needs' cards on
  the next build.
  A comment that starts with a configured ``@need-ids:`` marker is a reference and never a
  one-line need, as in ubCode: on the default one-line style, whose start sequence ``@``
  matched it too, ``// @need-ids: A, B`` used to become a need with the id ``B`` (or stop
  the build with ``duplicate_id``).

  ``ref_url_field`` in ``[codelinks.projects.*]`` is accepted, where a shared
  ``ubproject.toml`` that set it for ubCode stopped the build with
  ``Additional properties are not allowed ('ref_url_field' was unexpected)``.

  ``codelinks write rst`` still works and prints a deprecation notice on stderr; it will
  be removed in 2.0.0. Its ``-r`` default stays ``remote_url`` -- not the extension's
  ``remote-url`` -- since changing what an existing invocation writes is not worth it for
  a command that is going away. A project that keeps including the generated file gets
  both the attached field and the ``needextend``'d one: remove the include, and any
  ``needs_fields`` declaration of the field made for that route.

- ✨ Multi-line needs: a need written across the lines of a comment, from an
  ``@need[<markup>] <type>: <title>`` line with ``:key: value`` options to an ``@endneed``
  line, its body in reStructuredText or Markdown
  (`#2152 <https://github.com/useblocks/sphinx-needs/pull/2152>`__,
  `#1885 <https://github.com/useblocks/sphinx-needs/issues/1885>`__,
  `#1898 <https://github.com/useblocks/sphinx-needs/issues/1898>`__).

  ``get_multiline_needs = true`` switches them on for a project, and
  ``[analyse.multiline_needs]`` sets the two words, the default markup and the markups
  table. A block lives in one comment, docstring or run of consecutive line comments, in
  every supported language (C/C++, C#, Rust, Go, JSONC, Python, YAML, Bash); comment
  prefixes are stripped by the comment's kind, the doxygen ``*`` leader only when every line
  carries one, so ``*emphasis*`` in a body is kept. A block's lines are never read as
  one-line needs or ``@need-ids:`` references. ``codelinks analyse`` writes each need to
  ``marked_content.json`` as a ``"type": "multiline-need"`` record -- the need with its
  option values as written, its ``doctype``, and a source with a root-relative path and
  the open, close and body lines -- and prints a malformed block as an analyse warning at
  its source line. The ``src-trace`` directive renders them in a following release, once
  Sphinx-Needs can parse a need's content in its declared markup; until then it creates no
  need from them.

  **Removed:** the ``@rst`` … ``@endrst`` blocks, ``get_rst`` and
  ``[analyse.marked_rst]``. Nothing ever rendered those blocks (#1885), so no project loses
  output; a configuration still naming either key is refused with a message naming its
  replacement.
  The ``"type": "rst"`` entries of ``marked_content.json`` are gone, ``codelinks write rst``
  ignores the new records, and the CLI prints every analyse warning as
  ``Analyse warning in <file>:<line> - <kind>: <message>`` (it said ``Oneline parser
  warning``). ``SourceAnalyse.oneline_warnings`` is now ``SourceAnalyse.warnings``, which
  holds the multi-line kinds too; the old name stays as a read-only alias for one release.
  The row fix for marked-rst blocks below (#1982) landed days before this change replaced
  them; multi-line needs keep its rule, a block reported at the row of its open line.

- 🐛 A source file added to a ``src-trace`` directive's scope is seen by the next
  incremental build, with no ``-E`` (`#2040 <https://github.com/useblocks/sphinx-needs/issues/2040>`__).

  Sphinx re-read the document hosting the directive when a file it had analysed was edited
  or removed, but a file added to its ``:directory:`` (or to the project, for a directive
  with neither option) was a dependency of nothing: its one-line needs and references
  appeared only once the document changed. Each directive now records its scope, and every
  build walks each recorded scope again -- one directory walk per scope, no parsing -- and
  re-reads the documents whose files changed. A ``:file:`` scope is that one file, so a new
  file beside it costs nothing. The build's output and doctree directories are never
  traced, nor is any builder's output elsewhere (the ``.ignore`` bullet below). The
  walk costs roughly 0.1 s per
  2,000 discovered files on an Apple M2 Pro laptop, whatever their size -- the
  directive's own discovery plus a ``stat`` per file -- while parsing them costs tens of
  times more (2,000 200-line C++ files: ~0.1 s of walk against ~9 s of analysis).

- ✨ A project that no ``src-trace`` directive traces has its ``@need-ids:`` references
  attached anyway (ubCode's config-only mode), behind the same gate as a directive's. Its
  whole source directory is analysed, in the main process and so under ``-j N`` too, and
  no need is created from it -- its line counts the one-line needs it did not create.
  Every build walks the directory and analyses it again only when its files or the
  configuration changed (and keeps the result, writing the root document if it must); a
  failing scan warns ``codelinks.need_id_ref`` and the build goes on.

- 🐛 A need's card is rewritten when its code references change, whichever document it is
  in: a source-only edit used to update ``needs.json`` but leave the card in a document
  that was not read again showing the old references. Such a document is now written
  again (not read again). A ``needtable`` in a third document that filters on the field is
  still rewritten only when that document is.

- 🐛 A source file reached through a symbolic link inside the traced directory is analysed
  once, not once per path to it (its one-line needs used to abort the build with
  ``duplicate_id``): it is listed under its resolved path, though two spellings of one file
  on a case-insensitive file system are still two entries.

- 🐛 Two ``src-trace`` directives whose scopes overlap no longer abort the build
  (``duplicate_id``): the first directive in document order defines a one-line need found
  by both, the other skips it with a ``codelinks.duplicate_need`` warning naming both
  documents, and takes it over when the first no longer traces it (in a serial build; with
  ``-j N`` the other document takes it over only when it is next read). The id is the
  marker's or, for a one-line style without ``id``, the one Sphinx-Needs generates. A
  directive moved to another document no longer aborts the next build either. Overlapping
  directives still analyse the shared files once each
  (`#2042 <https://github.com/useblocks/sphinx-needs/issues/2042>`__).

- 🐛 A ``git_root`` that does not contain ``src_dir``, and a source file that resolves to
  outside ``src_dir``, are diagnosed instead of producing ``../`` reference paths or a
  traceback (`#2062 <https://github.com/useblocks/sphinx-needs/issues/2062>`__).

  A configured ``git_root`` that does not exist, cannot be read, or is neither ``src_dir``
  nor a directory above it, is ignored with one ``codelinks.git_root`` warning, and the
  repository root is detected from ``src_dir`` as when none is set: the remote URLs, the
  ``@need-ids:`` records and the attach all follow the detected root. It used to give
  records whose ``path`` began with ``../`` (with local URLs), or a ``ValueError``
  traceback (with remote URLs). ``codelinks analyse`` applies the same rule, warning on
  stderr, where such a ``git_root`` with a remote used to end it with a ``ValueError``.

  A file that discovery reaches through a symbolic link but whose target lies outside
  ``src_dir`` -- a file link, or a file below a followed directory link -- is skipped with
  one ``codelinks.outside_src_dir`` warning naming the link and its target, in a
  ``src-trace`` directive, a ``:file:`` scope, the scan of a project no directive traces,
  ``codelinks discover`` and ``codelinks analyse`` alike (the latter's
  ``marked_content.json`` no longer holds the file's markers). **This changes
  behaviour:** such a file used to be listed by discovery and analysed, and a build
  aborted with
  ``ValueError: … is not in the subpath of …`` as soon as it held a one-line need (URL
  fields on or off) or, with a URL field on, an ``@need-ids:`` reference; it is now never
  traced. Widen ``src_dir`` to cover the target, or exclude the link.

- 🐛 A ``src-trace`` directive whose ``:file:`` names no file -- a missing path, or a
  directory -- warns once at the directive (``codelinks.missing_file``: "src-trace:
  <target> is not a file below <src_dir>") and the build goes on, where it used to abort
  (``FileNotFoundError``, or ``IsADirectoryError`` for a directory) -- in a fresh build,
  or when the file was removed since the last; re-created, the file is traced again by
  the next build. ubCode errors the directive
  instead ("src-trace :file: … not found"); codelinks warns for every recoverable
  configuration problem
  (`#2069 <https://github.com/useblocks/sphinx-needs/issues/2069>`__).

- 🐛 Malformed one-line markers are now reported in the build, at the source line, as
  ``codelinks.oneline`` warnings; a build with ``-W`` that has one fails until the marker
  is fixed or ``suppress_warnings = ["codelinks.oneline"]`` is set. On a one-character
  start sequence such as the default ``@``, a line without the field separator is not a
  marker (ubCode's rule), so documentation tags like ``@param`` and ``@brief`` do not
  warn; an empty marker is not a marker, as in ubCode; a marker Sphinx-Needs refuses (an
  id ``needs_id_regex`` rejects, say) warns too, instead of stopping the build; and the
  messages are ubCode's (``1 given fields, minimum is 2``). The never-written warnings
  file under ``src_trace_cache`` and its reader are gone, a file nothing had written
  since at least 1.4.0 (:ref:`oneline_invalid`,
  `#2076 <https://github.com/useblocks/sphinx-needs/issues/2076>`__).

- 🐛 A one-line need whose style has no ``id`` field no longer aborts the build with
  ``KeyError: 'id'`` when local URLs are on; its source page links back to the generated
  id, and the page's back-link is a POSIX path on Windows too
  (`#2082 <https://github.com/useblocks/sphinx-needs/issues/2082>`__).

- 🐛 The source copies and pages are build state: kept up to date by every HTML build
  whether or not the directive's document is read again, under ``-j N`` too, and by HTML
  builders only (`#2070 <https://github.com/useblocks/sphinx-needs/issues/2070>`__, and the missing
  pages of `#2044 <https://github.com/useblocks/sphinx-needs/issues/2044>`__).

  With local URLs, each source file a need is created from or a reference names is copied
  into the output (``<outdir>/<src_dir name>/<path>``) and paged beside the copy -- the
  target of every local link. Both were side effects of the analysis, made only by a build
  that read the directive's document, from a registry that a ``-j N`` worker never handed
  back: a removed output directory, a second builder sharing the doctrees (``html`` then
  ``dirhtml``) or a parallel build left dead local links. What to copy and page is now kept
  in the environment, with the document (or the scanned project) it came from, and every
  HTML build writes those its output lacks or holds out of date; each page's ``[docs]`` link
  is the builder's own relative URI, so a ``dirhtml`` page links back correctly too. An
  unchanged build rewrites no copy or page; a page is written again when its source
  changed, a document tracing it -- now or before -- was read again, added or removed, or
  the output lacks it; a copy carries its source's modification time, so a source replaced
  by an older file is copied again too. A LaTeX build no longer drops source copies into
  its output; a source removed before the pages are written, or a second source copied to
  the same place (two projects whose source directories share a name), warns
  ``codelinks.source_page``. The first build after upgrading reads every document once:
  an environment from an earlier release holds no page records.

- 🐛 On Sphinx 7.4 with ``show_warning_types = True`` the ``[codelinks.*]`` type of a
  warning is shown once, not twice
  (`#2091 <https://github.com/useblocks/sphinx-needs/issues/2091>`__).

  Before Sphinx 8, Sphinx-CodeLinks appends the type to the warnings of its analysis
  itself, as Sphinx 8 does by default; it also did so when ``show_warning_types`` had
  Sphinx 7.4 append it, so the line ended in
  ``[codelinks.outside_src_dir] [codelinks.outside_src_dir]``. It is now appended only
  where Sphinx does not append it.

- 🔧 Every builder writes an ``.ignore`` file (``*``) at the root of its output and doctree
  directories, so with ``gitignore = true`` nothing any builder writes is traced --
  the extension's source copies, Sphinx's ``_downloads/`` copies of a traced source,
  another builder's whole tree -- wherever the output sits
  (`#2071 <https://github.com/useblocks/sphinx-needs/issues/2071>`__): two output trees
  inside ``src_dir`` but outside the documentation source directory
  (``sphinx-build docs build/html`` beside ``build/dirhtml``) no longer copy each other's
  copies, one level deeper per build. The directory containing the output and doctree
  directories is now skipped only for ``gitignore = false`` projects, which read no ignore
  file -- so with the default, an output directory placed directly inside a traced source
  directory no longer hides the sources beside it.

- ⬆️ ``typer`` is no longer capped below 0.26.8. The cap protected the documentation build,
  whose ``sphinxcontrib-typer`` imported a ``typer.rich_utils`` name that 0.26.8 removed;
  the ``docs`` extra now requires ``sphinxcontrib-typer`` 0.9.1 or newer, which tracks
  the new typer and declares its own floor on it.
- ⬆️ ``click`` is no longer a dependency. The line existed only to cap it below 8.2, working
  around click 8.2.0 printing an empty error when ``codelinks`` ran with no arguments -- an
  incompatibility in the typer of the time. This package never imported click itself, and
  the typer it requires no longer depends on click at all, so the cap was pinning a package
  nothing used; dropping it removes click from the environment.
- ⬆️ docutils 0.21 or newer is now required. The line was a bare ``docutils`` that left the
  floor to Sphinx, which accepts 0.20; it is now ``docutils>=0.21``, the floor the whole
  Sphinx-Needs workspace declares and type-checks against. There is no upper bound: Sphinx
  caps docutils per series itself.

- 🐛 A marked-rst block with text before its start marker on the same line was reported
  one row too low
  (`#1982 <https://github.com/useblocks/sphinx-needs/issues/1982>`__).

  The row of ``@rst`` was taken as the number of lines before it, and ``splitlines()``
  counts a partial line too -- so a one-line block such as ``// @rst … @endrst``, or an
  ``@rst`` behind a doxygen ``*`` prefix, landed on the row below. The row is now the
  number of newlines before the marker. The source maps in ``marked_content.json`` and the
  blob links built from them move up by one row for such blocks; a block whose ``@rst``
  starts its own line is unaffected.

- 🐛 ``src_trace_projects`` declared directly in ``conf.py`` are normalised before
  ``src-trace`` reads them.

  Projects configured without ``ubproject.toml`` now get the same typed
  ``source_discover_config`` and ``analyse_config`` objects as TOML-backed projects, so a
  ``src-trace`` directive no longer fails with ``KeyError: 'source_discover_config'``.

- 🐛 ``sphinx_codelinks.__version__`` reported ``"0.1.0"``.

  It had said so since the first commit, through seven releases, while the distribution
  metadata said otherwise -- so ``import sphinx_codelinks; sphinx_codelinks.__version__``
  on an installed 1.4.0 returned the wrong string. It is exported in ``__all__``, so this
  is a public-API fix rather than a cosmetic one. From now on the two move together: the
  workspace's ``bump`` command writes both, and its ``check_workspace`` fence fails when
  they disagree.

- 🐛 ``locate_git_root`` found no git root in a linked git worktree, where ``.git`` is a
  file rather than a directory
  (`#106 <https://github.com/useblocks/sphinx-codelinks/issues/106>`__).

  ``locate_git_root`` required ``.git`` to be a directory, and ``get_remote_url`` and
  ``get_current_rev`` then read ``<root>/.git/config`` and ``<root>/.git/HEAD`` directly.
  In a linked worktree ``.git`` is a file holding ``gitdir: <path>``, the remotes live in
  the main repository's git directory named by ``commondir``, and only per-worktree state
  is local -- so every ``remote-url`` and every source link was missing, and a
  documentation build with ``-nW`` failed outright. Both shapes are now handled, with a
  regression test that builds a real worktree.

- 🐛 The ``local-url`` and ``remote-url`` links render under ``sphinx-build -j N``, and each
  project's ``remote-url`` links with that project's ``remote_url_pattern``
  (`#2039 <https://github.com/useblocks/sphinx-needs/issues/2039>`__).

  The ``src-trace`` directive wrote the two fields' ``needs_string_links`` entries into the
  configuration while it was read. A parallel worker never hands such a write back, so
  under ``-j N`` both fields rendered as plain text; every rebuild reported
  ``The configuration has changed (… 'needs_string_links' …)``; and with two projects
  whose ``remote_url_pattern`` differed, the project read last decided every need's link.
  The entries are now registered once, at ``config-inited``.

  ``remote-url`` now holds the URL it is named for. In ``needs.json`` its value is the
  project's ``remote_url_pattern`` filled in for the marker
  (``https://github.com/org/repo/blob/<commit>/src/a.cpp#L3``), where it used to be the
  fragment ``src/a.cpp#L3``. The card links to the same URL; its name is now the part of
  the URL after the commit (``src/a.cpp#L3`` for GitHub and GitLab patterns,
  ``src/a.cpp#lines-3`` for Bitbucket), or the whole URL when the pattern has no commit in
  its path. A value that is not a URL renders as text -- including a ``path#Lline`` value
  from a ``needs.json`` built by an earlier release, which used to be linked through the
  pattern. ``local-url`` is unchanged. A ``needextend`` that sets ``remote-url`` to full URLs, as
  ``codelinks write rst -r remote-url`` generates, now links to each URL as given instead
  of to the URL appended to itself.

  A ``remote_url_pattern`` containing ``,`` or ``;`` (gitweb's
  ``?p=repo.git;a=blob;f={path}``, for one) is not supported for rendering: Sphinx-Needs
  splits a string-linked value on those characters, so its link renders as several broken
  ones. The build warns about such a pattern (``codelinks.remote_url_pattern``;
  ``suppress_warnings`` silences it, which a ``-W`` build needs).

- 🐛 A project outside a git repository, or in one without a commit yet, gets no remote
  URL (`#2045 <https://github.com/useblocks/sphinx-needs/issues/2045>`__).

  Its ``remote_url_pattern`` was filled with ``None`` for the commit and the build
  machine's absolute path for ``{path}`` (``…/blob/None//home/me/project/src/a.cpp#L1``),
  and that reached ``needs.json`` as a URL. Now a created need's ``remote-url`` stays
  unset, and an ``@need-ids:`` reference falls back to its local link (or to nothing,
  without local URLs) -- as in ubCode. The ``codelinks.git_root`` warning is unchanged.

- 🔧 ``libclang`` is now genuinely optional for the test suite.

  It has always been an optional extra at runtime, and three test modules guarded it with
  ``pytest.importorskip``; a fourth imported ``sphinx_codelinks.analyse.preproc`` without
  a guard, and that package imports the libclang loader eagerly, so an environment without
  the wheel failed during collection rather than skipping. It now degrades honestly: the
  56 test cases that need the engine stop running, and the other 303 run -- the summary
  reads ``303 passed, 26 skipped``, because a module-level ``importorskip`` is one skip
  per module and never collects the tests inside it.

- 🔧 Lint and type checking now use the Sphinx-Needs workspace's configuration.

  The ``[tool.ruff]`` tables are the workspace root's, and the one per-file-ignore entry
  this package still needs went to the root with them, scoped to
  ``packages/sphinx-codelinks/tests/*`` (``E402``, ``SIM300`` -- 2 findings if it were
  dropped). It is scoped rather than ``**/tests/*`` because at the root that glob would
  silently loosen the other packages' suites too. Linting and formatting are now
  ``uv run poe lint``, which runs the whole workspace's hook set. Type checking moves from
  mypy to `ty <https://github.com/astral-sh/ty>`__ -- ``uv run poe typecheck`` -- the
  ``mypy`` dependency group becomes a ``typing`` one that pins the oldest supported Sphinx
  and docutils, and the 61 ``# type: ignore`` comments become 17 ``# ty: ignore`` ones.
  The dead ``pydantic.mypy`` plugin -- nothing in the package imports pydantic -- and the
  unused ``pytest-docker``, ``moto`` and ``psutil`` test dependencies go with it. No
  behaviour changed; the whole diff is import order, suppressions and configuration.

- ‼️ Sphinx-Needs 8.5 or newer is now required (previously 5.0 or newer).

  Sphinx-CodeLinks is being imported into the Sphinx-Needs repository as a package of its
  uv workspace, where there is exactly one Sphinx-Needs and the manifest is required to
  track it tightly — ``sphinx-needs>=8.5.0,<9`` — so a wheel can never claim compatibility
  with a release it was not tested against. The per-Sphinx-Needs test factor is gone with
  it, and the two compatibility shims the old floor needed have been deleted: the
  ``add_field`` import fallback for Sphinx-Needs < 8, and the ``add_extra_option``
  signature probe that chose between a schema-aware and a schema-less registration. Both
  already took the modern branch on Sphinx-Needs 8.5, so behaviour there is unchanged.

- ✨ Python 3.11 is now supported; the floor moves down from 3.12.

  The full test suite passes on 3.11 unchanged, and the floor now equals the one the
  Sphinx-Needs workspace declares. The test matrix runs ``py{311,312,313,314}`` against
  ``sphinx{7,8,9}``, with one corner left out: ``py311-sphinx9`` is deliberately not a
  valid environment. Not because Sphinx 9 needs Python 3.12 -- Sphinx 9.0.x declares
  ``requires-python >=3.11`` and is exactly what a Python 3.11 user resolves by default,
  since 9.1 excludes itself for them -- but to align with the Sphinx-Needs workspace this
  package is being imported into, whose ``sphinx-9`` dependency group is
  ``sphinx~=9.1; python_version >= '3.12'`` and is therefore empty on 3.11. No package in
  that workspace is tested on 3.11 against Sphinx 9, and this matrix is replaced by that
  one at import, so the combination is left unexercised here too, deliberately.

- 📚 The documentation sources moved up beside ``conf.py``, so Read the Docs can build them.

  ``docs/source/*`` is now ``docs/*``, and the docs build no longer passes ``-c``:
  ``sphinx-build -nW --keep-going -b html docs docs/_build/html`` is what
  ``uv run poe docs-codelinks`` runs and what Read the Docs runs by itself. A
  ``.readthedocs.yaml`` comes with it, and the ``docs`` requirements move from a dependency
  group to a ``docs`` extra, which is the only form Read the Docs can install. The
  rendered site is unchanged; only the "edit this page" links point at the new paths.

- ✨ The default configuration file is now ``ubproject.toml``.

  :ref:`src_trace_config_from_toml` now defaults to ``"ubproject.toml"`` and the
  documentation recommends this file name throughout. ``ubproject.toml`` is the shared
  ubCode project file, which other useblocks tools — e.g. Sphinx-Needs via
  ``needs_from_toml`` or the ubCode checker in VS Code — read as well. Keeping the
  ``[codelinks]`` configuration in this single file makes all tools aware of the
  configured codelinks projects, which previously required a separate file per tool
  (e.g. ``src_trace.toml``) and left tools like the ubCode checker reporting
  ``Unknown codelinks project`` (ubcode-pub#75).

  A default file that does not exist or contains no ``[codelinks]`` table is silently
  ignored, so existing projects without ``ubproject.toml`` keep building without new
  warnings. The default is the value ``ubproject.toml`` exactly -- left unset, or
  written in :file:`conf.py` as that string -- so a 1.4.0 project that wrote
  ``src_trace_config_from_toml = "ubproject.toml"`` no longer gets a warning for a
  missing file or a missing table. Any other value, ``./ubproject.toml`` included, is an
  explicit file and warns when missing or without the table. A file that exists but
  cannot be read or parsed -- invalid TOML, not UTF-8, a directory, a ``codelinks`` key
  that is not a table -- warns (``codelinks.config``) either way, as any configured file
  did at 1.4.0. The
  documentation project itself now stores its codelinks configuration in
  ``ubproject.toml``.

- 🐛 A value given on the command line with ``-D`` now overrides the TOML file.

  ``sphinx-build -D src_trace_set_local_url=0`` was silently overwritten by a
  ``set_local_url`` in the ``[codelinks]`` table. The order is now ``-D`` > TOML >
  :file:`conf.py` > default, as in Sphinx-Needs. Only the full ``src_trace_<key>`` name
  counts: a bare ``-D set_local_url=0``, which Sphinx rejects as an unknown setting,
  leaves the TOML value alone. ``src_trace_projects`` always comes from :file:`conf.py`
  or the TOML: Sphinx refuses to override a dictionary setting with ``-D``, and the
  dotted ``-D src_trace_projects.<name>=...`` form is not supported. Sphinx refuses
  ``-D src_trace_outdir`` too, whose default is a path, and the TOML value then stands.
  A ``-D`` value Sphinx cannot convert (``-D src_trace_set_local_url=yes`` on
  Sphinx 8.2 or newer) is now reported by Sphinx instead of being silently replaced by
  the TOML, as it already was without a TOML.

- 👌 ``ubproject.toml`` is read through `ub-project <https://pypi.org/project/ub-project/>`__,
  the shared reader of the Sphinx-Needs family, which is now a dependency
  (``ub-project>=1.1.0,<2``).

  Both the Sphinx extension and ``codelinks analyse`` parse the file and select the
  ``[codelinks]`` table through it, and relative paths are anchored through its
  ``anchor``, at the same directories as before. What changes is what a broken file
  says: every message names the file and the problem (``invalid TOML``,
  ``not valid UTF-8``, ``[codelinks] must be a table, got str``), an explicitly
  configured file without a ``[codelinks]`` table says so instead of printing
  ``'codelinks'``, and ``codelinks analyse`` shows why a file could not be loaded rather
  than only that it could not -- a ``codelinks`` key that is ``0``, ``false`` or ``[]``
  is now reported as not a table instead of as a missing section. The extension's
  warnings about its configuration file carry the type ``codelinks.config``, so
  ``suppress_warnings = ["codelinks.config"]`` silences them.

- 🐛 A one-line need or ``@need-ids`` reference inside a C++ class or struct body, with no
  function after it, is associated with that class or struct.

  The C/C++ scope table named ``class_definition``, a node kind tree-sitter-cpp never
  emits, so such a marker had no ``tagged_scope``; it now names ``class_specifier`` and
  ``struct_specifier``, the kinds the grammar does emit.

- 🐛 Marker positions are physical: a one-line need's or ``@need-ids`` reference's
  ``source_map`` columns count the characters before it on its line.

  They counted from the start of the comment, so an indented marker, a comment after code,
  or a comment after a non-ASCII character reported a column that was not its column in the
  file; source links and editors that jump to a marker landed in the wrong place. A
  reference's span also started at the whitespace after ``@need-ids:`` rather than at its
  first id, and ended that many characters early.

- 👌 In a Python file, a line whose one-line start sequence is directly followed by a
  docstring tag (``@param``, ``@return``, ``@raises`` and the other Epydoc, Doxygen and
  Sphinx field names) is reported as a ``docstring_tag`` warning and creates no need.
  ``@param a: the first, thing`` used to become a need with the id ``thing``; the warning
  says to choose a start sequence the docstrings do not use.

.. _`release:1.4.0`:

1.4.0
-----

:Released: 30.07.2026

New and Improved
................

- ✨ Added Bash language support for the ``analyse`` module.

  Comments in shell scripts are now parsed for need ID references and one-line need
  definitions. ``.sh``, ``.bash``, ``.zsh``, and ``.ksh`` files are discovered when
  ``comment_type = "bash"``. The supported comment style is ``#``. Fish shell is not
  supported (no ``tree-sitter-fish`` grammar is published for the Python package).

- ✨ Added an opt-in preprocessor-aware C/C++ extraction engine, powered by libclang.

  The default tree-sitter engine sees every comment in a file, regardless of conditional
  compilation. Configuring the new :ref:`analyse.preprocessor <preprocessor_config>` table
  switches C/C++ extraction to libclang, which evaluates the preprocessor and emits only
  the markers in **active** branches — a need behind an inactive ``#if`` / ``#else`` is
  dropped. Compiler flags are resolved per file from a ``compile_commands.json``
  compilation database, with an explicit ``defines`` list for headers, which are not
  listed in such a database. Active markers keep their original line numbers.

  The engine requires the optional ``libclang`` dependency
  (``pip install 'sphinx-codelinks[libclang]'``). Plain tree-sitter C/C++ extraction is
  unaffected when it is not installed. See :ref:`preprocessor_engine` for details.

- 📚 Traced the preprocessor-aware C/C++ engine in the feature documentation.

  ``features.rst`` now declares the engine as a feature with its fault children, and the
  implementation carries the one-line markers that link back to it. The engine is therefore
  covered by the project's own traceability report, like every supported language.

- 🧪 Added a declarative fixture and snapshot test layer for marker extraction.

  Extraction cases are now data (a YAML fixture plus a captured JSON snapshot) instead of
  bespoke test functions, covering the one-line, need-ID-reference and ``@rst`` block
  surfaces across all supported languages.

Fixes
.....

- 🐛 Anchor newline-terminated one-line markers to the start of the comment.

  A start sequence (default ``@``) that appeared in free-form prose was matched anywhere in
  a comment, so a line such as ``// See @author, check the example`` was parsed as a need
  definition and the bogus ID raised ``InvalidNeedException`` in Sphinx-Needs. Markers that
  run to the end of the line now only match when nothing but comment decoration (``//``,
  ``#``, ``*``, ``///``, ``//!``, …) and whitespace precedes the start sequence. Markers
  with an explicit ``end_sequence`` (e.g. ``[[ … ]]``) are self-delimiting and remain
  position-independent, so they may still follow prose.

- 🐛 Pinned ``typer`` and ``sphinxcontrib-typer`` to keep the documentation build working.

  ``typer 0.26.8`` removed ``rich_utils.STYLE_METAVAR`` and ``sphinxcontrib-typer 0.9.1``
  requires ``rich_utils.STYLE_TYPES``; either combination broke ``sphinx-build``. The
  dependencies are now capped at ``typer<0.26.8`` and ``sphinxcontrib-typer<0.9.1``.

.. _`release:1.3.0`:

1.3.0
-----

:Released: 20.06.2026

New and Improved
................

- ✨ Added Go parser for the ``analyse`` module.

  Need ID references and one-line need definitions can now be extracted from Go source files.
  The supported comment styles are ``//`` and ``/* */``.

- ✨ Added JSONC language support for the ``analyse`` module.

  Comments in JSONC files are now parsed for need ID references and one-line need definitions.
  ``.json`` files are also checked when they begin with a comment (see jsonc.org).

- 👌 Replaced ``gitignore-parser`` with ``ignore-python`` for source discovery.

  This adds native nested ``.gitignore`` support, improves performance, and brings behavioral
  parity with ubCode. A per-project ``follow_links`` configuration option was also added.

- ⬆️ Support and test Sphinx-Needs v5-8.
- ⬆️ Allow Sphinx 9.
- 📚 Documented C# language support in ``features.rst``.
- 🧪 Added a Sphinx integration test for C# source files.

Fixes
.....

- 🐛 Register Sphinx-Needs fields with a typed schema.

  The ``project``, ``file``, ``directory`` and URL fields are now registered with a typed
  (string) schema, so they no longer trigger schema violations on needs that do not set them
  when strict Sphinx-Needs schema validation is enabled.

- 🐛 Do not mutate the ``rebuild='env'`` ``src_trace_projects`` configuration during builds.

  Incremental Sphinx builds no longer re-read every document on each run.

- 🐛 Route ``analyse`` logging through the active environment instead of installing a stderr
  handler at import time.

  Routine INFO progress no longer goes to stderr unconditionally, and importing the package no
  longer forces a logging handler onto consumers.

- 🐛 Validate field default ordering in the oneline configuration.

  A required field defined after a field with a default is now reported as an error instead of
  being silently skipped.

.. _`release:1.2.0`:

1.2.0
-----

:Released: 18.02.2026

New and Improved
................

- ✨ Added Rust parser for the ``analyse`` module.

  Need ID references and one-line need definitions can now be extracted from Rust source files.

- 👌 Added explicit ``git_root`` configuration option.

  Users can now explicitly specify the Git root directory instead of relying on automatic detection.

- 👌 Enhanced warning logging in the oneline parser.

  Warning messages now include more context to help diagnose parsing issues.

- 📚 Added traceability page to the documentation.
- 📚 Added ``features.rst`` page documenting the full feature set with source tracing.

Fixes
.....

- 🐛 Fixed space handling in marker extraction.

  Leading and trailing spaces in extracted marker content are now correctly stripped.

.. _`release:1.1.0`:

1.1.0
-----

:Released: 02.10.2025

New and Improved
................

- ✨ Added C# parser for ``analyse`` module.

  Need ID references and marked RST blocks can be extracted from C# source files.
  The comments styles supported are:(``//``, ``/* */``, ``///``)

- ✨ Added YAML parser for ``analyse`` module.

  Need ID references can be extracted from YAML files.
  The supported comment style is ``#`` as well as inline comment style, e.g. ``key: value # comment``.

- 👌 Directive ``src-trace`` itself does not create need items anymore and only generate need items from the one-line need definition in the given source.

  The need item is removed because:

  - It has no use cases so far.
  - It creates extra need items users may not actually want in their documentation
  - It creates errors with some Sphinx-Needs configurations, e.g., when ``need_id_required`` or ``needs_statuses`` is defined.

Fixes
.....

- 🐛 Replace absolute path with relative path to fix ``local-url`` not working on the non-local environment
- 🐛 Add more file extensions of C/C++ for SourceDiscover

.. _`release:1.0.0`:

1.0.0
-----

:Released: 22.08.2025

New and Improved
................

- ✨ Added a new ``analyse`` CLI command and corresponding API.

  The ``analyse`` command parses source files (Python, C/C++) and extracts markers from comments.
  It can extract three types of markers, as documented in the :ref:`analyse <analyse>` section:

  - One-line need definitions
  - Need ID references
  - Marked RST blocks

  The extracted markers and their metadata are saved to a JSON file for further processing.

- ✨ Added a new ``write rst`` CLI command.

  The ``write rst`` command writes a reStructuredText file with :external+needs:ref:`needextend <needextend>` directive from the extracted markers generated by ``analyse``.
  The generated RST can be included in the Sphinx documentation to create the source code links in the existing needs

- 👌 Replaced ``virtual_docs`` with the new ``analyse`` module.

  The ``virtual_docs`` feature, which handled one-line need definitions (:ref:`OneLineCommentStyle <oneline>`),
  has been migrated into the new ``analyse`` module and removed from the core.
  The caching feature of ``virtual_docs`` is temporarily removed and may be reintroduced later.

- 👌 Updated the ``src-trace`` Sphinx directive.

  The ``src-trace`` directive now uses the new ``analyse`` API instead of the old ``virtual_docs`` one.

- 👌 Unified configuration in TOML

  The configuration for ``src-trace`` directive defined in TOML is now compatible with the new ``analyse`` module.

.. _`release:0.1.2`:

0.1.2
-----

:Released: 16.07.2025

Fixes
.....

- 🐛 Apply default configuration values when not given

  When a user does not specify certain configuration options, the extension will automatically use predefined default
  values, allowing users to get started quickly without needing to customize every option.
  Users can override these defaults by explicitly providing their own configuration values.

- 🐛 Fix local links for multi project configurations

  Local links between docs and one-line need definitions work correctly, when :ref:`src_dir <source_dir>` in multiple
  project configurations point at different locations.

.. _`release:0.1.1`:

0.1.1
-----

:Released: 11.07.2025

Initial release of ``Sphinx-CodeLinks``

This version features:

- ✨ Sphinx Directive ``src-trace``
- ✨ Virtual Docs and Source Discovery CLI
- ✨ One-line comment to define a ``Sphinx-Needs`` need item
