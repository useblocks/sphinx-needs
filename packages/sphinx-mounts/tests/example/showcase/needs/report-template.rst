{# Jinja template for needreport.rst, addressed bundle-relative via its
   ``:template:`` option. Deliberately plain RST: the Sphinx-Needs default
   template emits ``dropdown`` directives, which would drag a sphinx-design
   dependency into the host project -- exactly the kind of coupling a
   self-contained bundle should avoid. Owning the template keeps the bundle's
   requirements to sphinx-needs alone.

   This file keeps the conventional ``.rst`` suffix, which is why the mount in
   ``ubproject.toml`` lists it under ``exclude``: it is template input, not a
   document, and without the exclude the directory mount would pick it up as
   one (an orphan page full of unrendered Jinja). #}
SHOWCASE_NEEDREPORT_TEMPLATE

.. list-table:: Need types configured for this project
   :widths: 40 20 20 20
   :header-rows: 1

   * - TITLE
     - DIRECTIVE
     - PREFIX
     - STYLE
   {% for type in types %}
   * - {{ type.title }}
     - ``{{ type.directive }}``
     - ``{{ type.prefix }}``
     - {{ type.style }}
   {% endfor %}
