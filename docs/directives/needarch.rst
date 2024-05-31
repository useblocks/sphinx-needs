

.. _needarch:

needarch
========

``needarch`` behaves exactly like :ref:`needuml`, but only works inside a need. It provides also additional exclusive
jinja functions :ref:`needarch_jinja_need` and :ref:`needarch_jinja_import`.

.. need-example::

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

The `need()` function provides you the need information the :ref:`needarch` is embedded in.

.. need-example::

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

.. need-example::

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

.. _needarch_ex_loop:

NeedArch Loop Example
---------------------

.. versionadded:: 1.0.3

NeedArch can detect include loops `(uml('1') -> uml('2') -> uml('3') -> uml('1')`
and can avoid to include an element twice. Maybe this is not always the use case
you have, if so please create an issue and mention this chapter. The algorithm
does detect different parameter sets and does import `uml()` calls with different
:ref:`parameter <needuml_jinja_uml_args>` to the same need.

.. need-example::

   .. comp:: COMP_T_001
      :id: COMP_T_001

      .. needarch::

         {{flow(need().id)}}
         {% if variant == "A" %}
         {{uml('COMP_T_003', variant="A")}}
         usecase {{need().id}}_usecase
         {% else %}
         {{uml('COMP_T_003')}}
         {{uml('COMP_T_003', variant="A")}}
         {% endif %}

   .. comp:: COMP_T_002
      :id: COMP_T_002

      .. needarch::

         {{flow(need().id)}}
         {% if variant == "A" %}
         {{uml('COMP_T_001', variant="A")}}
         usecase {{need().id}}_usecase
         {% else %}
         {{uml('COMP_T_001')}}
         {% endif %}

   .. comp:: COMP_T_003
      :id: COMP_T_003

      .. needarch::

         {{flow(need().id)}}
         {% if variant == "A" %}
         {{uml('COMP_T_002', variant="A")}}
         usecase {{need().id}}_usecase
         {% else %}
         {{uml('COMP_T_002')}}
         {% endif %}
