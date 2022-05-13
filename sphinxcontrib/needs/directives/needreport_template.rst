{% if types %}

.. container:: needs_report_table

    .. raw:: html

        <table class="colwidths-auto docutils align-left">
            <thead>
                <tr><th class="head align-center" colspan="4"><p>Need Types</p></th></tr>
            </thead>
            <tbody>
                <tr>
                    <td><b>TITLE</b></td>
                    <td><b>DIRECTIVE</b></td>
                    <td><b>PREFIX</b></td>
                    <td><b>STYLE</b></td>
                </tr>

                {% for type in types %}
                    {% set type_index = (loop.index - 1) % 2 %}
                    <tr class="{% if type_index == 0 %} row-even {% else %} row-odd {% endif %}">
                        <td>{{ type.title }}</td>
                        <td>{{ type.directive }}</td>
                        <td>{{ type.prefix }}</td>
                        <td>{{ type.style }}</td>
                    </tr>
                {% endfor %}

            </tbody>
        </table>

{% endif %}