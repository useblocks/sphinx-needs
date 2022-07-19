{% raw %}

.. _needuml:

needuml
=======

``needuml`` behaves exactly like the ``uml`` directive from the Sphinx extension
`Sphinxcontrib-PlantUML <https://github.com/sphinx-contrib/plantuml/>`_.
So it allows to define PlantUML diagrams.

But gives you access to need object data by supporting `Jinja <https://jinja.palletsprojects.com/>`_ statements,
which allows you to use loops, if-clauses, and it injects data from need-objects.

|ex|

.. code-block:: rst

   .. needuml::

      class "{{needs['FEATURE_1'].title}}" {
        implement
        {{needs['FEATURE_1'].status}}
      }

|out|

.. needuml::

   class "{{needs['FEATURE_1'].title}}" {
     implement
     {{needs['FEATURE_1'].status}}
   }

Options
-------

extra
~~~~~
Allows to inject additional key-value pairs into the ``needuml`` rendering.
``:extra:`` must be a comma-separated list, containing *key:value* pairs.

|ex|

.. code-block:: rst

   .. needuml::
      :extra: name:Roberto,work:RocketLab

      card "{{name}}" as a
      card "{{work}}" as b
      a -> b

|out|

.. needuml::
   :extra: name:Roberto,work:RocketLab

   card "{{name}}" as a
   card "{{work}}" as b
   a -> b

.. note::

   ``:extra:`` values are only available in the current PlantUML code.
   It is not available in code loaded via :ref:`jinja_uml`.

config
~~~~~~
Allows to preconfigure PlantUML and set certain layout options.

For details please take a look into needflow :ref:`needflow_config`.

debug
~~~~~

If ``:debug:`` is set, a debug-output of the generated PlantUML code gets added after the generated image.

Helpful to identify reasons why a PlantUML build may have thrown errors.

|ex|

.. code-block:: rst

   .. needuml::
      :debug:

      node "RocketLab" {
         card "Peter"
      }

|out|

.. needuml::
   :debug:

   node "RocketLab" {
      card "Peter"
   }

key
~~~

Allows to store multiple ``needuml`` inside a need under the given key. If no option key given, then
the first ``needuml`` will be stored in the need under ``diagram``. Option ``:key:`` value can't be empty,
and can't be ``diagram``. 

|ex|

.. code-block:: rst

   .. comp:: Component Y
      :id: COMP_002

      .. needuml::
         :key: sequence

         Alice -> Bob: Hi Bob
         Bob --> Alice: Hi Alice

      .. needuml::
         :key: class

         class System_A as A {
            todo
            open
         }

      .. needuml::

         B -> C: Hi
         C -> B: Hi there

|out|

.. comp:: Component Y
   :id: COMP_002

   .. needuml::
      :key: sequence

      Alice -> Bob: Hi Bob
      Bob --> Alice: Hi Alice

   .. needuml::
      :key: class

      class Foo

   .. needuml::

      B -> C: Hi
      C -> B: Hi there

save
~~~~

Specifies the file path to store generated Plantuml-code of current ``needuml``. This given file path can be relative path
or file name, e.g. ``needuml_group_A/my_needuml.puml`` or ``my_needuml.puml``.

The file will be created and written during each build by 
using builder :ref:`needumls_builder` or other builder like `html` with configuration option :ref:`needs_build_needumls` configured.

If given file path already exists, it will be overwritten.

|ex|

.. code-block:: rst

   .. int:: Test needuml save
      :id: INT_001

      .. needuml::
         :save: needuml_group_A/my_needuml.puml

         Alice -> Bob: Hi Bob
         Bob --> Alice: Hi Alice

In this example, if builder :ref:`needumls_builder` is used, the plantuml-code will be exported to file at `outdir` of current builder,
e.g. `_build/needumls/needuml_group_A/my_needuml.puml`.

|out|

.. int:: Test needuml save
   :id: INT_001

   .. needuml::
      :save: needuml_group_A/my_needuml.puml

      Alice -> Bob: Hi Bob
      Bob --> Alice: Hi Alice

Jinja context
-------------
When using Jinja statements, the following objects and functions are available.

needs
~~~~~
A Python dictionary containing all Needs. The ``need_id`` is used as key.

|ex|

.. code-block:: rst

   .. needuml::

      node "{{needs["FEATURE_1"].title}}"

|out|

.. needuml::

      node "{{needs["FEATURE_1"].title}}"


.. _jinja_need:

need(id)
~~~~~~~~
Loads a Sphinx-Need object as PlantUML object.
We use the same layout used for :ref:`needflow`.

This functions represents each Need the same way.

|ex|

.. code-block:: rst

   .. needuml::

      allowmixing

      {{need("COMP_001")}}
      {{need("FEATURE_1")}}

|out|

.. needuml::

   allowmixing

   {{need("COMP_001")}}
   {{need("FEATURE_1")}}


.. _jinja_filter:

