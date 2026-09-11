.. _cli:

Command line interface
======================
.. versionadded:: 1.5.0

``Sphinx-Test-Reports`` ships a ``test-reports`` command that converts
test-result XML into a ``needs.json`` **without running Sphinx**.

Why this exists: parsing test results inside a documentation build couples the
two, so results cannot be converted without building docs, the conversion cannot
be cached by a build system, and the data is unavailable to anything else. The
CLI splits the computation out; the documentation build only imports the result.

The command imports no Sphinx code at all, so it can run as a build action in an
environment that has no documentation toolchain installed. Installed as
``pip install sphinx-test-reports`` -- without the ``sphinx`` extra the
:doc:`extension needs </install>` -- the package brings a single dependency,
``lxml``.

Converting a report
-------------------

.. code-block:: bash

   test-reports build needs bazel-testlogs/my_target/test.xml --output needs.json

Several reports can be converted into one file -- a build system typically
passes them as a file list:

.. code-block:: bash

   test-reports build needs report_a.xml report_b.xml --output needs.json

Every test case must be unique across the given reports. A case's ID is derived
from where the test is, so the same case twice -- typically the same report
given twice -- would collapse into one need; the command refuses that with an
error naming the affected IDs rather than writing a valid-looking file that has
lost evidence.

Each test case becomes one need shaped exactly like the need the build's
``test-case`` directive creates for it: titled with the case name; ``suite``,
``case``, ``case_name``, ``case_parameter``, ``classname``, ``result`` (spelled
as the build spells it -- ``passed``, ``failed``, ``error``, ``skipped``,
``disabled`` -- so one filter matches imported and local cases alike) and
``time``; the report path under ``file``; the test's source location under
``case_file`` and ``case_line``; a one-line ``result_text``; and the full
failure evidence (every ``<failure>``/``<skipped>`` part plus captured output)
in the need content.

The three renameable fields carry the names the build's ``tr_file_option``,
``tr_source_file_option`` and ``tr_source_line_option`` select -- the converter
reads them from the same ``[test_reports]`` section (:ref:`tr_config_from_toml`),
so a project that spells its source location ``file``/``line`` gets a
``needs.json`` that says so too. That section is the only place it can read
them from: a rename made in ``conf.py`` alone is invisible to the converter,
which then writes the default names -- ``needimport`` drops ``case_file`` and
``case_line`` as unknown keys, and the report path lands in ``file``, the field
such a project defines as the *source* file. Renames belong in
``ubproject.toml``. None of the three may take the name of a fixed field
(``case``, ``result``, ...); both consumers refuse such a configuration, since
the field would be written twice.

Every field is declared in the file, under ``versions.<version>.needs_schema``,
the way Sphinx-Needs declares the fields of the ``needs.json`` a build writes:
its JSON type, a description, and whether it is a core field, a registered
field or a link field. Configured ``extra_options`` and mapped link fields are
declared whether or not a case populated them -- the block describes the
format, not the one report at hand. So a consumer that never runs Sphinx (a
schema check, a metamodel validator) can read the type of every field from the
artifact:

.. code-block:: json

   "time": {
     "type": ["string", "null"],
     "description": "Test execution time, in seconds",
     "field_type": "extra",
     "default": null
   }

The declarations and the fields the extension registers with Sphinx-Needs come
from one table, so a field cannot be typed one way in the file and another way
in the build. ``time`` is declared a string because that is what the build's
``test-case`` directive writes; turning it into a number is
`#156 <https://github.com/useblocks/sphinx-test-reports/issues/156>`__.

Consuming the result
--------------------

The output is a schema-conform ``needs.json``, so it can be imported as local
needs:

.. code-block:: rst

   .. needimport:: needs.json

or mounted as external needs via ``needs_external_needs`` in ``conf.py``.

