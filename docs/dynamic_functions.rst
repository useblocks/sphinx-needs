Dynamic functions
=================

Sphinx-needs provides a mechanism to set dynamic data for need-options during generation.
This is realised by giving an author the possibility to set a function call to a predefined function, which calculates
the final result/value for the option.

This can be useful, if for instance the status of a requirement depends on linked test cases and their status.
Or if specific data shall be requested from an external server like JIRA.

Examples
--------

.. code-block:: jinja

   .. req:: my test requirement
      :id: df_1
      :status: open
      :comment: [[test("my_test", [1,2,3], key="value")]]

      This need has the id **[[copy("id")]]**!!

.. req:: my test requirement
   :id: df_1
   :status: open
   :comment: [[test("my_test", [1,2,3], key="value")]]


   This need has the id **[[copy("id")]]**!!

    ==============  =====  =======
    A               B      A and B
    ==============  =====  =======
    True            False  [[copy("id")]]
    [[copy("id")]]  Bulb   Awesome
    ==============  =====  =======




Built-in  functions
-------------------
The following functions are available in all sphinx-needs installations.

.. contents::
   :local:

test
~~~~
.. autofunction:: sphinxcontrib.needs.functions.common.test

copy
~~~~
.. autofunction:: sphinxcontrib.needs.functions.common.copy
