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

All options are optional, only the title as argument must be given (if :ref:`needs_title_from_content` is not set).

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
* :ref:`need_style`

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

      .. req:: Link example Target
         :id: REQ_LINK_1

         This is the target for a link. Itself has no link set.

      .. req:: Link example Source
         :links: REQ_LINK_1

         This sets a link to id ``REQ_LINK_1``.

   .. req:: Link example
         :links: OWN_ID_123; IMPL_01
         :collapse: false

         We have linked this requirement to multiple other needs.



.. _need_extra_links:

extra links
+++++++++++

By using :ref:`needs_extra_links` you can use the configured link-types to set additional on other options.

.. container:: toggle

   .. container:: header

      **Show example**

   .. code-block:: python

      # conf.py
      needs_extra_links = [
         {
            "name": "blocks",
            "incoming": "is blocked by",
         },
         {
            "name": "tests",
            "incoming": "is tested by",
            "copy": False,
            "color": "#00AA00"
         }
      ]

   .. code-block:: rst

      .. req:: test me
         :id: test_req

         A requirement, which needs to be tested

      .. test:: test a requirement
         :id: test_001
         :tests: test_req

         Perform some tests


   .. req:: test me
      :id: test_req
      :collapse: false

      A requirement, which needs to be tested

   .. test:: test a requirement
      :id: test_001
      :tests: test_req
      :collapse: false

      Perform some tests


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


.. _title_from_content:

title_from_content
~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.3

When this flag is provided on an individual need, a title will be derived
from the first sentence of the content.  If not title and no content is provided
then the build process will fail.

The derived title will respect the :ref:`needs_max_title_length` and provide an
ellided title if needed.  By default there is no limit to the title length.

When using this setting be sure to exercise caution that special formatting
that you would not want in the title (bulleted lists, nested directives, etc.)
do not appear in the first sentence.

If a title is provided and the flag is present, then the provided title will
be used and a warning will be issued.

Example::

    .. req::
        :title_from_content:

        The first sentence will be the title.  Anything after the first
        sentence will not be part of the title.

The resulting requirement would have the title derived from the first
sentence of the requirement.

.. req::
    :title_from_content:

    The first sentence will be the title.  Anything after the first
    sentence will not be part of the title.

.. _need_layout::

layout
~~~~~~

TBD

.. _need_style:

style
~~~~~

.. versionadded:: 0.4.1

``style`` can be used to set a specific class-attribute for the need representation.

The class-attribute can then be addressed by css to specific the layout of the need.

.. req:: My styled requirement
   :id: STYLE_001
   :tags: style_example
   :style: red

.. req:: Another styled requirement
   :id: STYLE_002
   :tags: style_example
   :style: blue

.. req:: Green is my color
   :id: STYLE_003
   :tags: style_example
   :style: green

.. req:: Yellow and blue border
   :id: STYLE_004
   :style: yellow, blue_border

.. container:: toggle

   .. container:: header

      **Show code**

   .. code-block:: rst

      .. req:: My styled requirement
         :id: STYLE_001
         :tags: style_example
         :style: red

      .. req:: Another styled requirement
         :id: STYLE_002
         :tags: style_example
         :style: blue

      .. req:: Green is my color
         :id: STYLE_003
         :tags: style_example
         :style: green

      .. req:: Yellow and blue border
         :id: STYLE_004
         :style: yellow, blue_border

By using :ref:`dynamic_functions` the value of ``style`` can be automatically
combined with values from other need options.

Here ``style`` is set to ``needs_[[copy('status')]]``.

.. req:: My automatically styled requirement
   :id: STYLE_005
   :status: implemented
   :tags: style_example
   :style: [[copy("status")]]

.. req:: My automatically styled requirement
   :id: STYLE_006
   :status: open
   :tags: style_example
   :style: [[copy("status")]]

.. code-block:: rst

   .. req:: My automatically styled requirement
      :id: STYLE_005
      :status: implemented
      :tags: style_example
      :style: [[copy(status)]]

   .. req:: My automatically styled requirement
      :id: STYLE_006
      :status: open
      :tags: style_example
      :style: [[copy(status)]]

Customized Options
------------------

Sphinx-Needs supports the definition and filtering of customized options for needs.

Please see :ref:`needs_extra_options` for detailed information and examples.
