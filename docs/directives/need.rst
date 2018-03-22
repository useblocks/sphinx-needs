.. _need:

need/ req (or any other defined need type)
==========================================

Creates a need with specified type. The type is defined by using the correct directive, like
``.. req::`` or ``.. test::``.


.. code-block:: rst

    .. req:: User needs to login
       :id: ID123
       :status: open
       :tags: user;login
       :collapse: false

       Our users needs to get logged in via our login forms on **/login.php**.

.. req:: User needs to login
   :id: ID123
   :status: open
   :tags: user;login
   :collapse: false

   Our users needs to get logged in via our login forms on **/login.php**.

This creates a new requirement, with a title, content, given id, a status and several tags.

All options are optional, only the title as argument must be given.

.. note::

    By default the above example works also with `.. spec::`, `.. impl::`, `.. test::` and all other need types,
    which are configured via :ref:`need_types`.

Options
-------

Supported options:

* :ref:`need_id`
* :ref:`need_status`
* :ref:`need_tags`
* :ref:`need_links`
* :ref:`need_hide`
* :ref:`need_hide_status`
* :ref:`need_hide_tags`
* :ref:`need_collapse`

.. _need_id:

id
~~
The given ID must match the regular expression of config parameter :ref:`needs_id_regex`.
If it does not match, the build stops.

If no **id** is given, a short hash value is calculated based on the title. If the title gets not changed, the
id will be stable for all upcoming documentation generations.

.. _need_status:

status
~~~~~~
A need can only have one status and its selection may be restricted by config parameter :ref:`needs_statuses`.


.. _need_tags:

tags
~~~~
**Tags** must be separated by "**;**", like tag1; tag2;tag3. Whitespaces get removed.

.. _need_links:

links
~~~~~
**links** can be used to create a link to one or several other needs, no matter what kind of type they are.
All you need is the related ID.

You can easily set links to multiple needs by using ";" as separator.

.. container:: toggle

   .. container:: header

      **Show example**

   .. code-block:: rst

      .. req:: Link example
         :links: req_001; OWN_ID_123; IMPL_01

         We have linked this requirement to multiple other needs.

   .. req:: Link example
         :links: req_001; OWN_ID_123; IMPL_01
         :collapse: false

         We have linked this requirement to multiple other needs.



.. _need_hide:

hide
~~~~
There is an option **:hide:**, if this is set (no value is needed), the need will not be printed in
documentation. But it will show up in need filters!

.. _need_hide_status:

hide_status
~~~~~~~~~~~
You can also use **:hide_status:**  to hide status information for a need.

.. _need_hide_tags:

hide_tags
~~~~~~~~~
Or use **:hide_tags:** to hide the tags of a need.

.. _need_collapse:

collapse
~~~~~~~~
If set to **True**, details like status, links or tags are collapsed and viewable only after a click on the need title.

If set to **False**, details are shown directly.

If not set, the config parameter :ref:`needs_collapse_details` decides about the behavior.

Allowed values:

 * true; yes; 1
 * false; no; 0


.. container:: toggle

   .. container:: header

      **Show example**

   .. code-block:: rst

      .. req:: Collapse is set to True
         :tags: collapse; example
         :collapse: True

         Only title and content are shown

      .. req:: Collapse is set to False
         :tags: collapse; example
         :collapse: False

         Title, tags, links and everything else is shown directly.

   .. req:: Collapse is set to True
      :tags: collapse; example
      :collapse: True

      Only title and content are shown

   .. req:: Collapse is set to False
      :tags: collapse; example
      :collapse: False

      Title, tags, links and everything else is shown directly.

