:hide-navigation:

Changelog
=========

Unreleased
----------

The Sphinx-free half is its own distribution, ub-test-reports
.............................................................

- ‼️ The ``test-reports`` converter, the pytest plugin, the parsers, the result
  vocabulary, the deterministic case IDs and the ``[test_reports]`` model of
  ``ubproject.toml`` are now **ub-test-reports** 1.0.0, a distribution of their own with no
  Sphinx in it, imported as ``ub_test_reports``. They moved unchanged::

     pip install ub-test-reports              # the test-reports command
     pip install "ub-test-reports[pytest]"    # and the pytest plugin

  sphinx-test-reports is the Sphinx extension alone, and depends on ub-test-reports, so
  both still arrive with it.

- ‼️ **pip install sphinx-test-reports brings Sphinx, Sphinx-Needs, docutils and
  ub-test-reports again.** This reverses 2.0.0's install-footprint change: the extension's
  dependencies are hard dependencies now, not the ``sphinx`` extra. A CI job or a Bazel
  action that installed sphinx-test-reports only for the ``test-reports`` command or the
  pytest plugin now gets the whole documentation toolchain -- and a resolver conflict
  wherever that environment pins another Sphinx. Install ``ub-test-reports`` there instead:
  it is the same command and the same plugin, without the toolchain.

