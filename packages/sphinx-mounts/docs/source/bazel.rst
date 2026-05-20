Bazel integration
=================

This walk-through shows a Bazel workspace that emits RST files via a
``genrule`` and a Sphinx project that mounts the resulting
``bazel-bin/docs/`` directory — declaratively, via ``ubproject.toml``.

The Bazel workspace
-------------------

``MODULE.bazel``:

.. code-block:: python

   module(name = "my_docs", version = "0.0.0")

``BUILD.bazel``:

.. code-block:: python

   genrule(
       name = "gen_tutorial",
       outs = ["docs/tutorial.rst"],
       cmd = """cat > $@ <<'EOF'
   Tutorial
   --------

   Hello from Bazel.
   EOF
   """,
   )

   filegroup(
       name = "generated_docs",
       srcs = [":gen_tutorial"],
       visibility = ["//visibility:public"],
   )

After ``bazel build //:generated_docs``, the file lives at
``<workspace>/bazel-bin/docs/tutorial.rst``.

The Sphinx project
------------------

The Sphinx project sits under ``<workspace>/sphinx_project/`` and ships
two files: a minimal ``conf.py`` and the declarative ``ubproject.toml``.

``conf.py``:

.. code-block:: python

   extensions = ["sphinx_mounts"]

``ubproject.toml``:

.. code-block:: toml

   # Relative to confdir (sphinx_project/), so ../bazel-bin/docs
   # resolves to <workspace>/bazel-bin/docs.
   [[mounts]]
   dir = "../bazel-bin/docs"
   mount_at = "_bazel"

``index.rst``:

.. code-block:: rst

   My docs
   =======

   .. toctree::

      _bazel/tutorial

