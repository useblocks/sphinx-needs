.. _roles:

Roles
=====

You can use Roles to get short information of needs inside single sentences.

.. _role_need:
.. _needref:

need
----

The role ``:need:`` will add title, id and a link to the need.

We use it to reference an existing need, without the need to keep title and link location manually in sync.

With ``[[`` and ``]]`` you can refer to defined and set :ref:`extra options <needs_extra_options>`. 

.. need-example::

   .. req:: Sliced Bread
      :id: roles_req_1
      :status: open
      :value: 20
      :unit: slices

   | The requirement :need:`roles_req_1` is the most important one.
   | But we can also set :need:`a custom link name <roles_req_1>`.
   | And we can change the text even more e.g. :need:`[[value]] [[unit]] of [[title]] ([[id]] [[status]]) <roles_req_1>`.

.. note::

   You can customize the string representation by using the
   configuration parameters :ref:`needs_role_need_template` and
   :ref:`needs_role_need_max_title_length`.
   If we find a ``[[`` in the customized string, we handle it 
   according to Python's ``{`` `.format() <https://docs.python.org/3.4/library/functions.html#format>`_ 
   function.
   Please see https://pyformat.info/ for more information.
   RST-attributes like ``**bold**`` are **not** supported.

.. warning::

   If you refer to an :ref:`external need <needs_external_needs>`, the algorithm is different
   and you will only get the need id as link text.


.. _role_need_outgoing:

need_outgoing
-------------
.. versionadded:: 0.1.25

``:need_outgoing:`` adds a list of all outgoing links of the given need.
The list contains the need IDs only, no title or any other information is printed.

.. need-example::

   .. req:: Butter on Bread
      :id: roles_req_2
      :links: roles_req_1

   To get butter on our bread, we need to fulfill :need_outgoing:`roles_req_2`

.. _role_need_incoming:

need_incoming
-------------
.. versionadded:: 0.1.25

``:need_incoming:`` prints a list of IDs of needs which have set outgoing links to the given need.

.. need-example::

   The realisation of **Sliced Bread** is really important because the needs :need_incoming:`roles_req_1` are based on
   it.

.. _need_part:

need_part / np
----------------
.. versionadded:: 0.3.0

You can use ``:need_part:`` or as shortcut ``:np:`` inside needs to set a sub-id for a specific sentence/part.
This sub-ids can be linked and referenced in other need functions like links and co.

The used need_part id can be freely chosen, but should not contain any whitespaces or dots.

.. need-example::

   .. req:: Car must be awesome
      :id: my_car_1
      :tags: car
      :status: open

      My new car must be the fastest on the world. Therefor it shall have:

      * :need_part:`(1)A top speed of 300 km/h`
      * :np:`(2) An acceleration of 200 m/s² or much much more`

      And we also need --> :np:`(awesome_3) a turbo button`!


   .. spec:: Build awesome car
      :id: impl_my_car_1
      :links: my_car_1.1, my_car_1.2

      Requirements :need:`my_car_1.1` and :need:`my_car_1.2` are no problem and can
      be realised by doing rocket science.

      But no way to get :need:`my_car_1.awesome_3` realised.


   Reference to a part of a need from outside need scope: :need:`my_car_1.2`.

**Presentation in needflow**

Links to need_parts are shown as dotted line to the upper need inside :ref:`needflow` diagrams.
They are also getting the part_id as link description.

.. need-example::

   .. needflow::
      :filter: id in ["my_car_1","impl_my_car_1"]

**Presentation in needtable**

Please see :ref:`needtable_show_parts` of :ref:`needtable` configuration documentation.

.. need-example::

   .. needtable::
      :style: table
      :filter: 'car' in tags and is_need
      :show_parts:
      :columns: id, title, incoming, outgoing

.. _need_count:

need_count
----------
.. versionadded:: 0.3.1

Counts found needs for a given filter and shows the final amount.

The content of the role must be a valid filter-string as used e.g. by :ref:`needlist` in the ``:filter:`` option.
See :ref:`filter_string` for more information.

.. need-example::

   | All needs: :need_count:`True`
   | Specification needs: :need_count:`type=='spec'`
   | Open specification needs: :need_count:`type=='spec' and status=='open'`
   | Needs with tag *test*: :need_count:`'test' in tags`
   | Needs with title longer 10 chars: :need_count:`search(r"[\w\s]{10,}", title)`
   | All need_parts: :need_count:`is_part`
   | All needs containing need_parts: :need_count:`is_need and len(parts)>0`

.. note::

   If backslashes ``\`` are used inside the regex function ``search``, please make sure to double them as in python
   one ``\`` needs to be represented by ``\\``.

.. note::

   ``need_count`` executes the given filter on needs and need_parts!
   So if you use :ref:`need_part` , the result may contain the amount of found needs *and* found need_parts.
   To avoid this, add ``is_need`` or ``is_part`` to your filter.


.. _need_count_ratio:

Ratio
~~~~~

.. versionadded:: 0.5.3

To calculate the ratio of one filter to another filter, you can define two filters separated by ``_?_``
(question mark surrounded by one space on each side).

.. need-example::

   :need_count:`status == open and type == "spec" ? type == "spec"` % of our specifications are open.


.. _need_func:

need_func
---------
.. deprecated:: 3.1.0

   Use :ref:`ndf` instead.

.. _ndf:

ndf
---
.. versionadded:: 3.1.0

Executes a :ref:`need dynamic function <dynamic_functions>` and uses the return values as content.

.. need-example::

    A nice :ndf:`echo("first test")` for dynamic functions.