- ‼️ **The** ``test-reports`` **command belongs to ub-test-reports now**, so a tool installer
  that takes the command from the package you name finds none in sphinx-test-reports:
  ``pipx install sphinx-test-reports`` fails with "No apps associated with package
  sphinx-test-reports", and ``uv tool install sphinx-test-reports`` with "No executables are
  provided by package \`sphinx-test-reports\`". Name ``ub-test-reports`` there (``pipx install
  ub-test-reports``, ``uv tool install ub-test-reports``), and in anything else that looks
  the script up in the installing package's own metadata. ``pip install
  sphinx-test-reports`` still puts ``test-reports`` on the path, through the dependency.

- The ``sphinx`` extra is accepted and ignored until 4.0 -- ``pip install
  "sphinx-test-reports[sphinx]"`` installs exactly what the bare line does -- and the
  ``pytest`` extra passes through to ``ub-test-reports[pytest]`` until 4.0, so 2.0.0's
  documented install lines keep working.

- ‼️ **The pytest plugin is** ``-p ub_test_reports.pytest_plugin``. Its pluggy registration
  name is now ``ub_test_reports.xml_shape`` and the configuration warnings it issues start
  with ``ub_test_reports.pytest_plugin:`` (2.0.0: ``sphinxcontrib.test_reports.xml_shape``
  and ``sphinxcontrib.test_reports.pytest_plugin:``); a warning filter matching that text
  needs the new prefix. The two ``user_properties`` wire names it reserves do not change.

- ‼️ **The old module names need the extension.** ``sphinxcontrib.test_reports.junitparser``,
  ``.jsonparser`` and ``.pytest_plugin`` (below) are shipped by sphinx-test-reports, so they
  resolve only where it is installed -- which now means with Sphinx. On 2.0.0 a Sphinx-free
  environment could ``pip install sphinx-test-reports`` and import them; on 3.0 such an
  environment installs ``ub-test-reports`` and imports ``ub_test_reports.junitparser`` (and
  so on). With only ub-test-reports installed the old names fail as a plain
  ``ModuleNotFoundError: No module named 'sphinxcontrib'``.

- 🔧 The load-time toolchain check is gone. It existed because the toolchain was an opt-in
  extra pip never saw; as hard dependencies, pip resolves the floors itself. An environment
  whose Sphinx-Needs is downgraded below the floor AFTER installing is no longer refused:
  the extension does not check, so a below-floor Sphinx-Needs runs untested (it may work, it
  may fail anywhere); ``pip check`` (or ``uv pip check``) names the conflict. The extension
  itself still refuses a Sphinx older than 7.4 when it loads. With the check went
  ``compat-requirements.txt``, which the release's compatibility cell needed only while the
  toolchain was optional.

- The modules that moved were ``sphinx_test_reports.<module>`` only in this unreleased
  version -- 2.0.0 shipped them as ``sphinxcontrib.test_reports.<module>`` -- so no alias is
  kept for the ``sphinx_test_reports`` spelling; the old names that do keep working are the
  four below.

The import name moves
.....................

- ♻️ The extension is imported as ``sphinx_test_reports`` now, not
  ``sphinxcontrib.test_reports``: ``extensions = ["sphinx_test_reports"]``. The pytest
  plugin and the parsers moved further, to ``ub_test_reports`` (above).

  Four old names keep working until **4.0**, each with a warning that names its
  replacement. 4.0 turns all four into errors that say the same thing. Under pytest's
  ``filterwarnings = error`` the ``FutureWarning`` below is an error already, like any
  other deprecation: a ``conftest.py`` whose ``pytest_plugins`` names the old plugin, or a
  test module importing an old parser name, stops the run.

  - **The extension**, ``extensions = ["sphinxcontrib.test_reports"]``, loads the real one
    and emits a Sphinx warning of type ``test_reports.deprecated`` (Sphinx 8 and later print
    it as ``[test_reports.deprecated]``). A build run with ``-W``
    therefore FAILS on it: write ``"sphinx_test_reports"`` in ``conf.py``, or add
    ``suppress_warnings = ["test_reports.deprecated"]`` until you can. Listing both names
    loads the extension once.
  - **The pytest plugin**, ``-p sphinxcontrib.test_reports.pytest_plugin`` (and the same
    name in ``addopts``, ``PYTEST_PLUGINS`` or a ``conftest.py``'s ``pytest_plugins``),
    loads the real plugin, ``ub_test_reports.pytest_plugin``, and raises a ``FutureWarning``
    at start-up -- once per process, so
    once more for each pytest-xdist worker. A filter written against the old name --
    ``ignore::sphinxcontrib.test_reports.pytest_plugin.TestReportsConfigWarning`` -- still
    matches, because resolving it imports the alias. Change it together with the ``-p``
    line: once ``-p`` names the new module, that import happens inside pytest's own filter
    parsing, and under ``filterwarnings = error`` the alias's ``FutureWarning`` stops pytest
    with a usage error. Naming the plugin under BOTH names, in ``-p``, ``addopts`` or
    ``pytest_plugins``, stops pytest with "Plugin already registered under a different
    name"; keep one.
  - **The parsers**, ``sphinxcontrib.test_reports.junitparser`` and
    ``sphinxcontrib.test_reports.jsonparser``, are the real modules --
    ``ub_test_reports.junitparser`` and ``ub_test_reports.jsonparser`` -- under the old name,
    with a ``FutureWarning`` (once per process) that points at the ``import`` statement
    naming them -- at ``importlib`` itself when they are loaded with
    ``importlib.import_module``. Their classes, and a ``mock.patch`` target through the old
    path, are the real ones.

  The ``FutureWarning`` from a parser import, or from ``pytest_plugins`` in a
  ``conftest.py``, is silenced by ``filterwarnings = ignore::FutureWarning`` (or a narrower
  filter on its message) in the pytest configuration, ``-W ignore::FutureWarning`` on
  pytest's command line, or ``warnings.filterwarnings("ignore", category=FutureWarning)``
  in Python. The one that ``-p``, ``addopts`` or ``PYTEST_PLUGINS`` prints at start-up
  comes before pytest installs any filter, so only Python's own options reach it:
  ``PYTHONWARNINGS=ignore::FutureWarning``, which pytest-xdist's workers inherit, or
  ``python -W ignore::FutureWarning -m pytest``, which reaches the main process only. In
  every case the fix is the new name.

  **Every other** ``sphinxcontrib.test_reports.<module>`` **import breaks now**, as an
  ordinary ``ImportError`` (``ModuleNotFoundError`` for an ``import`` statement):
  ``projectconfig``, ``identity``, ``results``, the directives and the rest were never
  documented as an API. The module is the same under
  its new name -- ``sphinxcontrib.test_reports.projectconfig`` is
  ``ub_test_reports.projectconfig``, and the directives are under ``sphinx_test_reports``.

  The two ``user_properties`` names the pytest plugin reserves for its location override,
  ``sphinxcontrib.test_reports:file`` and ``sphinxcontrib.test_reports:line``, are wire
  names rather than the import path, and do not change.

- 🔧 The package builds with hatchling instead of flit, because its wheel now ships two
  top-level packages: ``sphinx_test_reports`` and the ``sphinxcontrib/test_reports/``
  aliases. ``sphinxcontrib`` stays a namespace package. The package also gains
  ``sphinx_test_reports.__version__``.

New and Improved
................

- 🔧 Sphinx-Test-Reports now lives in the Sphinx-Needs repository, as
  `packages/sphinx-test-reports <https://github.com/useblocks/sphinx-needs/tree/master/packages/sphinx-test-reports>`__.

  The whole of ``useblocks/sphinx-test-reports``' history came with it, rewritten so that
  every historical commit already places its files under that directory: ``git log`` and
  ``git blame`` read the full history there with no ``--follow``, and
  ``packages/sphinx-test-reports/design/import-commit-map.txt`` maps every hash the old
  repository had to its hash in the new one.

  - **The repository** is now https://github.com/useblocks/sphinx-needs. Pull requests and
    branches are opened there, under ``packages/sphinx-test-reports/``.
  - **Issues** move with it. New ones carry the ``pkg: sphinx-test-reports`` label, which
    the issue forms' "Package" dropdown sets.
  - **Release tags** are prefixed: ``sphinx-test-reports-v2.0.0`` rather than ``2.0.0``.
    Six of the ten historical bare names collided with existing Sphinx-Needs releases, so
    the prefix is load-bearing rather than tidy.
  - **The distribution keeps its name.** It is still ``sphinx-test-reports``, and the
    ``test-reports`` command is still the same command, now shipped by ub-test-reports,
    which it depends on. The import names do change, in this same release: see the two
    sections above.

