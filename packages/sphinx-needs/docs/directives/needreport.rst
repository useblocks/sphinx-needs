.. _needreport:

needreport
==========

.. versionadded:: 1.0.1

**needreport** documents the following configurations from **conf.py**:

* :ref:`Types <needs_types>`
* :ref:`Links <needs_links>`
* :ref:`Fields <needs_fields>`

and it also adds some needs metrics using the `usage`_ option.

``needreport`` renders a template, and out of the box that is the default template
packaged with Sphinx-Needs — no configuration is required.
To render a template of your own instead, either set the :ref:`needs_report_template`
configuration variable, which applies to every ``needreport`` in the project, or give a
single directive its own `template`_ option.

Templates are rendered with `MiniJinja <https://github.com/mitsuhiko/minijinja>`__, a
`Jinja <https://jinja.palletsprojects.com/>`__-compatible engine. The packaged default
template, how a template path is resolved, and the variables a template can read are all
documented under :ref:`needs_report_template`.

.. note::

   Each section of the default template is wrapped in a ``dropdown`` directive, which
   neither Sphinx nor Sphinx-Needs provides — it needs an extension that supplies one,
   for example `sphinx-design <https://sphinx-design.readthedocs.io>`__.
   If none is loaded, the report is rendered with ``admonition`` instead and warns.
   A template of your own is only affected if that substitution actually changes what
   it renders; see :ref:`needs_report_template`.
   To pick the directive yourself, and so render without a warning:

   .. code-block:: python

      needs_render_context = {
         "report_directive": "admonition",
      }

.. syntax-example::

   .. needreport::
      :types:


Options
-------

.. _types:

types
~~~~~

Flag for adding information about the :ref:`needs_types` configuration parameter.
The flag does not require any values.

.. syntax-example::

   .. needreport::
      :types:


.. _links:

links
~~~~~

Flag for adding information about the :ref:`needs_links` configuration parameter.
The flag does not require any values.

.. syntax-example::

   .. needreport::
      :links:


.. _options:

options
~~~~~~~

Flag for adding information about the :ref:`needs_fields` configuration parameter.
The flag does not require any values.

.. syntax-example::

   .. needreport::
      :options:

usage
~~~~~
Flag for adding information about all the ``need`` objects in the current project.
The flag does not require any values.

.. syntax-example::

   .. needreport::
      :usage:

.. _needreport_template_option:

template
~~~~~~~~

Path to the template this directive should render, overriding
:ref:`needs_report_template` for this one directive.
Unlike the flags above, it takes a value.

The path is resolved relative to the document the directive is written in, and a leading
``/`` makes it relative to the source directory — the path convention Sphinx uses
throughout, and *not* the one :ref:`needs_report_template` uses, which is always relative
to the source directory whether or not it starts with a ``/``.

.. code-block:: rst

   .. needreport::
      :types:
      :template: report_templates/types_only.need

If the file does not exist, a ``needs.needreport`` warning is emitted and the directive
renders nothing.
