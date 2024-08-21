

.. _needuml:

needuml
=======

``needuml`` behaves exactly like the ``uml`` directive from the Sphinx extension
`Sphinxcontrib-PlantUML <https://github.com/sphinx-contrib/plantuml/>`_.
So it allows to define PlantUML diagrams.

But gives you access to need object data by supporting `Jinja <https://jinja.palletsprojects.com/>`_ statements,
which allows you to use loops, if-clauses, and it injects data from need-objects.

.. need-example::

   .. needuml::

      {{uml('FEATURE_NEEDUML1')}}
      {{uml('COMP_NEEDUML2')}}

   .. feature:: NeedUml example need
      :id: FEATURE_NEEDUML1
      :tags: needuml
      :status: draft

      Example Need for NeedUml.

   .. comp:: NeedUml example need 2
      :id: COMP_NEEDUML2
      :tags: needuml
      :status: draft

      Second example Need for NeedUml.

      .. needuml::

         {{flow('COMP_NEEDUML2')}} {
         card implement
         card {{needs['COMP_NEEDUML2'].status}}
         }

.. _needuml_options:

Options
-------


.. _needuml_extra:

extra
~~~~~
Allows to inject additional key-value pairs into the ``needuml`` rendering.
``:extra:`` must be a comma-separated list, containing *key:value* pairs.

.. need-example::

   .. needuml::
      :extra: name:Roberto,work:RocketLab

      card "{{name}}" as a
      card "{{work}}" as b
      a -> b

.. note::

   ``:extra:`` values are only available in the current PlantUML code.
   It is not available in code loaded via :ref:`needuml_jinja_uml`.
   So we suggest to use them only in non-embedded needuml directives.
   In an embedded needuml, you can store the information in the options
   of the need and access them with :ref:`needflow` like in
   :ref:`needuml` introduction.


.. _needuml_config:

config
~~~~~~
Allows to preconfigure PlantUML and set certain layout options.

For details please take a look into needflow :ref:`needflow_config`.


.. _needuml_debug:

debug
~~~~~

If ``:debug:`` is set, a debug-output of the generated PlantUML code gets added after the generated image.

Helpful to identify reasons why a PlantUML build may have thrown errors.

.. need-example::

   .. needuml::
      :debug:

      node "RocketLab" {
         card "Peter"
      }

.. _needuml_key:

key
~~~

Allows to store multiple ``needuml`` inside a need under ``arch`` under the given key, e.g. ``need["arch"]["key_name"]``.
If no option key given, then the first ``needuml`` will be stored in the need under ``arch`` under ``diagram``, ``need["arch"]["diagram"]``.
Option ``:key:`` value can't be empty, and can't be ``diagram``.

.. need-example::

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

.. _needuml_save:

save
~~~~

Specifies the file path to store generated Plantuml-code of current ``needuml``. This given file path can be relative path
or file name, e.g. ``needuml_group_A/my_needuml.puml`` or ``my_needuml.puml``.

The file will be created and written during each build by 
using builder :ref:`needumls_builder` or other builder like `html` with configuration option :ref:`needs_build_needumls` configured.

If given file path already exists, it will be overwritten.

.. need-example::

   .. int:: Test needuml save
      :id: INT_001

      .. needuml::
         :save: needuml_group_A/my_needuml.puml

         Alice -> Bob: Hi Bob
         Bob --> Alice: Hi Alice

In this example, if builder :ref:`needumls_builder` is used, the plantuml-code will be exported to file at `outdir` of current builder,
e.g. `_build/needumls/needuml_group_A/my_needuml.puml`.


.. _needuml_jinja:

Jinja context
-------------
When using Jinja statements, the following objects and functions are available.


.. _needuml_jinja_needs:

needs
~~~~~
A Python dictionary containing all Needs. The ``need_id`` is used as key.

.. need-example::

   .. needuml::

      node "{{needs["FEATURE_NEEDUML1"].title}}"