- 🐛 A ``test-env`` directive written with ``:raw:`` and ``:env:`` but no ``:data:`` raised
  ``TypeError`` instead of rendering: that branch iterated the data-option list outside the
  guard its sibling branch keeps it inside.

- 👌 The error node for a missing test file no longer passes a second argument to
  ``docutils``' ``Text()``. That argument (``rawsource``) is ignored, deprecated, and due to
  be removed in Docutils 2.0; on every docutils this package supports it still works, so
  this was never a visible bug -- only a ``DeprecationWarning`` on each missing-file error.

- 🐛 A directive written without a ``:file:`` option raised an unhandled ``TypeError``
  instead of a readable error. The check that was meant to catch it could never run: it sat
  two lines below a slice of the missing value, which raised first. It now raises
  ``TestReportFileNotSetError`` like every other configuration mistake.

- ⬆️ The extension now requires docutils 0.21 or newer, as a dependency, the floor the whole
  Sphinx-Needs workspace declares and type-checks against (previously whatever Sphinx
  accepted, which is 0.20 for Sphinx 7.4 through 9.0). The ``test-reports`` command and the
  pytest plugin, which are ub-test-reports, install no docutils at all.

- ♻️ The ``ubproject.toml`` reader is now `ub-project <https://pypi.org/project/ub-project/>`__,
  the shared reader every useblocks tool uses for the file, and a runtime dependency of
  ub-test-reports, where the ``[test_reports]`` model now lives (standard library only, so
  the ``test-reports`` command and the pytest plugin still run without Sphinx). Nothing changes in behaviour: the walk up to the repository root, the
  anchoring of relative paths at the file's directory and every message are as before. One
  failure that used to escape as a traceback is now reported like the others: a file that
  is not UTF-8 is a configuration error naming the file.

Fixed
.....

- 🐛 ``tr_link`` no longer fails with ``'NoneType' object has no attribute 'split'`` on the
  usage the documentation shows, ``:links: [[tr_link('classname', 'title')]]``: every need
  carries the test fields, and on a need that is not a test-case the compared field --
  ``classname`` in the documented call -- has no value, so the old presence check never
  fired. The function now checks the value rather than the field's presence -- on the need
  it is called for and on each candidate target. Such a need gets no links, and a ``-W``
  build no longer fails.
  `#1949 <https://github.com/useblocks/sphinx-needs/issues/1949>`__,
  `#2117 <https://github.com/useblocks/sphinx-needs/pull/2117>`__

- 🐛 A ``test-file`` expanded with ``:auto_suites:`` / ``:auto_cases:`` lost its parent
  links when its ``:links:`` merely *contained* its id: with ``:id: TF_1`` and
  ``:links: TF_10``, no suite linked ``TF_1`` and no case linked it either, because the
  "already linked" check was a substring test (the same for a suite's id in its cases'
  links). The check now compares whole link ids, so ordinary numbering schemes keep the
  file → suite → case links; a ``:links:`` that shares no such prefix is unchanged.
  `#2114 <https://github.com/useblocks/sphinx-needs/issues/2114>`__,
  `#2118 <https://github.com/useblocks/sphinx-needs/pull/2118>`__

- 🐛 ``test-report`` inserted its body into the generated ``test-file`` as a Python list:
  the need's content read ``['First line.', 'Second line.']``. The body is now the
  ``test-file``'s content line for line, each line at the indentation the template gives
  ``{content}`` -- so a body of several lines stays inside the generated directive in a
  custom template too.
  `#2051 <https://github.com/useblocks/sphinx-needs/issues/2051>`__,
  `#2125 <https://github.com/useblocks/sphinx-needs/pull/2125>`__

- 🐛 ``test-report`` handed the generated ``test-file`` the RESOLVED, absolute report path,
  so the report-path field (``file``, or the name ``tr_file_option`` gives it) of a
  ``test-report``'s file, suites and cases differed from every other ``test-file``'s and
  from one machine to the next. ``{file}`` is now the ``:file:`` option as written, which
  the ``test-file`` resolves against ``tr_rootdir`` exactly as the ``test-report`` did. The
  template's *Test file* line shows that value too.
  `#2051 <https://github.com/useblocks/sphinx-needs/issues/2051>`__,
  `#2125 <https://github.com/useblocks/sphinx-needs/pull/2125>`__

