Language features
=================

This page is used as example source for all feature presentations.

.. _auto_ids:

Auto-generated need IDs
-----------------------

.. image:: /_images/lsp_auto_ids.gif
   :align: center

Type ``:`` in the line directly below a need directive like ``.. req::`` and select ``:id:`` in the IntelliSense interface.


.. hint::

   * If needls can't detect the type of the need it will just output `ID`.
   * The ID is calculated using a hash function of the current user, doc URI, line number and the need prefix (e.g.).
     To lower the risk of ID conflicts further a pseudo-randomization is part of the ID generation.s


.. _snippets:

Predefined Snippets
-------------------

.. image:: /_images/lsp_snippets.gif
   :align: center


Type ``..`` and choose to auto-complete the directive in the IntelliSense interface.

.. _id_selection:

ID selection
------------
   
.. image:: /_images/lsp_id_selection.gif
   :align: center


#. After `:need:` role or `:links:` option type `->` which triggers the auto-completion of needs
#. Select a need type from the IntelliSense dialog (use arrow keys)

   * Type `>` again to trigger the doc completion (file in which needs are specified)
   * Type `/` to complete the doc path, continue until the doc path is completed to a `*.rst` file
   * Type `>` to trigger completion of a specfic need by ID, expand the completion item info to see the content of the selected need


.. _goto:

Go to definition for need IDs
-----------------------------

.. image:: /_images/lsp_goto.gif
   :align: center


Move cursor to a need ID and hit `F12`

Alternatively right click on a need ID and choose "Go to Definition" from the context menu


.. _preview:

Need information on mouse hover
-------------------------------

.. image:: /_images/lsp_preview.gif
   :align: center

Move the mouse cursor over any need ID

Example data
------------
The below needs are used as example data.


.. req:: Language features support for Sphinx-Needs
   :id: REQ_001
   

   Our Sphinx project needs to support to write need objects more easily.


.. spec:: Use Language Server Esbonio
   :id: SPEC_001
   :links: REQ_001

   We implement language features intergrated into language server `Esbonio <https://github.com/swyddfa/esbonio>`_ to fulfill :need:`REQ_001`.

