.. _needuml:

{% raw %}
needuml
=======

``neduml`` behaves exactly like the ``uml`` directive from the Sphinx extension
`Sphinxcontrib-PlantUML <https://github.com/sphinx-contrib/plantuml/>`_.
So it allows to define PlantUML diagrams.

The different is, that it also supports `Jinja <https://jinja.palletsprojects.com/>`_ statements, which allows
to use loops, if-clauses, and it injects data from need-objects.

.. code-block:: rst

   .. needuml::
      :scale: 50%
      :align: center

      class "{{needs['FEATURE_1'].title}}" {
        implement
        {{needs['FEATURE_1'].status}}
      }

.. needuml::
   :scale: 50%
   :align: center

   class "{{needs['FEATURE_1'].title}}" {
     implement
     {{needs['FEATURE_1'].status}}
   }

Options
-------

.. contents::
   :local:

extra
~~~~~
Allows to inject additional key-value pairs into the needuml rendering.
``extra`` must be a comma-separated list, containing `key:value` pairs.

.. code-block:: rst

   .. needuml::
      :extra: name:Roberto,work:RocketLab

      card "{{name}}" as a
      card "{{work}}" as b
      a -> b

.. needuml::
   :extra: name:Roberto,work:RocketLab

   card "{{name}}" as a
   card "{{work}}" as b
   a -> b

.. note::

   ``extra`` values are only available in the current PlantUML code.
   It is not available in code loaded via :ref:`jinja_uml`.

scale
~~~~~

align
~~~~~

config
~~~~~~

See needflow :ref:`needflow_config` for details.

debug
~~~~~

If ``debug`` is set, a debug-output of the generated PlantUML code gets added after the generated image.

Helpful to identify reasons why a PlantUML build may have thrown errors.

.. code-block:: rst

   .. needuml::
      :debug:

      node "RocketLab" {
         card "Peter"
      }

.. needuml::
   :debug:

   node "RocketLab" {
      card "Peter"
   }

Jinja context
-------------
When using Jinja statements, the following objects and functions are available.

needs
~~~~~
A Python dictionary, which contains all Needs. The ``need_id`` is used as key.

.. code-block:: rst

   .. needuml::

      node "{{needs["FEATURE_1"].title}}"

.. needuml::

      node "{{needs["FEATURE_1"].title}}"


.. _jinja_need:

need(id)
~~~~~~~~
Loads a Sphinx-Need object as PlantUML object.
The used layout is the same one as used for :ref:`needflow`.

This functions represents each Need the same way.


.. code-block:: rst

   .. needuml::

      {{need("COMP_001")}}
      {{need("FEATURE_1")}}


.. needuml::

      {{need("COMP_001")}}
      {{need("FEATURE_1")}}

.. _jinja_uml:

uml(id)
~~~~~~~
Loads a Sphinx-Need object as PlantUML object or reuses the stored PlantUML code inside the Sphinx-Need object.
This depends on the used :ref:`needs_types` and its ``content`` value.

If ``content="plantuml"``, the stored PlantUML diagram gets completely imported.
Otherwise a Sphinx-Needs objects representation is used (same as in :ref:`jinja_need`).


.. code-block:: rst

   .. needuml::

      {{uml("COMP_001")}}
      {{uml("FEATURE_1")}}


.. needuml::

   {{uml("COMP_001")}}
   {{uml("FEATURE_1")}}

Additional keyword arguments
++++++++++++++++++++++++++++

``uml()`` supports to set additional parameters, which are then available in the loaded PlantUML code.

**Example Need object**

.. comp:: Variant A or B
   :id: COMP_A_B

   {% if variant == "A" %}
    class "A" as cl
   {% elif variant == "B" %}
    class "B" as cl {
        attribute_x
        function_x()
    }
   {% else %}
    class "Unknown" as cl
   {% endif %}

.. code-block:: rst

   .. comp:: Variant A or B
      :id: COMP_A_B

      {% if variant == "A" %}
        class "A" as cl
      {% elif variant == "B" %}
        class "B" as cl {
            attribute_x
            function_x()
        }
      {% else %}
        class "Unknown" as cl
      {% endif %}

**Example for Variant A**

.. code-block:: rst

   .. needuml::

      {{uml("COMP_A_B", variant="A")}}

.. needuml::

   {{uml("COMP_A_B", variant="A")}}

**Example for Variant B**

.. code-block:: rst

   .. needuml::

      {{uml("COMP_A_B", variant="B")}}

.. needuml::

   {{uml("COMP_A_B", variant="B")}}


Chaining diagrams
+++++++++++++++++
As PlantUML Need objects are using internally ``needuml`` to define their diagrams, all
features are available and ``uml()`` can be used multiple time on different levels of a planned architecture.


.. tab-set::

    .. tab-item:: Needs

        .. int:: Interface A
           :id: INT_A

           circle "Int A" as int

        .. comp:: Component X
           :id: COMP_X

           {{uml("INT_A")}}

           class "Class A" as cl_a
           class "Class B" as cl_b

           cl_a o-- cl_b
           cl_a --> int

        .. sys:: System RocketScience
           :id: SYS_ROCKET

           node "RocketScience" as rocket {
               {{uml("COMP_X")}}
               card "Service Y" as service

               int --> service
           }

        And finally a ``needuml`` to make use of the Sphinx-Need system object:

        .. needuml::

              {{uml("SYS_ROCKET")}}

              actor "A friend" as me #ff5555

              me --> rocket: doing


    .. tab-item:: Code

        .. code-block:: rst

            .. int:: Interface A
               :id: INT_A

               circle "Int A" as int

            .. comp:: Component X
               :id: COMP_X

               {{uml("INT_A")}}

               class "Class A" as cl_a
               class "Class B" as cl_b

               cl_a o-- cl_b
               cl_a --> int

            .. sys:: System RocketScience
               :id: SYS_ROCKET

               node "RocketScience" {
                   {{uml("COMP_X")}}
                   card "Service Y" as service

                   int --> service
               }

            And finally a ``needuml`` to make use of the Sphinx-Need system object:

            .. needuml::

                  {{uml("SYS_ROCKET")}}

                  actor "A friend" as me #ff5555

                  me --> rocket: doing


Examples
--------

.. code-block:: rst

   .. needuml::

      allowmixing

      class "Sphinx-Needs" as sn {
        requirements
        specifications
        test_cases
        customize()
        automate()
        export()
      }

      {% set ids = ["FEATURE_1", "FEATURE_5", "FEATURE_7"]%}
      {% for need in needs.values() %}
          {% if need.id in ids %}
              card "{{need['title']}}" as need_{{loop.index}} #ffcc00
              need_{{loop.index}} --> sn
          {% endif %}
      {% endfor %}

      card "and much more..." as much #ffcc00
      much -> sn


.. needuml::
   :scale: 50%
   :align: right

   allowmixing

   class "Sphinx-Needs" as sn {
     requirements
     specifications
     test_cases
     customize()
     automate()
     export()
   }

   {% set ids = ["FEATURE_1", "FEATURE_5", "FEATURE_7"]%}
   {% for need in needs.values() %}
       {% if need.id in ids %}
           card "{{need['title']}}" as need_{{loop.index}} #ffcc00
           need_{{loop.index}} --> sn
       {% endif %}
   {% endfor %}

   card "and much more..." as much #ffcc00
   much -> sn

{% endraw %}

.. comp:: Component X
   :id: COMP_001

   class "Class X" as class_x {
     attribute_1
     attribute_2
     function_1()
     function_2()
     function_3()
   }

   class "Class Y" as class_y {
     attribute_1
     function_1()
   }

   class_x o-- class_y
