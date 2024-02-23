extensions = ["sphinx_needs"]

needs_extra_options = [
    "introduced",
    "updated",
    "impacts",
]

needs_template_collapse = """
.. _{{id}}:

{% if hide == false -%}
.. role:: needs_tag
.. role:: needs_status
.. role:: needs_type
.. role:: needs_id
.. role:: needs_title

.. rst-class:: need
.. rst-class:: need_{{type_name}}

.. container:: need

    `{{id}}` - {{content|indent(4)}}

    .. container:: toggle

        .. container:: header

            Details

{% if status and  status|upper != "NONE" and not hide_status %}        | status: :needs_status:`{{status}}`{% endif %}
{% if tags and not hide_tags %}        | tags: :needs_tag:`{{tags|join("` :needs_tag:`")}}`{% endif %}
{% if introduced %}        | introduced: `{{introduced}}` {% endif %}
{% if updated %}        | updated: `{{updated}}` {% endif %}
{% if impacts %}        | impacts: `{{impacts}}` {% endif %}
        | links incoming: :need_incoming:`{{id}}`
        | links outgoing: :need_outgoing:`{{id}}`

{% endif -%}
"""