- 🐛 The shipped default ``tr_report_template`` no longer ends with a *Template* section.
  That section ``literalinclude``\ d the template itself by a path only this package's own
  documentation could resolve, so in every other project each ``test-report`` warned
  ``Include file ... not found or reading it failed`` (failing a ``-W`` build) and
  published a *Template* heading and its one sentence with no template under them.
  **This removes output**: the section never rendered whole outside this repository, and
  the template's source is now shown on the ``test-report`` documentation page instead. A
  project that copied the template to work around it keeps its copy; it can delete the
  section there, or go back to the default.
  `#1932 <https://github.com/useblocks/sphinx-needs/issues/1932>`__,
  `#2125 <https://github.com/useblocks/sphinx-needs/pull/2125>`__

- 🐛 ``test-results`` and ``test-env`` make each suite / environment a real section now,
  one level below the section the directive stands in: its heading is one level deeper
  than before (an ``<h4>`` under an ``<h3>`` heading, where it was a second ``<h3>``), it
  has an id and a permalink of its own, and ``.. contents::`` and the sidebar list it.
  Before, the heading was a stray title of the enclosing section, at that section's level
  and with that section's permalink, and either directive written inside a list item
  failed the HTML build with ``AssertionError``. Text written after the directive in the
  same section now follows the last generated section -- in a PDF (LaTeX) it is part of
  it -- so write the directive at the end of its section, or give the text that follows a
  heading of its own.

  **This can fail a** ``-W`` **build** where a suite or environment is named like a
  heading on the same page: the name is ambiguous then, and a ```Name`_`` reference to
  either is docutils' ``ERROR: Duplicate target name, cannot be used as a unique
  reference``. Under ``sphinx.ext.autosectionlabel`` the generated sections are labelled
  like authored ones, so such a name is a duplicate label -- across the whole project
  without ``autosectionlabel_prefix_document`` -- and a ``:ref:`` to it may land on the
  generated section (autosectionlabel keeps the last one read). Rename the heading, set
  ``autosectionlabel_prefix_document``, or give the heading an explicit label and
  reference that. Two suites named alike on one page are two sections with distinct ids;
  docutils reports that duplicate at INFO level, which leaves ``-W`` green only while
  nothing references the name.
  `#1959 <https://github.com/useblocks/sphinx-needs/issues/1959>`__,
  `#NNNN <https://github.com/useblocks/sphinx-needs/pull/NNNN>`__

What the move costs, stated rather than left to the CI diff
............................................................

- **Sphinx-Needs is now tested at ONE version, not five.** The retired ``noxfile.py`` ran the
  suite against Sphinx-Needs 6.0.1, 6.3.0, 7.0.0, 8.0.0 and 8.5.0; in the workspace the
  suite runs against the sibling in the tree, across Sphinx 7.4, 8.2 and 9.1 instead. With
  it, **the declared floor narrows from** ``sphinx-needs>=6.0.1`` **to**
  ``sphinx-needs>=8.5.0,<9`` (and from ``>=6`` in ``docs``). That is
  the workspace's tight-tracking policy for a dependency on a sibling, and it is enforced;
  it means this release supports a narrower range of Sphinx-Needs than 2.0.0 did.
- **Five ruff rule families are no longer enforced here** -- ``FURB``, ``PERF``, ``PGH``,
  ``PIE`` and ``SLF`` -- because the workspace has one shared rule set and they are not in
  it. All five were at zero violations, so nothing changed in the code; what changed is that
  a new violation would no longer be caught.
- **Both retired nox lanes have CI jobs**, now that the plugin is ub-test-reports': the
  ``toolchain_free`` lane is a job that installs ub-test-reports with no documentation
  toolchain at all, asserts it, and runs that package's whole suite; the ``plugin_floor``
  lane runs the same suite on pytest 7.0.1 (Python 3.11) and 7.3.2 (Python 3.12).
- **mypy is replaced by ty**, which checks the whole package -- the mypy configuration
  excluded fifteen modules.
- **Beyond those five families, four rules this package enabled are now ignored**
  (``B904``, ``ICN001``, ``ISC004``, ``N818``) because the shared set ignores them. All
  four are at zero violations, so nothing in the code changed.
- **The documentation is no longer link-checked.** The retired CI ran ``linkcheck``; the
  workspace's link-check job is scoped to Sphinx-Needs' own documentation. Tracked as a
  follow-up.
- **Three formatting hooks retired with the old pre-commit configuration**:
  ``end-of-file-fixer``, ``trailing-whitespace`` and ``pretty-format-json``.

.. _`release:2.0.0`:

2.0.0
-----
:Released: 11.09.2026

