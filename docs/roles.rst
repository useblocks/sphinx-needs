.. _roles:

Roles
=====

Roles can be used to get short information of needs inside single sentences::

    My specification :need:`my_spec` is used to fulfill requirements :need_incoming:`my_spec`

.. _role_need:

need
----

The role ``:need:`` will add title, id and a link to the need.

It is mostly used to reference an existing need, without the need to keep title and link location manually in sync.

Example
~~~~~~~

.. req:: Sliced Bread
   :id: roles_req_1

.. code-block:: jinja

   The requirement :need:`roles_req_1` is the most important one.

**Result**: The requirement :need:`roles_req_1` is the most important one.

.. note::

   The string representation can be easily customized by using the
   configuration parameter :ref:`needs_role_need_template`.


.. _role_need_outgoing:

need_outgoing
-------------
.. versionadded:: 0.1.25

``:need_outgoing:`` adds a list of all outgoing links of the given need.
The list contains the need IDs only, no title or any other information is printed.

Example
~~~~~~~

.. req:: Butter on Bread
   :id: roles_req_2
   :links: roles_req_1

.. code-block:: jinja

   To get butter on our bread, we need to fulfill :need_outgoing:`roles_req_2`

**Result**: To get butter on our bread, we need to fulfill :need_outgoing:`roles_req_2`


.. _role_need_incoming:

need_incoming
-------------
.. versionadded:: 0.1.25

``:need_incoming:`` prints a list IDs of needs, which have set outgoing links to the given need.

Example
~~~~~~~

.. code-block:: jinja

   The realisation of **Sliced Bread** is really important because the needs :need_incoming:`roles_req_1` are based on
   it.

**Result**: The realisation of **Sliced Bread** is really important because the
needs :need_incoming:`roles_req_1` are based on it.


need_inline / ni
----------------
.. versionadded:: 0.3.0

``:need_inline`` or as shortcut ``:ni:`` can be used inside needs to set a sub-id for a specific sentence/area.
This sub-ids can be linked and referenced in other need functions like links and co.

Example
~~~~~~~

.. code-block:: jinja

   .. req:: Car must be awesome
      :id: my_car_1
      :tags: car
      :status: open

      My new car must be the fastest on the world. Therefor it shall have:

      * :need_inline:`(1)A topspeed of 300 km/h`
      * :ni:`(2) An acceleration of 30 m/s or much much more`

      And we also need --> :ni:`(awesome_3) a turbo button`!


   .. spec:: Build awesome car
      :links: my_car_1.1, my_car_1.2

      No way to get :need:`my_car_1.awesome_3` realised.


   Reference to a need_internal from outside need scope: :need:`my_car_1.2`.

**Result**

.. req:: Car must be awesome
   :id: my_car_1
   :tags: car
   :status: open

   My new car must be the fastest on the world. Therefor it shall have:

   * :need_inline:`(1)A topspeed of 300 km/h`
   * :ni:`(2) An acceleration of 30 m/s or much much more`

   And we also need --> :ni:`(awesome_3) a turbo button`!


.. spec:: Build awesome car
   :links: my_car_1.1, my_car_1.2

   No way to get :need:`my_car_1.awesome_3` realised.


Reference to a need_internal from outside need scope: :need:`my_car_1.2`.