Why this matters: an IDE plugin or build-system query tool can read the
same ``ubproject.toml`` to learn that ``_bazel/*`` lives under
``bazel-bin/docs/`` — without having to evaluate ``conf.py``.

Running the build
-----------------

.. code-block:: bash

   bazel build //:generated_docs
   sphinx-build -b html sphinx_project/ sphinx_project/_build/html

The Sphinx build reads ``bazel-bin/docs/tutorial.rst`` directly from the
Bazel output location. Nothing is copied into the Sphinx source tree.

Hermetic builds
---------------

For hermetic CI, point sphinx-mounts at a path that Bazel writes
deterministically — typically the ``bazel-bin`` symlink under the
workspace, or a path captured from ``$(bazel info bazel-bin)``. The
example test in ``tests/test_bazel.py`` uses a per-test
``--output_base`` to fully isolate Bazel state from the user's other
caches.

The ``bazel-bin`` / ``bazel-out`` symlinks Bazel maintains at the
workspace root are themselves portable: they sit at the same
*workspace-relative* path on every platform (Linux, macOS, Windows
under WSL or msys2), and the actual output directory they point to
is an implementation detail managed by Bazel. That means a relative
TOML entry such as ``dir = "../bazel-bin/docs"`` resolves to a
valid path on every developer machine and CI runner — and
:ref:`path-anchoring` ensures it stays anchored to the TOML's own
directory, so the file is genuinely **checked-in-able**. There is no
need to generate the TOML per-machine or per-OS; one
version-controlled ``ubproject.toml`` is enough.

When the mount *list itself* needs to be dynamic — assembled across
repositories, gated by Bazel ``select()`` choices, or emitted by a
configuration repo — pair sphinx-mounts with `needs-config-writer`_.
It can populate ``ubproject.toml`` with the ``[[mounts]]`` section
(among others) from Python-side configuration at build time. The
generated TOML is then the artefact sphinx-mounts and `ubCode`_ both
consume, exactly as if it had been hand-written. See `Generating
ubproject.toml from a build-system config`_ above for the full
pipeline shape.

Relation to ``bazel-drives-sphinx``
-----------------------------------

The `bazel-drives-sphinx`_ project tackles the same goal — letting
Bazel decide what ends up in a Sphinx build — but at a different
point on the spectrum. There, Bazel rules act as the source of truth:
each component declares its RST files (and, for `Sphinx-Needs`_
setups, its ``needs.json`` artifacts) as Bazel labels, ``cfg_bazel``
generates per-project ``docs_html``, ``docs_needs`` and ``docs_schema``
targets, and ``sphinx-build`` is invoked as the final rendering step
on the assembled tree. Bazel features such as tag-driven variant
selection, cross-project needs imports, and per-target caching all
flow through.

sphinx-mounts is the lighter take on the same idea. The contract has
only two parts:

1. Bazel runs first and localizes every generated file under
   ``bazel-bin/`` (or ``bazel-out/``) at deterministic relative paths.
2. ``sphinx-mounts`` mounts that directory at a ``mount_at`` prefix —
   Sphinx then reads each file *in place*, with no staging step and no
   per-file Bazel rule on the Sphinx side.

The build system stays in control of the dependency graph; Sphinx
focuses on rendering. The same setup would work with Buck2, Pants,
Make, or any script that lands files under a known path — nothing in
``ubproject.toml`` references Bazel concepts.

.. note::

   A full, browsable reference example of this pattern (Bazel-driven
   bundles + a host project + ``attach_to`` wiring) lives at
   `tests/example/
   <https://github.com/useblocks/sphinx-mounts/tree/main/tests/example>`__
   in the repository. Every file is checked in (no pytest
   bootstrapping); the README there walks through the layout, the
   ``bazel build`` step, and the ``sphinx-build`` step. The pytest
   binding ``tests/test_example.py`` runs the whole pipeline
   end-to-end.

A further difference is who owns the documentation *structure*. Under
sphinx-mounts the host RST files — ``index.rst`` and every toctree —
are hand-written by the documentation author. The extension attaches
mount entries to existing toctrees via ``attach_to`` (see
:ref:`toctree-integration`) at build time, on the parsed doctree, and
never rewrites the RST on disk. Anything that reads the source tree
— editors, version control, ``grep`` — sees exactly what the author
wrote.

``bazel-drives-sphinx`` sits at the opposite end of this axis: it is
fundamentally file-based and can potentially *destructure* a project
to suit the build graph. Files such as ``index.rst`` and their
toctrees may be generated by Bazel rules, so the shape of the
rendered documentation becomes a function of the build configuration
rather than of an authored hierarchy. That is the right trade-off
when the build system is also the system of record for variant
assembly and cross-project imports, but it costs authorial control
over structure.

A useful side effect of "files live in place" is that IDE features
keep working: the generated tree sits at a stable filesystem path that
editors and the `ubCode`_ language server can open directly, and they
consult the same ``ubproject.toml`` Sphinx does, so cross-references
resolve identically at edit time and at build time.

Pick whichever is right for the scale of the project.
``bazel-drives-sphinx`` is the reference when you need fine-grained,
per-file Bazel rule collection across many projects, Bazel-managed
cross-project needs imports, and tag-driven variants. sphinx-mounts is
the reference when "run a Bazel build, then point Sphinx at
``bazel-bin/``" is enough.

Generating ``ubproject.toml`` from a build-system config
--------------------------------------------------------

For workspaces where the *list of mounts itself* is dynamic — assembled
across several repositories, gated by Bazel ``select()`` choices, or
emitted by a configuration repository — hand-writing ``ubproject.toml``
quickly becomes a maintenance burden. `needs-config-writer`_ closes
that loop: it is a Sphinx extension whose job is to *emit* a
``ubproject.toml`` from a Python-side configuration (whatever
``conf.py`` and its imports assemble at build time, including values
pulled in from Bazel-generated config files such as those described
above for ``bazel-drives-sphinx``).

A typical pipeline looks like:

1. A Bazel rule assembles the dynamic configuration — including the
   set of mount entries that should appear in this build — and
   exposes it to Sphinx (e.g. via a generated config module that
   ``conf.py`` imports).
2. A first Sphinx pass runs with `needs-config-writer`_ enabled. The
   extension writes a static ``ubproject.toml`` (including its
   ``[[mounts]]`` section) next to ``conf.py``.
3. A second Sphinx pass — the actual documentation build — runs
   ``sphinx-mounts``, which reads the now-static ``ubproject.toml``
   exactly like a hand-written one. The same file is what
   `ubCode`_ and other static readers see; editor and build see
   the same shape.

The advantage over feeding Python directly into ``mounts = [...]`` in
``conf.py`` is that the generated TOML can be checked into version
control (or surfaced as a Bazel output) and consumed by any tool that
can read TOML — without anyone having to evaluate ``conf.py``. That is
the same "declarative is primary" property that motivates
``ubproject.toml`` in the first place, extended to projects where the
mount list is itself a build-system artefact.

``needs-config-writer`` is primarily oriented at the Sphinx-Needs
config sections today, but the same mechanism can populate any TOML
section the project needs — including ``[[mounts]]``. See its
`motivation
<https://needs-config-writer.useblocks.com/motivation.html>`__ for the
distributed-build use case in detail.