filter(filter_string)
~~~~~~~~~~~~~~~~~~~~~
Finds a list of Sphinx-Need objects that pass the given filter string.

|ex|

.. code-block:: rst

   .. needuml::

      {% for need in filter("type == 'int' and status != 'open'") %}
      node "{{need.title}}"
      {% endfor %}

|out|

.. needuml::

      {% for need in filter("type == 'int' and status != 'open'") %}
      node "{{need.title}}"
      {% endfor %}


.. _jinja_uml:

uml(id)
~~~~~~~
Loads a Sphinx-Need object as PlantUML object or reuses the stored PlantUML code inside the Sphinx-Need object.

If diagram code is available in the need data under ``diagram``, the stored PlantUML diagram gets imported.

Please read :ref:`need_diagram` for details.


|ex|

.. code-block:: rst

   .. needuml::

      allowmixing

      {{uml("COMP_001")}}
      {{uml("FEATURE_1")}}

|out|

.. needuml::

   allowmixing

   {{uml("COMP_001")}}
   {{uml("FEATURE_1")}}

Key argument
++++++++++++

:ref:`uml() <jinja_uml>` supports ``key`` argument to define which PlantUML code to load from the Sphinx-Need object.
``key`` value by default is ``diagram``. If no key argument given, then the PlantUML code is loaded from ``diagram``.

|ex|

.. code-block:: rst

   .. comp:: Z
      :id: COMP_Z

      .. needuml::

         {{uml('COMP_002', 'sequence')}}

|out|

.. comp:: Z
   :id: COMP_Z

   .. needuml::

      {{uml('COMP_002', 'sequence')}}

Additional keyword arguments
++++++++++++++++++++++++++++

:ref:`uml() <jinja_uml>` supports additional keyword parameters which are then available in the loaded PlantUML code.

|ex|

.. code-block:: rst

   .. comp:: Variant A or B
      :id: COMP_A_B

      .. needuml::

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

      By default **Unknown** is shown, as no variant was set.

|out|

.. comp:: Variant A or B
   :id: COMP_A_B

   .. needuml::

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

   By default **Unknown** is shown, as no variant was set.


Passing ``variant="A"`` parameter to the :ref:`uml() <jinja_uml>` function, we get the following:

|ex|

.. code-block:: rst

   .. needuml::

      {{uml("COMP_A_B", variant="A")}}

|out|

.. needuml::

   {{uml("COMP_A_B", variant="A")}}

Passing ``variant="B"`` parameter to the :ref:`uml() <jinja_uml>` function, we get the following:

|ex|

.. code-block:: rst

   .. needuml::

      {{uml("COMP_A_B", variant="B")}}

|out|

.. needuml::

   {{uml("COMP_A_B", variant="B")}}


Chaining diagrams
+++++++++++++++++
PlantUML Need objects uses the ``needuml`` directive internally to define their diagrams.
All features are available and ``uml()`` can be used multiple time on different levels of a planned architecture.


.. tab-set::

    .. tab-item:: Needs

        .. int:: Interface A
           :id: INT_A

           .. needuml::

              circle "Int A" as int

        .. comp:: Component X
           :id: COMP_X

           .. needuml::

               allowmixing

               {{uml("INT_A")}}

               class "Class A" as cl_a
               class "Class B" as cl_b

               cl_a o-- cl_b
               cl_a --> int

        .. sys:: System RocketScience
           :id: SYS_ROCKET

           .. needuml::

               allowmixing

               node "RocketScience" as rocket {
                   {{uml("COMP_X")}}
                   card "Service Y" as service

                   int --> service
               }

        And finally a ``needuml`` to make use of the Sphinx-Need system object:

        .. needuml::

            allowmixing

            {{uml("SYS_ROCKET")}}

            actor "A friend" as me #ff5555

            me --> rocket: doing


    .. tab-item:: Code

        .. code-block:: rst

            .. int:: Interface A
               :id: INT_A

               .. needuml::

                  circle "Int A" as int

            .. comp:: Component X
               :id: COMP_X

               .. needuml::

                  allowmixing

                  {{uml("INT_A")}}

                  class "Class A" as cl_a
                  class "Class B" as cl_b

                  cl_a o-- cl_b
                  cl_a --> int

            .. sys:: System RocketScience
               :id: SYS_ROCKET

               .. needuml::

                  allowmixing

                  node "RocketScience" {
                      {{uml("COMP_X")}}
                      card "Service Y" as service

                      int --> service
                  }

            And finally a ``needuml`` to make use of the Sphinx-Need system object:

            .. needuml::

               allowmixing

               {{uml("SYS_ROCKET")}}

               actor "A friend" as me #ff5555

               me --> rocket: doing


NeedUml Examples
----------------

|ex|

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

|out|

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

|ex|

.. code-block:: rst

    .. comp:: Component X
       :id: COMP_001

       .. needuml::

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

|out|

.. comp:: Component X
   :id: COMP_001

   .. needuml::

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
