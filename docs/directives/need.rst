.. _need:

need/ req (or any other defined need type)
==========================================

Example::

    .. req:: User needs to login
       :id: ID123
       :status: open
       :tags: user;login
       :links: ID444; ID_555

       Our users needs to get logged in via our login forms on **/login.php**.

This creates a new requirement, with a title, content, given id, a status and several tags.

All options are optional, only the title as argument must be given.

However, if no **id** is given, a short hash value is calculated based on the title. If the title gets not changed, the
id will be stable for all upcoming documentation generations.

**Tags** must be separated by "**;**", like tag1; tag2;tag3. Whitespaces get removed.

**links** can be used to create a link to one or several other needs, no matter what kind of type they are.
All you need is the related ID.

There is an additional option **:hide:**, if this is set (no value is needed), the need will not be printed in
documentation. But it will show up in need filters!

You can also use **:hide_status:** and **:hide_tags:** to hide the related information for this need.

.. note::

    By default the above example works also with `.. spec::`, `.. impl::`, `.. test::` and all other need types,
    which are configured via :ref:`need_types`.