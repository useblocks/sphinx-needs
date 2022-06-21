.. _needattribute:

needattribute
=============

.. versionadded:: 0.7.5

``needattribute`` adds a attribute to your documented :ref:`need`:

|ex|

.. code-block:: rst

    .. spec:: Example for needattribute
    :id: SPEC_NEEDATTRIBUTE_1
    :status: open

        .. needattribute:: multi_line_attribute

            multi
            line
            text

|out|

.. spec:: Example for needattribute
   :id: SPEC_NEEDATTRIBUTE_1
   :status: open

   .. needattribute:: multi_line_attribute

      multi
      line
      text

|ex|

|out|

.. req:: Component X as needattribute
   :id: COMP_X_NEEDATTRIBUTE
   :status: open

   We cannot use need comp, as it would treat all content as uml code, so let's
   use a "req" as a placeholder for a logical component.
   I used structure_model and activity_diagram to indicate that the naming is user defined.

   .. needattribute:: structure_model
      :uml:

      circle "Int A" as int

      class "Class A" as cl_a
      class "Class B" as cl_b

      cl_a o-- cl_b
      cl_a --> int

   .. needattribute:: activity_diagram
      :uml:

      circle "Int X" as int

      class "Class Y" as cl_a
      class "Class Z" as cl_b

      cl_a o-- cl_b
      cl_a --> int

