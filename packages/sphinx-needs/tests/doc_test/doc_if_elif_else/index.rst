IF ELIF ELSE Test
=================

If taken
--------

.. if:: var.arch == "abc"

   TAKEN_IF

.. elif:: var.arch == "abc"

   SKIPPED_ELIF_AFTER_TAKEN_IF

.. else::

   SKIPPED_ELSE_AFTER_TAKEN_IF

First true elif wins
--------------------

.. if:: var.arch == "xyz"

   SKIPPED_IF_FALSE

.. elif:: var.arch == "def"

   SKIPPED_ELIF_FALSE

.. elif:: var.arch == "abc"

   TAKEN_FIRST_TRUE_ELIF

.. elif:: var.debug

   SKIPPED_SECOND_TRUE_ELIF

.. else::

   SKIPPED_ELSE_AFTER_TAKEN_ELIF

All false
---------

.. if:: var.arch == "xyz"

   SKIPPED_ALL_FALSE_IF

.. elif:: not var.debug

   SKIPPED_ALL_FALSE_ELIF

.. else::

   TAKEN_ELSE_ALL_FALSE

If and else
-----------

.. if:: not var.debug

   SKIPPED_IF_BEFORE_ELSE

.. else::

   TAKEN_ELSE_WITHOUT_ELIF

Independent chains
------------------

.. if:: var.arch == "abc"

   TAKEN_FIRST_CHAIN

.. if:: var.arch == "xyz"

   SKIPPED_SECOND_CHAIN_IF

.. else::

   TAKEN_SECOND_CHAIN_ELSE

Comments between branches
-------------------------

.. if:: var.arch == "xyz"

   SKIPPED_IF_BEFORE_COMMENT

.. a comment between two branches

.. else::

   TAKEN_ELSE_AFTER_COMMENT

Nested chains
-------------

.. if:: var.debug

   OUTER_TAKEN

   .. if:: var.arch == "xyz"

      SKIPPED_NESTED_IF

   .. else::

      TAKEN_NESTED_ELSE

.. else::

   SKIPPED_OUTER_ELSE

Section title in a taken branch
-------------------------------

.. if:: var.arch == "abc"

   Conditional heading
   ~~~~~~~~~~~~~~~~~~~

   TAKEN_SECTION_CONTENT

.. else::

   SKIPPED_ELSE_AFTER_SECTION

Chains in need content
----------------------

.. req:: A requirement with variant content
   :id: REQ_HOST

   .. if:: var.arch == "xyz"

      SKIPPED_IN_NEED

   .. else::

      TAKEN_IN_NEED

Needs in branches
-----------------

.. if:: var.arch == "xyz"

   .. req:: Requirement in a skipped if
      :id: REQ_IF_SKIPPED

.. elif:: var.arch == "abc"

   .. req:: Requirement in a taken elif
      :id: REQ_ELIF_TAKEN

.. else::

   .. req:: Requirement in a skipped else
      :id: REQ_ELSE_SKIPPED
