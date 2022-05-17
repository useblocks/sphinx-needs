.. _needuml:

{% raw %}
needuml
=======

``neduml`` behaves exactly like the ``uml`` directive from the Sphinx extension
`Sphinxcotrib-PlantUML <https://github.com/sphinx-contrib/plantuml/>`_.
So it allows to define PlantUML diagrams.

The different is, that it also supports `Jinja <https://jinja.palletsprojects.com/>`_ statements, which allows
to use loops, if-clauses, and it injects data from need-objects.

.. code-block:: rst

   .. needuml::
      :scale: 50%
      :align: center

      class "{{needs['FEATURE_1'].title}}" {
        implement
        needs['FEATURE_1'].status
      }

.. needuml::
   :scale: 50%
   :align: center

   class "{{needs['FEATURE_1'].title}}" {
     implement
     needs['FEATURE_1'].status
   }


Jinja architecture functions
----------------------------

uml
~~~

.. code-block:: rst

   .. needuml::

      {{uml("FEATURE_1")}}


.. needuml::

   {{uml("FEATURE_1")}}


Example
-------

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
