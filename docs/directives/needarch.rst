{% raw %}

.. _needarch:

needarch
========

``needarch`` behaves exactly like :ref:`needuml`, but only works inside a need. It provides also addtional exclusive
jinja function :ref:`needarch_jinja_import`.

|ex|

.. code-block:: rst

   .. req:: Requirement arch
      :id: req_arch_001
         
      .. needarch::
         :scale: 50
         :align: center

         Alice -> Bob: Hi Bob
         Bob --> Alice: hi Alice

|out|

.. req:: Requirement arch
   :id: req_arch_001

   .. needarch::
      :scale: 50
      :align: center

      Alice -> Bob: Hi Bob
      Bob --> Alice: hi Alice

Jinja context
-------------

The following Jinja functions are **only available** for :ref:`needarch`. 


.. _needarch_jinja_need:

need()
~~~~~~

.. versionadded:: 1.0.3

The `need()` function provides you the need information the :ref:`needarch` / :ref:`needuml` is embedded in.

|ex|

.. code-block:: rst

   .. req:: Req Arch four
      :id: req_arch_004
      :status: draft
      :blocks: req_arch_001

      content.

      .. needarch::
         :scale: 50
         :align: center

         class "{{need().title}}" {
         {{need().status}}
         {% for e in need().blocks %}{{e}}
         {% endfor %}
         }

|out|

.. req:: Req Arch four
   :id: req_arch_004
   :status: draft
   :blocks: req_arch_001

   content.

   .. needarch::
      :scale: 50
      :align: center

      class "{{need().title}}" {
      {{need().status}}
      {% for e in need().blocks %}{{e}}
      {% endfor %}
      }


.. _needarch_jinja_import:

import(need_links_option_name)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This function takes undefined amounts of current need links option names as arguments.

Then it executes :ref:`needuml_jinja_uml` automatically for all links/need_ids defined from the given arguments.

|ex|

.. code-block:: rst

   .. req:: Req Arch second
      :id: req_arch_002

      content.

   .. req:: Req Arch third
      :id: req_arch_003

      some.

   .. test:: Test Arch
      :id: test_arch_001
      :checks: req_arch_001
      :tests: req_arch_002, req_arch_003

      Test need arch jinja import function.

      .. needarch::
         :scale: 50
         :align: center

         {{import("checks", "tests")}}

|out|

.. req:: Req Arch second
   :id: req_arch_002

   arch req content.

.. req:: Req Arch third
   :id: req_arch_003

   some req stuff.

.. spec:: Spec Arch first
   :id: spec_arch_001

   some spec content.

.. test:: Test Arch
   :id: test_arch_001
   :checks: req_arch_002
   :triggers: req_arch_003, spec_arch_001

   Test need arch jinja import function.

   .. needarch::
      :scale: 50
      :align: center

      {{import("checks", "triggers")}}


{% endraw %}
