.. _pytest_plugin:

pytest plugin
=============
.. versionadded:: 1.5.0

A stock pytest run writes a JUnit XML that this extension can only partly use.
Under pytest's default ``junit_family = xunit2`` no ``<testcase>`` carries the
``file``/``line`` attributes that give a test case its source location
(``tr_source_file_option``/``tr_source_line_option``, and the deterministic ID
of ``tr_deterministic_case_ids``). Under ``xunit1`` pytest writes them, but
counts the line from 0, keeps Bazel's runfiles prefix, and has no way to point
a case at the file that drove it. And nothing records the requirements a test
verifies. ``Sphinx-Test-Reports`` ships a small pytest plugin that takes care
of both.

The plugin is generic: which properties exist, what they are called in the XML
and whether they take a list is pytest configuration, not code. S-CORE's model
is the worked example below.

Enabling it
-----------

The plugin is the ``pytest`` extra of the package: ``pip install
"sphinx-test-reports[pytest]"`` installs it without the documentation toolchain
(see :doc:`/install`). Enable it in the pytest configuration:

.. code-block:: ini

   # pytest.ini / pyproject.toml [tool.pytest.ini_options]
   addopts = -p sphinxcontrib.test_reports.pytest_plugin
   junit_family = xunit1

then run with ``--junitxml=report.xml`` as usual. ``junit_family = xunit1`` is
required: pytest writes ``<testcase>`` attributes only under that family (its
``legacy`` is an alias), and the plugin warns at start-up when a report is
requested under ``xunit2``. Every test case now carries ``file`` and ``line``
as an editor shows them: the line counted from 1, the path relative to the
pytest rootdir with Bazel's ``_main/`` runfiles prefix cut off. Every case
means every case -- one skipped or erroring during setup gets the same
treatment, so a deterministic ID does not move with the outcome. The plugin
works through hooks on the test reports, not fixtures, which is also why it
holds under pytest-xdist: the location is written on the controller, where
pytest keeps the XML writer, and the properties travel with the reports.

Nothing else changes for tests that do not use the decorator below.

The start-up notice is a ``TestReportsConfigWarning``. A project that turns
warnings into errors (``filterwarnings = error``, ``-W error``) gets it as a
clean usage error instead;
``ignore::sphinxcontrib.test_reports.pytest_plugin.TestReportsConfigWarning``
silences it.

Declaring the properties
------------------------

The ``test_reports_properties`` ini option declares the properties a test may
carry, one per line:

.. code-block:: text

   keyword [= XmlName] [, list]

*keyword*
   what a test author writes -- the argument of ``add_test_properties`` or the
   key in the metadata of ``apply_test_metadata``.
*XmlName*
   the ``<property name="...">`` written to the report. Leave it out when it
   equals the keyword.
``list``
   marks a multi-valued property: a list is written joined with ``", "`` -- the
   shape ``tr_property_link_types`` splits again -- and a bare string counts as
   one value. Without it the property takes exactly one value, and a list is a
   ``TypeError`` rather than a silent join.

A keyword that is not declared is written under its own name with a single
value. A list under it is a ``TypeError`` whose message names the option, so a
project cannot lose requirement IDs to a Python ``repr`` silently. For the same
reason every item of a list has to be a string: a nested list, ``bytes`` or any
other object is a ``TypeError`` naming the item. Values are joined with a comma
and split on it again on the build side, and there is no escaping, so a value
of a ``list`` property must not contain a comma. A line outside the grammar, or
two keywords declaring the same XML name, stops the run at start-up with a usage
error that quotes the line.

The option exists only while the plugin is loaded: an ini file that declares
``test_reports_properties`` without the ``-p`` line above fails
``--strict-config`` with an unknown option. The two belong together.

**Example: S-CORE.** The model of S-CORE's docs-as-code, whose ``score_pytest``
plugin this one was ported from:

.. code-block:: ini

   # pytest.ini
   [pytest]
   addopts = -p sphinxcontrib.test_reports.pytest_plugin
   junit_family = xunit1
   test_reports_properties =
       partially_verifies = PartiallyVerifies, list
       fully_verifies = FullyVerifies, list
       test_type = TestType
       derivation_technique = DerivationTechnique

.. code-block:: toml

   # pyproject.toml
   [tool.pytest.ini_options]
   addopts = "-p sphinxcontrib.test_reports.pytest_plugin"
   junit_family = "xunit1"
   test_reports_properties = [
       "partially_verifies = PartiallyVerifies, list",
       "fully_verifies = FullyVerifies, list",
       "test_type = TestType",
       "derivation_technique = DerivationTechnique",
   ]

With it, tests written against ``score_pytest`` keep working when they import
``add_test_properties`` and ``apply_test_metadata`` from here. The values of
``test_type`` and ``derivation_technique`` are the identifiers of S-CORE's
verification methods and derivation techniques, from its
`verification concept <https://eclipse-score.github.io/process_description/main/process_areas/verification/verification_concept.html#verification-concept-types-methods>`_:

.. list-table::
   :header-rows: 1

   * - ``TestType``
     - ``DerivationTechnique``
   * - ``control-flow-analysis``, ``data-flow-analysis``, ``fault-injection``,
       ``inspection``, ``interface-test``, ``requirements-based``,
       ``resource-usage``, ``static-code-analysis``,
       ``structural-statement-coverage``, ``structural-branch-coverage``,
       ``walkthrough``
     - ``requirements-analysis``, ``design-analysis``, ``boundary-values``,
       ``equivalence-classes``, ``fuzz-testing``, ``error-guessing``,
       ``explorative-testing``

