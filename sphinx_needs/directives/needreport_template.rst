{# Output for needs_types #}
{% if types|length != 0 %}

.. {{ report_directive }}:: Need Types

   .. list-table::
      :widths: 40 20 20 20
      :header-rows: 1

      * - TITLE
        - DIRECTIVE
        - PREFIX
        - STYLE
      {% for type in types %}
      * - {{ type.title }}
        - {{ type.directive }}
        - `{{ type.prefix }}`
        - {{ type.style }}
      {% endfor %}
{% endif %}
{# Output for needs_types #}

{# Output for needs_extra_links #}
{% if links|length != 0 %}

.. {{ report_directive }}:: Need Extra Links

   .. list-table::
      :widths: 10 30 30 5 20
      :header-rows: 1

      * - OPTION
        - INCOMING
        - OUTGOING
        - COPY
        - ALLOW DEAD LINKS
      {% for link in links %}
      * - {{ link.option | capitalize }}
        - {{ link.incoming | capitalize }}
        - {{ link.outgoing | capitalize }}
        - {{ link.get('copy', None) | capitalize }}
        - {{ link.get('allow_dead_links', False) | capitalize }}
      {% endfor %}
{% endif %}
{# Output for needs_extra_links #}

{# Output for needs_options #}
{% if options|length != 0 %}

.. {{ report_directive }}:: Need Extra Options

   {% for option in options %}
   * {{ option }}
   {% endfor %}
{% endif %}
{# Output for needs_options #}

{# Output for needs metrics #}
{% if usage|length != 0 %}

.. {{ report_directive }}:: Need Metrics

   .. list-table::
      :widths: 40 40
      :header-rows: 1

      * - NEEDS TYPES
        - NEEDS PER TYPE
      {% for k, v in usage["needs_types"].items() %}
      * - {{ k | capitalize }}
        - {{ v }}
      {% endfor %}
      * - **Total Needs Amount**
        - {{ usage.get("needs_amount") }}
{% endif %}
{# Output for needs metrics #}