A major release. ``pip install sphinx-test-reports`` no longer installs Sphinx
and Sphinx-Needs, Python 3.10 is no longer supported, Sphinx-Needs 6.0.1 and
Sphinx 7.4 are the oldest supported versions, and a failed test case's
``result`` is spelled ``failed`` rather than ``failure``. What the bare package
gains in return is a life outside a documentation build: a ``test-reports``
command that turns test-result XML into a ``needs.json`` without running
Sphinx, and a pytest plugin that writes the XML shape this extension reads. A
project can also be described once, declaratively, in the ``[test_reports]``
section of ``ubproject.toml`` instead of being restated in ``conf.py``.

Upgrading a documentation project means adding the extra to its install line:
``pip install "sphinx-test-reports[sphinx]"``. Beyond that, only a project that
names the old ``failure`` result has to change anything: a filter on the value,
a custom ``tr_report_template`` copied from the shipped one, and custom CSS on
the ``tr_failure`` class.

* Breaking: ``pip install sphinx-test-reports`` no longer installs Sphinx and
  Sphinx-Needs. They are the new ``sphinx`` extra, so the install line of a
  documentation project becomes ``pip install "sphinx-test-reports[sphinx]"``.
  The bare package brings only ``lxml``, the dependency of the ``test-reports``
  command, which runs in test runners and build actions that have no
  documentation toolchain; the pytest plugin, the ``pytest`` extra, runs there
  too. An extra is opt-in, so the extension now checks the installed toolchain
  against the versions the extra declares when Sphinx loads it: a missing or
  older Sphinx or Sphinx-Needs stops the build with a message naming the
  install line, instead of a traceback from inside a directive.
  `#159 <https://github.com/useblocks/sphinx-test-reports/pull/159>`_
* Breaking: Python 3.10 is no longer supported. It reached the end of upstream
  support, and dropping it lets the package read TOML with ``tomllib`` from the
  standard library instead of carrying a backport.
  `#147 <https://github.com/useblocks/sphinx-test-reports/pull/147>`_
* Breaking: sphinx-needs 6.0.1 and Sphinx 7.4 are the oldest supported
  versions. 6.0.1 is the first release whose ``add_extra_option`` takes a
  schema, which this extension registers its fields with; sphinx-needs 6 itself
  requires Sphinx 7.4. The compatibility branches for older releases are gone.
  `#150 <https://github.com/useblocks/sphinx-test-reports/pull/150>`_
* Breaking: a failed test case now carries the ``result`` value ``failed``
  instead of ``failure``, so that every state is spelled the same way -- as a
  participle, like the ``passed``, ``skipped`` and ``disabled`` beside it, and
  like the ``failed`` count on a test-file and test-suite need. ``failure`` was
  never a chosen name: it was the name of the JUnit ``<failure>`` element,
  passed through by the parser. The full vocabulary is now ``passed``,
  ``failed``, ``error``, ``skipped``, ``disabled``; ``error`` is unchanged,
  because it agrees with the ``errors`` count beside it. **Three things in a
  project have to be updated:** a filter naming the value
  (``'failure' == result`` becomes ``'failed' == result``), a custom
  ``tr_report_template``, which contains two such filters in the shipped
  template it was copied from, and custom CSS targeting the generated
  ``tr_failure`` class, which is now ``tr_failed`` (the stylesheet still
  carries rules for both, so the colours survive either way). The value is also
  what ``test-reports build needs`` writes into ``needs.json``, so a consumer
  of that file -- a schema, a metamodel validator -- has to be updated with it.
  `#161 <https://github.com/useblocks/sphinx-test-reports/pull/161>`_
* Feature: New ``test-reports build needs`` command line interface, converting
  test-result XML into a ``needs.json`` without running Sphinx, so the
  conversion can run as a cacheable build action and the documentation build
  only imports the result. Its settings come from the
  ``[test_reports.build.needs]`` table of ``ubproject.toml``, with flags for
  per-invocation overrides. See :ref:`cli`.
  `#148 <https://github.com/useblocks/sphinx-test-reports/pull/148>`_
* Feature: A pytest plugin (``-p sphinxcontrib.test_reports.pytest_plugin``)
  gives every test case the source location an editor shows -- pytest's
  ``file``/``line`` counted from 1, Bazel's runfiles prefix cut, a runtime
  override for file-driven tests -- and requirement-link ``<properties>`` from
  an ``add_test_properties`` decorator or an ``apply_test_metadata`` runtime
  helper, for cases skipped at setup and under pytest-xdist too. Which
  properties exist, their XML names and which take lists is the
  ``test_reports_properties`` pytest ini option; S-CORE's model, which the
  plugin was ported from, is the documented example. The plugin is the
  ``pytest`` extra: ``pip install "sphinx-test-reports[pytest]"`` installs it
  and pytest, without the documentation toolchain. See :ref:`pytest_plugin`.
  `#151 <https://github.com/useblocks/sphinx-test-reports/pull/151>`_
