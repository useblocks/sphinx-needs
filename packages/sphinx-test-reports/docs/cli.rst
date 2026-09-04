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
environment that has no documentation toolchain installed.

Converting a report
-------------------

.. code-block:: bash

   test-reports convert bazel-testlogs/my_target/test.xml --output needs.json

Several reports can be converted into one file -- a build system typically
passes them as a file list:

.. code-block:: bash

   test-reports convert report_a.xml report_b.xml --output needs.json

Each test case becomes one need, with the source location under the ``file`` and
``line`` fields, the result under ``result``, a one-line ``result_text``, and the
full failure evidence (every ``<failure>``/``<skipped>`` part plus captured
output) in the need content.

Consuming the result
--------------------

The output is a schema-conform ``needs.json``, so it can be imported as local
needs:

.. code-block:: rst

   .. needimport:: needs.json

or mounted as external needs via ``needs_external_needs`` in ``conf.py``.

Every need carries the synthesized source URL twice: as ``external_url``, which
Sphinx-Needs uses when rendering a link to an external need, and as a plain
``remote_url`` field, so needs imported as *local* needs keep a clickable link
through a ``needs_string_links`` entry.

Linking test cases to requirements
----------------------------------

XML ``<properties>`` become need fields under their own names. To turn one into a
link field instead, map it -- the value is split on commas:

.. code-block:: bash

   test-reports convert test.xml --output needs.json \
       --link-property PartiallyVerifies=partially_verifies \
       --link-property FullyVerifies=fully_verifies

Mapped link fields are written even when a case has no such property, so a schema
can require them.

Source links
------------

Source URLs need both a repository and a commit; they are refused separately,
because half the metadata cannot produce a URL:

.. code-block:: bash

   test-reports convert test.xml --output needs.json \
       --remote-url git@github.com:org/repo.git \
       --commit "$(git rev-parse HEAD)"

Git remotes are accepted in ``scp`` form and normalised. Without this metadata --
as in a hermetic sandbox -- the URL fields stay empty rather than carrying a
placeholder that looks real and then 404s.

Forges that lay out blob URLs differently are handled with ``--url-pattern``,
which accepts the placeholders ``{base}``, ``{commit}``, ``{file}`` and
``{line}``:

.. code-block:: bash

   test-reports convert test.xml --output needs.json \
       --remote-url https://gitlab.com/org/repo --commit abc123 \
       --url-pattern "{base}/-/blob/{commit}/{file}#L{line}"

Reproducible output
-------------------

The written file is byte-stable: keys are sorted and no timestamp is recorded.
Converting the same report twice produces identical bytes, so the output works as
a cached build-action output and as diffable evidence.

Missing source locations
------------------------

If no test case in a report carries a ``line`` attribute, the command says so on
stderr. The usual cause is pytest's default ``junit_family = xunit2``, which
filters ``file`` and ``line`` off ``<testcase>``; ``xunit1`` (or ``legacy``)
emits them.

All options
-----------

.. code-block:: text

   test-reports convert FILE [FILE ...] --output PATH
                        [--project NAME] [--version KEY]
                        [--need-type TYPE] [--tags TAGS]
                        [--link-property PROPERTY=LINK_FIELD]
                        [--remote-url URL] [--commit COMMITISH]
                        [--url-pattern PATTERN]

``--project`` and ``--version`` fill the ``needs.json`` envelope;
``--need-type`` (default ``testcase``) sets the need type and the ID prefix;
``--tags`` is a comma-separated list applied to every created need.
