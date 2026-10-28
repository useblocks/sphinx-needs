Template directives
===================

A template directive renders a `Jinja <https://jinja.palletsprojects.com>`__ template
with data you declare, and inserts the result into the page as if you had written it there.
Its commonest use is generating needs from a data file:
the generated needs are ordinary needs of the section that holds the directive.

Templates are rendered with `minijinja <https://github.com/mitsuhiko/minijinja>`__,
the engine ubCode renders the same templates with, configured identically on both sides.

.. _templates_contexts:

Data: contexts and ``var``
--------------------------

A context is named data, declared in ``ubproject.toml``,
either inline or as a JSON or TOML file under the source directory:

.. code-block:: toml

   [parse.template_contexts.reqs]
   file = "data/reqs.json"

   [parse.template_contexts.team]
   lead = "Ada"
   members = ["Bob", "Cy"]

Context data is plain data: strings, booleans, integers (in the signed 64-bit range), finite floats,
arrays (of one kind of scalar, or of tables) and tables, at most 64 levels deep.
A null, a date or time, ``inf`` or ``nan``, a mixed array, an array of arrays,
a file whose top level is not a table, a YAML file, a file of any other extension than ``.json`` or ``.toml``
(read case-insensitively), or a file that does not parse
is reported at each use (``ub_directives.template_context_invalid``), which then renders nothing.
A mapping iterates in the order the data writes it, and so do ``options`` and ``contexts``.
For ``ub-template``, a top-level ``var``, ``loop`` or ``self`` key is refused the same way,
and a key no template can name (``true``, ``none``, ``in``, …) is skipped.

Every template also sees ``var``: the project's variant data,
the same values ``.. if::`` evaluates against (``[variants]`` in ``ubproject.toml``).
A context cannot be named ``var``.

.. _templates_declared:

Declare a template directive
----------------------------

.. code-block:: toml

   [parse.directive_templates.req-row]
   template = "_templates/req_row.rst.j2"   # under the source directory; or body = "…"
   description = "One requirement row"
   argument = { required = true, description = "Requirement id" }
   content = false                           # whether the directive takes a body

   [parse.directive_templates.req-row.options]
   owner = { required = true, description = "Who owns it" }
   status = { choices = ["open", "closed"], default = "open" }
   draft = { flag = true }

The template sees exactly ``argument`` (or ``none``), ``options`` (every declared option:
the written value, else its default, else ``none``; a flag is ``True`` or ``False``),
``body`` (when ``content`` is true), ``contexts`` (every context, by name) and ``var``:

.. code-block:: jinja

   .. req:: Owned by {{ options.owner }}
      :id: {{ argument }}
      :status: {{ options.status }}

and a page uses it like any directive:

.. code-block:: rst

   .. req-row:: REQ_010
      :owner: Ada

The signature is closed: an option that is not declared, a missing required option or argument,
a value outside ``choices``, a flag written with a value, an argument to a directive that declares none,
or a body on a directive without ``content`` is reported on the use (``ub_directives.template_signature``),
which then renders nothing.

A declaration whose name is already a directive (in any case), that differs only in case from another,
or that gives both or neither of ``template`` and ``body`` is reported once (``ub_directives.directive_template_invalid``) and ignored.

**Markup.** A declared template writes reStructuredText or MyST Markdown:
``markup = "rst"`` or ``"md"``, else its file's name (``*.rst.j2``, ``*.md.j2``, ``*.rst.jinja``, ``*.md.jinja``),
else reStructuredText.
In a page of the other markup the output is parsed as its own markup, and may not hold
a substitution definition, a footnote or a citation (``ub_directives.template_markup_construct``).

A declaration's fields have fixed shapes (``default`` a string, ``choices`` an array of strings,
``flag``, ``required`` and ``content`` booleans, ``argument`` a table);
a wrong one refuses the declaration (``ub_directives.directive_template_invalid``),
and an unknown key is reported (``ub_directives.directive_template_unknown_key``) and ignored.

.. _templates_ub_template:

The ``ub-template`` directive
-----------------------------

Switch it on in ``ubproject.toml``; until then a use renders nothing and says so
(``ub_directives.template_switched_off``):

.. code-block:: toml

   [parse]
   ub_template_enabled = true

.. code-block:: rst

   .. ub-template:: team

      {% for m in members %}
      .. req:: Member {{ m }}
         :id: REQ_{{ m|upper }}

      {% endfor %}

Its argument names a context, whose keys are the template's variables. Options:

``:file:``
   Render this template file instead of the body:
   relative to the page, or to the source directory with a leading ``/``.
``:ctx:``
   More variables, as an inline JSON object; they override the named context's.
``:debug:``
   Also show the rendered text, as a literal block.
``:raw:``
   Emit the rendered text unparsed, as raw content of this output format (``:raw: html``).

How output joins the page
-------------------------

Output is inserted as body content where the directive is, as if you had written it there,
so a need it generates belongs to the section that holds the directive.

**Template output may not hold a section title** in this version: in either markup,
anywhere in the output (inside a ``note`` or a list item it writes too), wherever the directive sits.
A use whose output holds one is reported (``ub_directives.template_heading``) and renders nothing.
A rubric (``.. rubric::``, or MyST's ``{rubric}``) is not a section title, and is allowed;
so is title-like text in a ``code-block``. Put the heading in the page, above the directive.

The output may not hold another template directive (it is never expanded again)
nor a directive that reads a file the template did not declare (nor a preset of one,
written with the preset's options):
``include``, ``literalinclude``, ``csv-table`` and ``raw`` with ``:file:`` or ``:url:``,
``needimport``, ``needreport`` with ``:template:``, ``needservice``, ``src-trace``,
``graphviz``, ``mermaid``, ``plantuml`` and ``uml`` given a file, the ``auto*`` directives,
the sphinx-test-reports directives, and a need with ``:template:``, ``:pre_template:``,
``:post_template:`` or ``:jinja_content:``.
Such a directive renders nothing and is reported
(``ub_directives.template_nested_expansion``, ``ub_directives.template_output_reads_file``);
the rest of the output renders.
A directive of another extension that reads a file is your responsibility:
a Sphinx build warns when one notes a dependency (``ub_directives.template_reads_dependency``).

The language
------------

Undefined values are errors (test with ``is defined``); nothing is escaped;
``break`` and ``continue``, Python methods on values (``.upper()``, ``.items()``),
``filesizeformat``, ``urlencode``, ``truncate``, ``pluralize``, ``striptags``,
``joiner()``, ``cycler()`` and ``wordwrap`` (with a positional width) are available.
There is no clock, randomness or I/O, and no ``env``
(``ub_directives.template_context_unavailable``).
``{% include %}``, ``{% import %}`` and ``{% extends %}`` name files relative to the source directory.

Limits
------

A render may write at most 1 MiB (``ub_directives.template_output_limit``)
and spend a bounded amount of work; a use over a limit renders nothing.
The output is checked once rendered, and the values a template builds on the way are not bounded
in a Sphinx build (ubCode bounds them too), so a runaway template can use a lot of memory before it is refused.
In one page, once a template has hit a limit with three different inputs,
its later uses there with yet other inputs are not rendered (``ub_directives.template_disabled``).
Every template, context file and included file a use reads is a dependency of the page.

Other findings: ``template_render_error`` (the template cannot be rendered),
``template_context_unknown`` (no context of that name), ``template_missing`` and
``template_outside_root`` (a template file), ``template_option_invalid`` (``ub-template``'s options).
