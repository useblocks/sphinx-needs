{% for key, need in needs_list|dictsort -%}

.. {{need.type}}:: {{need.title}}
   :id: {{id_prefix}}{{need.id}}
   :status: {{need.status}}
   {% if need.links|length > 0 -%}
   :links: {{need.links|join(',')}}
   {% endif -%}
   {% if need.tags|length > 0 -%}
   :tags: {{need.tags|join(',')}}
   {% endif -%}
   {% if hide or need.hide -%}
   :hide:
   {% endif %}
   {% for line in need.description.split('\n') -%}
   {{ line }}
   {% endfor %}
{% endfor %}