Importing needs sphinx-needs 4 or newer: older versions read the need text
from a ``description`` key, the converter writes ``content`` like every version
since. Two things a build has to allow for. The IDs are lowercase
(``testcase__MathTest__Addition_hcuyy``), the scheme S-CORE's tooling uses, and
sphinx-needs' default ``needs_id_regex`` accepts capitals only -- widen it, e.g.
``needs_id_regex = "^[A-Za-z0-9_]{5,}"``, or every import is refused (see also
``tr_deterministic_case_ids`` in :ref:`configuration`). And a link field
created with ``--link-property`` has to exist as a link type (``needs_links``;
``needs_extra_links`` before sphinx-needs 6.3), as for any need. The plain
fields the converter adds
beyond the directive's (``result_text``, ``remote_url``) are registered by the
extension, so ``needimport`` keeps them.

Every need carries the synthesized source URL twice: as ``external_url``, which
Sphinx-Needs uses when rendering a link to an external need, and as a plain
``remote_url`` field, so needs imported as *local* needs keep a clickable link
through a ``needs_string_links`` entry.

Linking test cases to requirements
----------------------------------

An XML ``<property>`` becomes a need field under its own name when it is listed
in the ``extra_options`` of the ``[test_reports]`` section -- the same list that
makes the build register the field and accept it, so an import never has to drop
it as an unknown key -- or given with ``--extra-option NAME``. Properties named
by neither are left out, and the command says which, once. A listed property is
written for every case -- ``null`` where a case has no such property, as the
build leaves a field a directive did not set -- so a schema can require it.
``--extra-option`` adds to the section's list rather than replacing it
(``--no-config`` leaves the file out); a name that list does not contain is
reported, because the build registers exactly the listed fields and
``needimport`` drops every other one. To turn a property into a link field
instead, map it -- the value is split on commas:

.. code-block:: bash

   test-reports build needs test.xml --output needs.json \
       --link-property PartiallyVerifies=partially_verifies \
       --link-property FullyVerifies=fully_verifies

Mapped link fields are written even when a case has no such property, so a schema
can require them. A test run that names its link properties
``PartiallyVerifies`` and ``FullyVerifies`` is configured as

.. code-block:: toml

   [test_reports.build.needs]
   link_properties = { PartiallyVerifies = "partially_verifies", FullyVerifies = "fully_verifies" }

and lists ``TestType`` and ``DerivationTechnique`` in ``extra_options``.

A property whose name is already taken by a built-in field (``result``,
``file``, ``time``, ...) or by a mapped link field is not exported: the built-in
value wins, and the command says so on stderr, once. Rename the property, or map
it to a link field, to get it into the need.

Source links
------------

Source URLs need both a repository and a commit; they are refused separately,
because half the metadata cannot produce a URL:

.. code-block:: bash

   test-reports build needs test.xml --output needs.json \
       --remote-url git@github.com:org/repo.git \
       --commit "$(git rev-parse HEAD)"

Git remotes are accepted in ``scp`` form and normalised, and credentials are
stripped -- ``https://gitlab-ci-token:TOKEN@gitlab.example/org/repo.git`` is
what GitLab's ``CI_REPOSITORY_URL`` looks like, and the base is written into
every need. Without this metadata -- as in a hermetic sandbox -- the URL fields
stay empty rather than carrying a placeholder that looks real and then 404s.

Forges that lay out blob URLs differently are handled with ``--url-pattern``,
which accepts the placeholders ``{base}``, ``{commit}``, ``{file}`` and
``{line}``:

.. code-block:: bash

   test-reports build needs test.xml --output needs.json \
       --remote-url https://gitlab.com/org/repo --commit abc123 \
       --url-pattern "{base}/-/blob/{commit}/{file}#L{line}"

The template is checked before any report is read: an unknown placeholder, an
attribute lookup such as ``{base.x}`` or an unbalanced brace is a configuration
error naming the problem, not a traceback on the first case that happens to
carry a file.

.. _cli-declarative:

Declarative configuration
-------------------------