.. _needuml_jinja_flow:

flow(id)
~~~~~~~~
Loads a Sphinx-Need object as PlantUML object.
We use the same layout used for :ref:`needflow`.

This functions represents each Need the same way.

.. versionchanged:: 1.0.3
   In the past the returned plantuml representation string ends with a
   newline. Now it is up to the author of the Jinja template to write
   the newline, which is normally anyway the case. E.g. see the following
   example, where the two `flow()` are separated by a newlone. With this
   approach it is possible to write plantuml code following `flow()`.
   E.g. see even the following example, with text following 
   `{{flow("COMP_001")}}`.

.. need-example::

   .. needuml::

      {{flow("FEATURE_NEEDUML1")}}
      {{flow("COMP_001")}} {
      card manuall_written
      }


.. _needuml_jinja_filter:

filter(filter_string)
~~~~~~~~~~~~~~~~~~~~~
Finds a list of Sphinx-Need objects that pass the given filter string.

.. need-example::

   .. needuml::

      {% for need in filter("type == 'int' and status != 'open'") %}
      node "{{need.title}}"
      {% endfor %}


.. _needuml_jinja_ref:

ref(id, option, text)
~~~~~~~~~~~~~~~~~~~~~

Allows to create an hyperlink to a Sphinx-Need object in a PlantUML schema. The
text associated to the hyperlink is either defined by `option` (in this case,
Sphinx-Need picks the text of the field specified by `option`), or by the free text `text`.


.. need-example::

   .. needuml::

      Alice -> Bob: {{ref("FEATURE_NEEDUML1", option="title")}}
      Bob -> Alice: {{ref("COMP_NEEDUML2", text="A completely free text")}}

.. _needuml_jinja_uml:

uml(id)
~~~~~~~
Loads a Sphinx-Need object as PlantUML object or reuses the stored PlantUML code inside the Sphinx-Need object.

If diagram code is available in the need data under ``arch``, the stored PlantUML diagram gets imported.

Please read :ref:`need_diagram` for details.


.. need-example::

   .. needuml::

      allowmixing

      {{uml("COMP_001")}}
      {{uml("FEATURE_NEEDUML1")}}


.. _needuml_jinja_uml_key:

Key argument
++++++++++++

:ref:`uml() <needuml_jinja_uml>` supports ``key`` argument to define which PlantUML code to load from the Sphinx-Need object.
``key`` value by default is ``diagram``. If no key argument given, then the PlantUML code is loaded from ``diagram`` under ``arch``
inside the need object.

.. need-example::

   .. comp:: Z
      :id: COMP_Z

      .. needuml::

         {{uml('COMP_002', 'sequence')}}


.. _needuml_jinja_uml_args:

Additional keyword arguments
++++++++++++++++++++++++++++

:ref:`uml() <needuml_jinja_uml>` supports additional keyword parameters which are then available in the loaded PlantUML code.

.. need-example::

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


Passing ``variant="A"`` parameter to the :ref:`uml() <needuml_jinja_uml>` function, we get the following:

.. need-example::

   .. needuml::
      :debug:

      {{uml("COMP_A_B", variant="A")}}

Passing ``variant="B"`` parameter to the :ref:`uml() <needuml_jinja_uml>` function, we get the following:

.. need-example::

   .. needuml::
      :debug:

      {{uml("COMP_A_B", variant="B")}}


.. _needuml_jinja_uml_chain:

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


.. _needuml_example:

NeedUml Examples
----------------

.. need-example::

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

      {% set ids = ["FEATURE_NEEDUML1", "COMP_NEEDUML2"]%}
      {% for need in needs.values() %}
         {% if need.id in ids %}
            card "{{need['title']}}" as need_{{loop.index}} #ffcc00
            need_{{loop.index}} --> sn
         {% endif %}
      {% endfor %}

      card "and much more..." as much #ffcc00
      much -> sn

.. need-example::

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
