.. _ide:

IDE Support
===========

.. _lsp_features:

Features
--------

The following features are supported when using an `Esbonio <https://github.com/swyddfa/esbonio>`_ based IDE
extension, like VsCode extension `reStructuredText <https://github.com/vscode-restructuredtext/vscode-restructuredtext>`_,
in your **Sphinx-Needs** project.

.. grid::

   .. grid-item-card:: Auto-generated IDs
      :img-bottom: /_images/lsp_auto_ids.gif

   .. grid-item-card:: Snippets
      :img-bottom: /_images/lsp_snippets.gif

.. grid::

   .. grid-item::

      .. card:: ID Selection
         :width: 75%
         :img-bottom: /_images/lsp_id_selection.gif

      .. card:: Goto Definition
         :width: 75%
         :img-bottom: /_images/lsp_goto.gif

      .. card:: Need Preview
         :width: 100%
         :img-bottom: /_images/lsp_preview.gif

.. _ide_installation:

Installation
------------

VsCode
~~~~~~

The VsCode extension `reStructuredText <https://github.com/vscode-restructuredtext/vscode-restructuredtext>`_ supports all the Sphinx-Needs
language features and is available at `Visual Studio Marketplace <https://marketplace.visualstudio.com/items?itemName=lextudio.restructuredtext>`_.

To install and configure this extension, see details in
`How to install reStructuredText from Marketplace <https://github.com/vscode-restructuredtext/vscode-restructuredtext>`_ and

`How to use it <https://docs.restructuredtext.net/>`_.

.. _ide_usage:

Usage
-----

To use all the Sphinx-Needs language featues,

#. Install IDE extension or plugin, see current supported IDE extension in :ref:`ide_installation`.

#. Build `needs.json` file in your Sphinx-Needs project:

   * automatically build `needs.json` if configure `needs_build_json = True` in conf.py. See details in :ref:`needs_build_json`.
   * manually build `needs.json` using `sphinx-build -b needs source_dir build_dir`. See details in :ref:`builders`.

Auto-generated need IDs
~~~~~~~~~~~~~~~~~~~~~~~

.. image:: /_images/lsp_auto_ids.gif
   :align: center

Type ``:`` in the line directly below a need directive like ``.. req::`` and select ``:id:`` in the IntelliSense interface.

.. hint::

   * If needls can't detect the type of the need it will just output `ID`.
   * The ID is calculated using a hash function of the current user, doc URI, line number and the need prefix (e.g.).
     To lower the risk of ID conflicts further a pseudo-randomization is part of the ID generation.s

Predefined Snippets
~~~~~~~~~~~~~~~~~~~

.. image:: /_images/lsp_snippets.gif
   :align: center

Type ``..`` and choose to auto-complete the directive in the IntelliSense interface.

ID Selection
~~~~~~~~~~~~

.. image:: /_images/lsp_id_selection.gif
   :align: center

#. After `:need:` role or `:links:` option type `->` which triggers the auto-completion of needs
#. Select a need type from the IntelliSense dialog (use arrow keys)

   * Type `>` again to trigger the doc completion (file in which needs are specified)
   * Type `/` to complete the doc path, continue until the doc path is completed to a `*.rst` file
   * Type `>` to trigger completion of a specfic need by ID, expand the completion item info to see the content of the selected need

Goto Definition for need IDs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. image:: /_images/lsp_goto.gif
   :align: center

Move cursor to a need ID and hit `F12`

Alternatively right click on a need ID and choose "Go to Definition" from the context menu

Need information on mouse hover
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. image:: /_images/lsp_preview.gif
   :align: center

Move the mouse cursor over any need ID

.. _ide_myst:

MyST/Markdown
-------------

Directives and roles can be used in `MyST <https://myst-parser.readthedocs.io/en/latest/index.html>`_ in
this `Syntax <https://myst-parser.readthedocs.io/en/latest/syntax/roles-and-directives.html>`_.

All the above IDE :ref:`lsp_features` can also be supported for MyST/Markdown.

Usage
~~~~~

* Install MyST Parser using pip.

   .. code-block:: python

      pip install myst-parser

* Enable and active the MyST Parser extension in your Sphinx-Needs project by simply adding the following in your `conf.py` file:

   .. code-block:: python

      extensions = ["sphinx_needs", "myst_parser"]

      source_suffix = [".rst", ".md"]

* All the above IDE :ref:`lsp_features` are supported and used the same way like editing in rst files from above :ref:`ide_usage`, 
  when you editing your markdown files. e.g. `myfile.md`:

   * Directive snippets and role completion will be automatically translated into MyST/Markdown supported syntax style, see the following :ref:`ide_myst_example`

.. _ide_myst_example:

Example
~~~~~~~

Directive snippets 

.. image:: /_images/lsp_directive_snippets_markdown.gif
   :align: center

Directive snippets used inside `{eval-rst}` block

.. image:: /_images/lsp_directive_snippets_inside_eval_rst_block_markdown.gif
   :align: center

Role need completion

.. image:: /_images/lsp_need_role_need_suggestion_markdown.gif
   :align: center