None of the settings above has to be spelled as a flag. The command reads the
``[test_reports.build.needs]`` table of ``ubproject.toml`` -- the same declarative
file the documentation build reads (see :ref:`tr_config_from_toml`), so the two
consumers of a project never work from different descriptions of it. By default
the file is searched for in the working directory and its parents, stopping at
the repository root (the directory holding ``.git``) or, outside a repository,
at the directory holding ``pyproject.toml``. An absent default file is not an
error. A found one is named on stderr: it may sit directories above the
invocation, and the output depends on it.

.. code-block:: toml

   [test_reports.build.needs]
   project = "My Project"
   version = "2.0"
   need_type = "testcase"
   tags = ["ci", "unit"]
   link_properties = { PartiallyVerifies = "partially_verifies" }
   remote_url = "https://github.com/org/repo"
   url_pattern = "{base}/blob/{commit}/{file}#L{line}"

.. code-block:: bash

   test-reports build needs bazel-testlogs/my_target/test.xml --output needs.json \
       --commit "$(git rev-parse HEAD)"

**Precedence** is flag > table > built-in default. A flag given alongside the
file overrides that key -- the natural home for per-invocation values such as
the commit a CI job is converting for. ``--link-property``, given at all,
replaces the whole ``link_properties`` table. ``--config PATH`` reads a
different file (used as-is, not searched for, and it must exist);
``--no-config`` ignores declarative configuration entirely, so the output
depends only on the arguments given. A run without a file is quiet by default
-- most projects have none -- but ``-v`` says where the search ended and why,
so a misplaced file can be placed right, and names a ``--config`` file; the
Sphinx build says the same at ``sphinx-build -v``.

**Validation** follows the file's own policy: a known key with the wrong type
stops the conversion with an error, an unknown key is reported on stderr and
ignored. The whole ``[test_reports]`` section is validated, not only the
``build.needs`` table, so the converter refuses exactly the files the build
would refuse.

``need_type`` and the ``type`` of the build's ``case`` entry both name the need
type of a test case, so they must agree: a ``needs.json`` written with one type
is neither registered nor cross-linked by a build configured with the other. The
rule holds for the *merged* value -- a ``--need-type`` flag, or the built-in
default, disagreeing with the file's ``case`` is refused just like a
disagreeing ``need_type`` in the file.

Reproducible output
-------------------

The written file is byte-stable: keys are sorted and no timestamp is recorded.
Converting the same report twice produces identical bytes, so the output works as
a cached build-action output and as diffable evidence.

Empty reports
-------------

A report without a single test case adds no needs, and the command says so on
stderr. A file that is not a test report at all -- a ``pom.xml``, a
``coverage.xml`` given by mistake -- parses as one empty suite, so a valid,
empty ``needs.json`` with exit code 0 would otherwise be the silent outcome of
exactly the mistake a cached build action needs to hear about.

Missing source locations
------------------------

If no test case in a report carries a ``line`` attribute, the command says so on
stderr. The usual cause is pytest's default ``junit_family = xunit2``, which
filters ``file`` and ``line`` off ``<testcase>``; ``xunit1`` (or ``legacy``)
emits them -- and only through the ``record_xml_attribute`` fixture, which a
stock run never calls. A test run therefore has to set ``junit_family`` and
write the attributes itself for the source location to reach the needs.

All options
-----------

.. code-block:: text

   test-reports build needs FILE [FILE ...] --output PATH
                            [--config PATH | --no-config] [-v]
                        [--project NAME] [--version KEY]
                        [--need-type TYPE] [--tags TAGS]
                        [--extra-option NAME] [--link-property PROPERTY=LINK_FIELD]
                        [--remote-url URL] [--commit COMMITISH]
                        [--url-pattern PATTERN]

``--project`` and ``--version`` fill the ``needs.json`` envelope;
``--need-type`` (default ``testcase``) sets the need type and the ID prefix;
``--tags`` is a comma-separated list applied to every created need. Every one
of these can also come from ``[test_reports.build.needs]`` in ``ubproject.toml``;
a flag wins.
