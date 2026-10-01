MATCH Test
==========

.. toctree::

   other

P1 first true case wins
-----------------------

The conditions after the taken case are never evaluated,
so the invalid one and the unknown key cannot warn.

.. match::

   .. case:: var.arch == "abc"

      TAKEN_P1_FIRST

   .. case:: var.debug

      SKIPPED_P1_SECOND_TRUE

   .. case:: this is not python !!!

      SKIPPED_P1_INVALID_SYNTAX

   .. case:: var.no_such_key == 1

      SKIPPED_P1_UNKNOWN_KEY

   .. case::

      SKIPPED_P1_DEFAULT

P2 default taken when no case holds
-----------------------------------

.. match::

   .. case:: var.arch == "xyz"

      SKIPPED_P2_FALSE

   .. a comment between two cases

   .. case::

      TAKEN_P2_DEFAULT

P2b no case holds and there is no default
-----------------------------------------

.. match::

   .. case:: var.arch == "xyz"

      SKIPPED_P2B_1

   .. case:: not var.debug

      SKIPPED_P2B_2

TAKEN_P2B_AFTER_MATCH

P3 needs in cases
-----------------

.. match::

   .. case:: var.arch == "xyz"

      .. req:: In a case that is not taken
         :id: REQ_P3_SKIPPED

   .. case:: var.arch == "abc"

      .. req:: In the taken case
         :id: REQ_P3_TAKEN

   .. case::

      .. req:: In a default that is not taken
         :id: REQ_P3_DEFAULT_SKIPPED

P4 sections in the taken case
-----------------------------

.. match::

   .. case:: var.debug

      P4 conditional heading
      ~~~~~~~~~~~~~~~~~~~~~~

      TAKEN_P4_SECTION_BODY

   .. case::

      P4 skipped heading
      ~~~~~~~~~~~~~~~~~~

      SKIPPED_P4_BODY

P5 nested match
---------------

.. match::

   .. case:: var.debug

      TAKEN_P5_OUTER

      .. match::

         .. case:: var.arch == "xyz"

            SKIPPED_P5_INNER

         .. case::

            TAKEN_P5_INNER_DEFAULT

   .. case::

      SKIPPED_P5_OUTER

P5b match in the content of a need
----------------------------------

The need is extracted on the other page,
which renders its content from the need-node cache.

.. req:: Host with match content
   :id: REQ_HOST

   .. match::

      .. case:: var.arch == "xyz"

         SKIPPED_P5B_IN_NEED

      .. case:: var.arch == "abc"

         TAKEN_P5B_IN_NEED

      .. case::

         SKIPPED_P5B_IN_NEED_DEFAULT

X1 the cases come from an include
---------------------------------

.. match::

   .. include:: cases.txt

X2 an include inside the taken case
-----------------------------------

.. match::

   .. case:: var.debug

      .. include:: taken_body.txt

      TAKEN_X2_AFTER_INCLUDE

   .. case::

      SKIPPED_X2_DEFAULT

TAKEN_X2_AFTER_MATCH