* Feature: Declarative configuration in the ``[test_reports]`` section of
  ``ubproject.toml``, the file shared with the other useblocks tooling, so a
  project is described once instead of being restated in ``conf.py``. The file
  is searched for upwards from the ``confdir``, stopping at the repository
  root; the new ``tr_config_from_toml`` names or disables it. Precedence is
  ``-D`` > ``ubproject.toml`` > ``conf.py`` > default. See
  :ref:`tr_config_from_toml`.
  `#145 <https://github.com/useblocks/sphinx-test-reports/pull/145>`_
* Feature: The produced ``needs.json`` declares every field it uses in a
  ``needs_schema``, as Sphinx-Needs does for the files a build writes, so a
  consumer can read the type of a field from the artifact instead of from a
  Sphinx build with the extension loaded. The declarations and the fields the
  extension registers come from one table, so the two cannot drift apart.
  `#148 <https://github.com/useblocks/sphinx-test-reports/pull/148>`_
* Feature: Support the googletest XML dialect: ``status="notrun"`` is reported
  as ``disabled`` instead of ``passed``, all ``<failure>``/``<skipped>`` parts
  of a test case are kept instead of only the first, ``RecordProperty`` values
  in attribute form are read (on ``<testcase>`` for googletest < 1.8.1 and on
  ``<testsuite>`` for suite-level properties up to 1.15.x), and ``timestamp``,
  ``value_param`` and ``type_param`` are parsed. ``<system-err>`` is captured.
  `#141 <https://github.com/useblocks/sphinx-test-reports/pull/141>`_
* Feature: The source location of a test case is available as Sphinx-Needs
  fields, configurable via the new ``tr_source_file_option`` and
  ``tr_source_line_option``.
  `#142 <https://github.com/useblocks/sphinx-test-reports/pull/142>`_
* Feature: New ``tr_deterministic_case_ids`` option derives test-case IDs from
  the source location instead of the need content, so an ID no longer changes
  when a test starts failing differently.
  `#143 <https://github.com/useblocks/sphinx-test-reports/pull/143>`_
* Improvement: both parsers now map their input onto the one ``result``
  vocabulary instead of each passing its own through, so a JSON report written
  against the JUnit dialect no longer produces a different ``result`` than the
  XML it mirrors. A state this package does not know is still passed through
  untouched, so a ``tr_json_mapping`` pointing at a report with a vocabulary of
  its own keeps working.
  `#161 <https://github.com/useblocks/sphinx-test-reports/pull/161>`_
* Bugfix: ``tr_file_option`` is now honoured by the directives, not only by the
  field registration. Renaming the field previously produced needs carrying an
  unregistered field.
  `#142 <https://github.com/useblocks/sphinx-test-reports/pull/142>`_
* Bugfix: ``tr_file_option``, ``tr_source_file_option`` and
  ``tr_source_line_option`` may no longer name a fixed field such as ``case``
  or ``result``, in ``conf.py`` or in the declarative file. The build
  previously stopped with a bare ``TypeError`` from inside a directive.
  `#148 <https://github.com/useblocks/sphinx-test-reports/pull/148>`_
* Support: ``result_text`` and ``remote_url`` are registered as need fields by
  the extension, so a ``needs.json`` the ``build needs`` command produced
  imports without dropping them. A project that registered ``remote_url``
  itself keeps its own registration.
  `#148 <https://github.com/useblocks/sphinx-test-reports/pull/148>`_
* Support: ``packaging`` is no longer a runtime dependency. The last import of
  it under ``sphinxcontrib/`` is gone, so the ``docs`` and ``test`` extras,
  whose ``conf.py`` files still use it, declare it instead.
  `#154 <https://github.com/useblocks/sphinx-test-reports/pull/154>`_
* Testing: CI installs the package with the ``pytest`` extra alone and runs the
  converter's and the pytest plugin's tests without Sphinx -- on the newest
  pytest and on the oldest the plugin supports -- so a toolchain import
  creeping into either import chain, or Sphinx creeping back into a dependency
  list, fails the build.
  `#159 <https://github.com/useblocks/sphinx-test-reports/pull/159>`_
* Testing: Run the test suite against sphinx-needs 8.5.0. The matrix
  previously topped out at 8.0.0, so the release a fresh install resolves to
  was untested.
  `#158 <https://github.com/useblocks/sphinx-test-reports/pull/158>`_
* Known: Sphinx 9 renders a configuration error raised from the declarative
  file -- a wrong type, a rename onto a fixed field, a disagreeing need type
  -- as its crash report rather than as a one-line message; the message is in
  the report. A typo in ``[test_reports.build.needs]`` is reported the same
  way, and so is a missing or outdated toolchain refused when the extension
  loads.
  `#148 <https://github.com/useblocks/sphinx-test-reports/pull/148>`_

