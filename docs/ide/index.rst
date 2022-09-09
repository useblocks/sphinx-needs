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

* Install IDE extension or plugin, see current supported IDE extension in :ref:`ide_installation`.

* Build `needs.json` file in your Sphinx-Needs project:

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