They are documented here, not enforced by the plugin: S-CORE's own metamodel
accepts any string for both fields, and a project with a different metamodel
writes its own values.

Linking a test to requirements
------------------------------

With the S-CORE model declared:

.. code-block:: python

   from sphinxcontrib.test_reports.pytest_plugin import add_test_properties

   @add_test_properties(
       partially_verifies=["REQ_1", "REQ_2"],
       test_type="requirements-based",
       derivation_technique="requirements-analysis",
   )
   def test_addition():
       """Adding two numbers."""
       assert 1 + 1 == 2

writes, on that test's ``<testcase>``:

.. code-block:: xml

   <properties>
     <property name="PartiallyVerifies" value="REQ_1, REQ_2"/>
     <property name="TestType" value="requirements-based"/>
     <property name="DerivationTechnique" value="requirements-analysis"/>
   </properties>

The declared XML name doubles as keyword, so ``PartiallyVerifies=[...]`` is
accepted too; a keyword declared as such wins over an XML name of the same
spelling. Empty values are not written, and a decorator that would write
nothing is an error at import time. The values are written when the test is
set up, against the declared model; a wrong shape -- a list where one value is
expected -- makes that test error at setup with the ``TypeError`` above (its
need then carries the result ``error``, not ``failed``). The properties keep
the order of the keywords.

The decorator also goes on a class, and decorators stack: a classification on
the class and the requirement links on each method are merged into the method's
``<properties>``, the decorator closest to the function winning where two set
the same property.

A skipped test carries its properties too, so its requirement links are in the
report next to ``result="skipped"``. The plugin records the link; what the link
means is the project's rule to make. A traceability query that reads "verified"
off a link has to look at ``result`` as well, or a test that never ran counts as
verification.

On the build side the properties arrive through the directives' property
handling: ``tr_property_link_types`` turns a comma-separated property into a
link field, and the link field has to exist as a sphinx-needs link type;
``tr_extra_options`` lists the properties that become plain fields, each of
which has to exist as a need field --

.. code-block:: python

   # conf.py, sphinx-needs 7 and later
   needs_links = {
       "partially_verifies": {"incoming": "partially verified by", "outgoing": "partially verifies"},
       "fully_verifies": {"incoming": "fully verified by", "outgoing": "fully verifies"},
   }
   needs_fields = {"TestType": {"nullable": True}, "DerivationTechnique": {"nullable": True}}
   tr_property_link_types = {"PartiallyVerifies": "partially_verifies", "FullyVerifies": "fully_verifies"}
   tr_extra_options = ["TestType", "DerivationTechnique"]

On sphinx-needs 6 the two registrations are ``needs_extra_links`` (a list of
dicts with an ``option`` key) and ``needs_extra_options`` (a list of names);
sphinx-needs 7 deprecated both in favour of the spelling above. A link field
missing from ``needs_links`` fails the build on the first test case that carries
the property. The same names work for any other consumer of the report.

Metadata known only at run time
-------------------------------

A parameterised test whose metadata comes from the file it is driven by cannot
use a decorator. :func:`apply_test_metadata` records the same properties from
inside the test body, and can point the case at the file that drove it instead
of at the test function:

.. code-block:: python

   from sphinxcontrib.test_reports.pytest_plugin import apply_test_metadata

   @pytest.mark.parametrize("spec", SPECS)
   def test_spec(spec, record_property):
       metadata = read_metadata(spec)   # {"fully_verifies": [...], "test_type": ...}
       apply_test_metadata(
           record_property=record_property,
           metadata=metadata,
           file=str(spec),
           line=metadata_line(spec),
       )
       ...  # the actual checks

Call it before the first assertion, so a failing test still carries its
metadata. Metadata without values -- a file with an empty metadata block, a
parser handing back ``""`` or ``[]`` for an absent field -- writes no properties
and is not an error; ``file`` and ``line`` are applied regardless. ``file`` is
cut like every other location.

The override travels with the test report to where the XML is written, so it
holds under pytest-xdist: as two ``user_properties`` entries named
``sphinxcontrib.test_reports:file`` and ``sphinxcontrib.test_reports:line``,
which the plugin takes out again before the properties are written. Those two
names are reserved -- a property recorded under either is read as a location
override, not written as a property.

Calls written against ``score_pytest`` may keep passing ``record_xml_attribute``;
the argument is accepted and ignored. Drop the fixture from the test's signature,
though: requesting it is what makes pytest warn that the fixture is
experimental, and under ``-W error`` or ``filterwarnings = error`` that request
is a setup error. The plugin neither requests the fixture nor filters its
notice any more, so whether a test keeps it, and how it treats the notice, is
that test's own business.

Origin
------

The plugin is a port of the ``score_pytest`` attribute plugin of S-CORE's
`docs-as-code <https://github.com/eclipse-score/docs-as-code>`_. What that
plugin hard-codes -- the four properties and their spelling -- is the
``test_reports_properties`` example above here, and other metamodels declare
their own. With that example the XML comes out the same, with four exceptions:
a case skipped or erroring at setup carries its location and properties here
and pytest's stock values there; the properties keep the order of the keywords
rather than a fixed one; the Bazel prefix is cut at a whole ``_main`` component
only, not wherever the text ``_main/`` occurs; and a ``file`` handed to
``apply_test_metadata`` is cut the same way rather than passed through. Two of
that plugin's rules are not ported, because they are process rules of that
project rather than properties of the data: the ``test_type`` and
``derivation_technique`` vocabularies are documented but not enforced, and a
decorated test is not required to carry a docstring.