.. _`release:1.4.0`:

1.4.0
-----
:Released: 16.06.2026

This release adds Sphinx-Needs 8 support and the ability to map JUnit XML
``<properties>`` onto Sphinx-Needs fields and links. It also registers every
field that Sphinx-Test-Reports adds with a typed schema, so unset fields no
longer trigger false-positive ``unevaluatedProperties: false`` schema-validation
warnings, and it fixes JUnit ``<error>`` test cases being reported as passed.

* Feature: Map JUnit XML ``<properties>`` to Sphinx-Needs fields and links via
  the new ``tr_property_link_types`` and ``tr_extra_options`` options.
  `#135 <https://github.com/useblocks/sphinx-test-reports/pull/135>`_
* Improvement: Support Sphinx-Needs 8 by registering fields through the new
  ``add_field`` API, falling back to ``add_extra_option`` on older versions.
  `#133 <https://github.com/useblocks/sphinx-test-reports/pull/133>`_
* Bugfix: Register ``file``, ``suite``, ``case``, ``case_name``,
  ``case_parameter`` and ``classname`` with a typed (string) schema so they
  default to an unset/``None`` value and are stripped before schema validation.
  Previously they were registered untyped and defaulted to ``""``, which caused
  false-positive ``Unevaluated properties are not allowed`` warnings on needs
  that did not set them when a schema used ``unevaluatedProperties: false``.
  `#133 <https://github.com/useblocks/sphinx-test-reports/pull/133>`_
* Bugfix: Handle the JUnit ``<error>`` result state in ``parse_testcase()``;
  ``<error>`` test cases were previously misclassified as ``passed``.
  `#134 <https://github.com/useblocks/sphinx-test-reports/pull/134>`_
* Testing: Run the test suite against Sphinx-Needs 6.3.0.
  `#130 <https://github.com/useblocks/sphinx-test-reports/pull/130>`_
* Testing: Add a regression test that a strict schema ignores unpopulated
  Sphinx-Test-Reports fields.
  `#137 <https://github.com/useblocks/sphinx-test-reports/pull/137>`_
* Docs: Clarify the Sphinx-Needs type names (``testfile``, ``testsuite``,
  ``testcase``) versus the hyphenated directives.
  `#136 <https://github.com/useblocks/sphinx-test-reports/pull/136>`_
* Docs: Note that numeric ``cases`` filtering requires Sphinx-Needs >= 6.
  `#139 <https://github.com/useblocks/sphinx-test-reports/pull/139>`_

.. _`release:1.3.2`:

1.3.2
-----
:Released: 13.11.2025

This release improves Sphinx-Test-Reports compatibility with Sphinx and
fixes some Sphinx related deprecation warnings.

* Bugfix: Fix deprecation warnings with Sphinx 8.
  `#128 <https://github.com/useblocks/sphinx-test-reports/pull/128>`_

.. _`release:1.3.1`:

1.3.1
-----
:Released: 02.10.2025
:Full Changelog: `v1.3.0...v1.3.1 <https://github.com/useblocks/sphinx-test-reports/compare/1.3.0...ac4d771777b0af46919acf31f7cd34178d0b46d5>`__

* Support Sphinx-Needs 6 schema validation
  `#122 <https://github.com/useblocks/sphinx-test-reports/pull/122>`_

1.3.0
-----
:Released: 28.09.2025

This release makes Sphinx-Test-Reports compatible with Sphinx-Needs 5.1 and
introduces several maintenance improvements.

* Improvement: Support for Sphinx-Needs 5.1.
  `#119 <https://github.com/useblocks/sphinx-test-reports/pull/119>`_
* Bugfix: Fix plantuml on RTD.
  `#115 <https://github.com/useblocks/sphinx-test-reports/pull/115>`_
* Maintenance: Removed py38 from classifiers.
  `#116 <https://github.com/useblocks/sphinx-test-reports/pull/116>`_
* Maintenance: Activate mypy.
  `#113 <https://github.com/useblocks/sphinx-test-reports/pull/113>`_
* Maintenance: Remove baumpfleger.
  `#112 <https://github.com/useblocks/sphinx-test-reports/pull/112>`_
* Maintenance: Clean makefile.
  `#111 <https://github.com/useblocks/sphinx-test-reports/pull/111>`_
* Maintenance: Use flit.
  `#110 <https://github.com/useblocks/sphinx-test-reports/pull/110>`_
* Maintenance: Added all_good job.
  `#109 <https://github.com/useblocks/sphinx-test-reports/pull/109>`_
* Maintenance: Add standard hooks.
  `#106 <https://github.com/useblocks/sphinx-test-reports/pull/106>`_
