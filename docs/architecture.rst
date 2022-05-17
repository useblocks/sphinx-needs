Architecture Elements
=====================
Sphinx-Needs allows to create and maintain reusable Architecture elements, which are based on the
diagram language `PlantUML <https://plantuml.com/>`_.

By using this Need types the content part is supporting PlantUML code only, no rst or markdown content is allowed.

Configuration
-------------
Each need type can be configured to use the content type "plantuml".
There can be as many "Architecture" types as needed. For instance for system, component and interfaces.

.. code-block:: rst
   :emphasize-lines: 4

    needs_types = [
        dict(directive="comp",
             title="Component",
             content="plantuml"
             prefix="C_",
             color="#BFD8D2",
             style="node")]

``content="plantuml"`` activates a specific handling for this need type. By default ``content`` is set to ``sphinx``.

Usage
-----


.. code-block:: rst

   .. comp:: My architecture component
      :id: COMP_A
      :status: open

      package "Component A" as comp_a {
        class "User"
        class Address
      }

.. comp:: My architecture component
   :id: COMP_A
   :status: open

   package "Component A" as comp_a {
     class "User"
     class Address
   }





