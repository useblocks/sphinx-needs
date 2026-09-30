ubproject
=========

The shared reader for ``ubproject.toml``, the declarative file that describes a project to
every useblocks tool: the sphinx-needs family of Sphinx extensions (sphinx-needs,
sphinx-mounts, sphinx-codelinks, sphinx-test-reports), their command lines, and ubCode.

It holds the parts of that file more than one tool reads, so that they are read one way:

- **finding, loading and anchoring** the file -- the walk up to the repository root (or,
  outside a repository, the distribution root), TOML read with every failure named, a dotted table selected, and relative paths anchored at
  the file's own directory;
- **the** ``[variants]`` **table**, with the legacy ``[needs] variant_data*`` keys as its
  fallback;
- **the variant-data merge** -- validate, load from JSON, deep-merge, resolve -- in one copy.

Standard library only: no Sphinx, no docutils, no sibling distribution. A converter or a
build action that runs without the documentation toolchain can use it.

The three calls
---------------

.. code-block:: python

   from pathlib import Path

   from ubproject import find_project_config, load_toml, read_variants

   toml_path = find_project_config(Path.cwd())   # or the path your tool is configured with
   if toml_path is not None:
       result = read_variants(load_toml(toml_path), toml_path)
       result.data          # the merged variant map
       result.data_file     # the data file, anchored at the TOML's directory, or None
       result.location      # "variants", "needs" or None
       result.diagnostics   # findings to report -- or not

Every hard failure is an ``UbprojectError`` whose message names the file and the rule that
was broken.

``[variants]``
--------------

.. code-block:: toml

   [variants]
   data_file = "variants.json"   # one path, anchored at this file's directory

   [variants.data]               # deep-merged over the file; the inline table wins
   edition = "pro"
   build = { debug = false }

If ``[variants]`` declares neither key, the reader falls back to ``[needs] variant_data``
and ``[needs] variant_data_file``. If both locations are set, ``[variants]`` is read whole
and every ignored ``[needs]`` key is reported.

Consumers decide the policy
---------------------------

This package decides nothing a consumer has reason to decide differently. **Discovery**
(walk up, or read the Sphinx ``confdir``), **warnings** (a diagnostic is returned, never
logged: whether the legacy location deserves one is each tool's call), and **the command
line** (``-D`` in Sphinx, ``-c`` in ubCode) are all the consumer's.

The contract
------------

``design/reading-contract.md`` is the normative specification, and
``tests/fixtures/ubproject_reading_conformance.toml`` is its executable half: a corpus of
inputs and expected results that this package's suite runs, and that ubCode is to vendor
and run against its own reader (its reader does not read ``[variants]`` yet).
