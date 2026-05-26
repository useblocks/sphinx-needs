IF Directive Test
=================

True condition
--------------

.. if:: var.arch == "abc"

   INCLUDED_ARCH_ABC

False condition
---------------

.. if:: var.arch == "xyz"

   EXCLUDED_ARCH_XYZ

Boolean truthiness
------------------

.. if:: var.debug

   INCLUDED_DEBUG_TRUE

.. if:: not var.debug

   EXCLUDED_DEBUG_FALSE

Nested access
-------------

.. if:: var.build.opt > 1

   INCLUDED_BUILD_OPT

.. if:: var.build.opt > 99

   EXCLUDED_BUILD_OPT_HIGH

Membership test
---------------

.. if:: "f1" in var.build.features

   INCLUDED_FEATURE_F1

.. if:: "missing" in var.build.features

   EXCLUDED_FEATURE_MISSING

Nested if directives
--------------------

.. if:: var.debug

   OUTER_IF_CONTENT

   .. if:: var.arch == "abc"

      NESTED_IF_CONTENT

Header inside if
-----------------

.. if:: var.arch == "abc"

   Conditional section
   ~~~~~~~~~~~~~~~~~~~

   INCLUDED_SECTION_CONTENT

.. if:: var.arch == "xyz"

   Skipped section
   ~~~~~~~~~~~~~~~

   EXCLUDED_SECTION_CONTENT

Needs inside if
---------------

.. if:: var.arch == "abc"

   .. req:: A conditional requirement
      :id: REQ_CONDITIONAL

      This requirement only exists when arch is abc.

.. if:: var.arch == "xyz"

   .. req:: A skipped requirement
      :id: REQ_SKIPPED

      This requirement should not exist.