* Maintenance: Add yamlfmt.
  `#105 <https://github.com/useblocks/sphinx-test-reports/pull/105>`_
* Maintenance: Introduce ruff.
  `#104 <https://github.com/useblocks/sphinx-test-reports/pull/104>`_
* Maintenance: Add taplo pre-commit.
  `#103 <https://github.com/useblocks/sphinx-test-reports/pull/103>`_


1.2.0
-----
:Released: 27.03.2025

* Improvement: Introducing :ref:`tr_extra_options` for setting custom options in all derrived
  test-cases from ``test-file`` and co.
  `#96 <https://github.com/useblocks/sphinx-test-reports/issues/96>`_
* Improvement: JSON-Parser allows to set custom options in test-cases, like ``status`` or even ``id``.
  See :ref:`tr_json_mapping` for examples. `#99 <https://github.com/useblocks/sphinx-test-reports/issues/99>`_

1.1.0
-----
:Released: 17.01.2025

* Bugfix: Compatible with Sphinx-Needs >= 4.0.
* Bugfix: Path handling is os independent.
* Improvement: Referenced target_option in `tr_link` can contain a comma separated list.
* Improvement: The new :ref:`json_parser` is introduced.
* Improvement: Template file encoding could be configured. See :ref:`tr_import_encoding`.
  `#60 <https://github.com/useblocks/sphinx-test-reports/issues/60>`_
*  Improvement: Supporting JSON files containing test results: :ref:`json_parser`.
*  Improvement: Implemented :ref:`tr_json_mapping` config option for JSON mapping.

1.0.2
-----
:Released: 21.12.2022 🎄

* Bugfix: Links in `test-suite` and co. do not raise error.
  `#51 <https://github.com/useblocks/sphinx-test-reports/issues/51>`_
* Improvement: Allows empty text and message fields, which allows integration of ctest junit files
  `#49 <https://github.com/useblocks/sphinx-test-reports/issues/49>`_

1.0.1
-----
:Released: 04.11.2022

* Improvement: ID length can be configured to avoid conflicts. See :ref:`tr_suite_id_length` and :ref:`tr_case_id_length`.
  `#45 <https://github.com/useblocks/sphinx-test-reports/issues/45>`_
* Bugfix: Multiple testsuites get documented correctly.
  `#40 <https://github.com/useblocks/sphinx-test-reports/issues/40>`_

1.0.0
-----
:Released: 26.09.2022

* Improvement: Supporting `Sphinx-Needs <https://sphinx-needs.readthedocs.io/en/latest/>`__ ``>= 1.01`` only.
* Improvement: Migrated nosetests to pytest.

0.3.7
-----
:Released: 09.06.2022

* Improvement: Nested test suites are supported (like in Robot Framework 5.0)
  `#30 <https://github.com/useblocks/sphinx-test-reports/issues/30>`_

0.3.6
-----
:Released: 12.11.2021

* Improvement: Added support for parallel modes.
  `#20 <https://github.com/useblocks/sphinx-test-reports/issues/20>`_
* Improvement: Support getting skipped tests.
  `#18 <https://github.com/useblocks/sphinx-test-reports/issues/18>`_

0.3.5
-----
:Released: 18.06.2021

* Bugfix: Minor bugfixes

0.3.4
-----
:Released: 30.04.2021 (Recalled, contains major bugs)

* Bugfix: Removed Sphinx 4 deprecation warnings

0.3.3
-----
* Improvement: Added :ref:`test-report` directive.
* Improvement: Introduces :ref:`tr_file`, :ref:`tr_suite` and :ref:`tr_case` options to customize names.
* Improvement: Not found files will throw warning instead of exception so that build goes on.
* Improvement: Provides css_classes ``tr_passed``, ``tr_failure``, ``tr_skipped`` to colorize needs and their rows in tables.
* Bugfix: Stabilised extension initialisation phase.


0.3.1
-----
* Improvement: Support of case and table colors based on ``result``.
* Bugfix: Hash-Id for autogenerated test-cases size was increased.


0.3.0
-----
* Improvement: Using `sphinx-needs <https://sphinx-needs.readthedocs.io/en/latest/>`_ for data representation
  and filtering.
* Improvement: New directives :ref:`test-file`, :ref:`test-suite` and :ref:`test-case`.
* Improvement: New possibilities to :ref:`filter test data <filter>`.
* Improvement: Much better documentation.

0.2.1
-----
* Skipped support für Python < 3.5.
* Bugfix: junit-file-format of pytest > 5.1.0 supported. `#8 <https://github.com/useblocks/sphinx-test-reports/issues/8>`_


0.2.0
-----

**Initial start for the changelog**

* Improvement: added directive ``:test-env:`` to take tox-envreport.json as input and create a table.
