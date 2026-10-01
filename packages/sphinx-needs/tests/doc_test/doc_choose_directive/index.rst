CHOOSE Test
===========

.. toctree::

   other

P1 first true branch wins
-------------------------

The conditions after the taken branch are never evaluated,
so the invalid one and the unknown key cannot warn.

.. choose::

   .. when:: var.arch == "abc"

      TAKEN_P1_FIRST

   .. when:: var.debug

      SKIPPED_P1_SECOND_TRUE

   .. when:: this is not python !!!

      SKIPPED_P1_INVALID_SYNTAX

   .. when:: var.no_such_key == 1

      SKIPPED_P1_UNKNOWN_KEY

   .. when::

      SKIPPED_P1_DEFAULT

P2 default taken when no branch holds
-------------------------------------

.. choose::

   .. when:: var.arch == "xyz"

      SKIPPED_P2_FALSE

   .. a comment between two branches

   .. when::

      TAKEN_P2_DEFAULT

P2b no branch holds and there is no default
-------------------------------------------

.. choose::

   .. when:: var.arch == "xyz"

      SKIPPED_P2B_1

   .. when:: not var.debug

      SKIPPED_P2B_2

TAKEN_P2B_AFTER_CHOOSE

P3 needs in branches
--------------------

.. choose::

   .. when:: var.arch == "xyz"

      .. req:: In a branch that is not taken
         :id: REQ_P3_SKIPPED

   .. when:: var.arch == "abc"

      .. req:: In the taken branch
         :id: REQ_P3_TAKEN

   .. when::

      .. req:: In a default that is not taken
         :id: REQ_P3_DEFAULT_SKIPPED

P4 sections in the taken branch
-------------------------------

.. choose::

   .. when:: var.debug

      P4 conditional heading
      ~~~~~~~~~~~~~~~~~~~~~~

      TAKEN_P4_SECTION_BODY

   .. when::

      P4 skipped heading
      ~~~~~~~~~~~~~~~~~~

      SKIPPED_P4_BODY

P5 nested choose
----------------

.. choose::

   .. when:: var.debug

      TAKEN_P5_OUTER

      .. choose::

         .. when:: var.arch == "xyz"

            SKIPPED_P5_INNER

         .. when::

            TAKEN_P5_INNER_DEFAULT

   .. when::

      SKIPPED_P5_OUTER

P5b choose in the content of a need
-----------------------------------

The need is extracted on the other page,
which renders its content from the need-node cache.

.. req:: Host with choose content
   :id: REQ_HOST

   .. choose::

      .. when:: var.arch == "xyz"

         SKIPPED_P5B_IN_NEED

      .. when:: var.arch == "abc"

         TAKEN_P5B_IN_NEED

      .. when::

         SKIPPED_P5B_IN_NEED_DEFAULT

X1 a whole choose in an included file
-------------------------------------

The choose and its branches are written in the same (included) file,
which is fine; branches an include supplies to a choose written elsewhere are refused.

.. include:: included_choose.txt

X2 an include inside the taken branch
-------------------------------------

.. choose::

   .. when:: var.debug

      .. include:: taken_body.txt

      TAKEN_X2_AFTER_INCLUDE

   .. when::

      SKIPPED_X2_DEFAULT

TAKEN_X2_AFTER_CHOOSE
