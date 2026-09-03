TEST DOCUMENT NEEDUML FILTER FUNCTION
=====================================

.. story:: Test story
   :id: ST_001
   :status: open

   Some content

.. story:: Test story 02
   :id: ST_002
   :status: closed

   Another content

.. int:: Test needuml filter function
   :id: INT_001

   .. needuml::

      DC -> Marvel: Hi Kevin
      Marvel --> DC: Anyone there?

      {% for need in filter("type == 'story' and status != 'open'") %}
      {{uml(need.id)}}
      {% endfor %}
