.. _need:

need items
==========

Creates a **need** object with a specified type.
You can define the type using the correct directive, like ``.. req::`` or ``.. test::``.

.. need-example::

    .. req:: User needs to login
       :id: ID123
       :status: open
       :tags: user;login
       :collapse: false

       Our users needs to get logged in via our login forms on **/login.php**.

The code example above creates a new requirement, with a title, content, given id, a status and several tags.

All the options for the requirement directive ( ``req`` ) are optional,
but you must set a title as an argument (i.e. if you do not specify :ref:`needs_title_from_content` in the conf.py file).

.. note::

    By default, the above example works also with ``.. spec::``, ``.. impl::``, ``.. test::`` and all other need types,
    which are configured via :ref:`needs_types`.

.. _needs_variant_support:

Variants for options support
----------------------------
.. versionadded:: 1.0.2

Needs variants add support for variants handling on need options. |br|
The support for variants options introduce new ideologies on how to set values for *need options*.

To implement variants options, you can set a *need option* to a variant definition or multiple variant definitions.
A variant definition can look like ``var_a:open`` or ``['name' in tags]:assigned``.

A variant definition has two parts: the **rule or key** and the **value**. |br|
For example, if we specify a variant definition as ``var_a:open``, then ``var_a`` is the key and ``open`` is the value.
On the other hand, if we specify a variant definition as ``['name' in tags]:assigned``, then ``['name' in tags]`` is the rule
and ``assigned`` is the value.

Rules for specifying variant definitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Variants must be wrapped in ``<<`` and ``>>`` symbols, like ``<<var_a:open>>``.
* Variants gets checked from left to right.
* When evaluating a variant definition, we use data from the current need object,
  `Sphinx-Tags <https://www.sphinx-doc.org/en/master/man/sphinx-build.html#cmdoption-sphinx-build-t>`_,
  and :ref:`needs_filter_data` as the context for filtering.
* You can set a *need option* to multiple variant definitions by separating each definition with either
  the ``,`` symbol, like ``var_a:open, ['name' in tags]:assigned``. |br|
  With multiple variant definitions, we set the first matching variant as the *need option's* value.
* When you set a *need option* to multiple variant definitions, you can specify the last definition as
  a default "variant-free" option which we can use if no variant definition matches. |br|
  Example; In this multi-variant definitions, ``[status in tags]:added, var_a:changed, unknown``, *unknown* will be used
  if none of the other variant definitions are True.
* If you prefer your variant definitions to use rules instead of keys, then you should put your filter string
  inside square brackets like this: ``['name' in tags]:assigned``.
* For multi-variant definitions, you can mix both rule and variant-named options like this:
  ``[author["test"][0:4] == 'me']:Me, var_a:Variant A, Unknown``

To implement variants options, you must configure the following in your ``conf.py`` file:

* :ref:`needs_variants`
* :ref:`needs_variant_options`

There are various use cases for variants options support.

Use Case 1
~~~~~~~~~~

In this example, you set the :ref:`needs_variants` configuration that comprises pre-defined variants assigned to
"filter strings".
You can then use the keys in your ``needs_variants`` as references when defining variants for a *need option*.

For example, in your ``conf.py``:

.. code-block:: python

   needs_variants = {
     "var_a": "'var_a' in sphinx_tags"  # filter_string
     "var_b": "assignee == 'me'"
   }

In your ``.rst`` file:

.. code-block:: rst

   .. req:: Example
      :id: VA_001
      :status: <<var_a:open, var_b:closed, unknown>>

From the above example, if a *need option* has variants defined, then we get the filter string
from our ``needs_variants`` configuration and evaluate it.
If a variant definition is true, then we set the *need option* to the value of the variant definition.

Use Case 2
~~~~~~~~~~

In this example, you can use the filter string directly in the *need option's* variant definition.

For example, in your ``.rst`` file:

.. code-block:: rst

   .. req:: Example
      :id: VA_002
      :status: <<['var_a' in tags]:open, [assignee == 'me']:closed, unknown>>

From the above example, we evaluate the filter string in our variant definition without referring to :ref:`needs_variants`.
If a variant definition is true, then we set the *need option* to the value of the variant definition.

Use Case 3
~~~~~~~~~~

In this example, you can use defined tags (via the `-t <https://www.sphinx-doc.org/en/master/man/sphinx-build.html#cmdoption-sphinx-build-t>`_
command-line option or within conf.py, see `here <https://www.sphinx-doc.org/en/master/usage/configuration.html#conf-tags>`_)
in the *need option's* variant definition.

First of all, define your Sphinx-Tags using either the ``-t`` command-line ``sphinx-build`` option:

.. code-block:: bash

   sphinx-build -b html -t tag_a . _build

or using the special object named ``tags`` which is available in your Sphinx config file (``conf.py`` file):

.. code-block:: python

   tags.add("tag_b")   # Add "tag_b" which is set to True

In your ``.rst`` file:

.. code-block:: rst

   .. req:: Example
      :id: VA_003
      :status: <<[tag_a and tag_b]:open, closed>>

From the above example, if a tag is defined, the plugin can access it in the filter context when handling variants.
If a variant definition is true, then we set the *need option* to the value of the variant definition.

.. note:: Undefined tags are false and defined tags are true.

Below is an implementation of variants for need options:

.. need-example::

   .. req:: Variant options
      :id: VA_004
      :status: <<['variants' in tags and not collapse]:enabled, disabled>>
      :tags: variants;support
      :collapse:

      Variants for need options in action

.. _need_diagram:

Diagram support
---------------
A need objects can also define it's own PlantUML representation.
Therefore Sphinx-Needs looks for the :ref:`needuml` directive inside the content
and stores its PlantUML code under given key from :ref:`needuml` directive under the option name ``arch``.

This diagram data can then be used in other :ref:`needuml` calls to combine and reuse PlantUML elements.

.. need-example::

   .. spec:: Interfaces
      :id: SP_INT
      :status: open

      This are the provided interfaces:

      .. needuml::

         circle "Int A" as int_a
         circle "Int B" as int_b
         circle "Int C" as int_c

   Reuse of :need:`SP_INT` inside a :ref:`needuml`:

   .. needuml::

      allowmixing

      {{uml("SP_INT")}}
      node "My System" as system

      system => int_a


This simple mechanism is really powerful to design reusable and configurable SW architecture diagrams.
For more examples and details, please read :ref:`needuml`.

Filter for diagrams
~~~~~~~~~~~~~~~~~~~
The option ``arch`` can be easily used for filtering. For instance to show all need objects, which
are representing some kind of a diagram.

.. need-example::

   .. needtable::
      :filter: bool(arch)
      :style: table
      :columns: id, type, title


Options for Need Type
---------------------

.. _need_id:

id
~~
The given ID must match the regular expression (regex) value for the :ref:`needs_id_regex` parameter in **conf.py**.
The Sphinx build stops if the ID does not match the regex value.

If you do not specify the id option, we calculate a short hash value based on the title. The calculated value can 
also include title if :ref:`needs_id_from_title` is set to **True**.
If you don’t change the title, the id will work for all upcoming documentation generations.

.. _need_status:

status
~~~~~~
A need can only have one status, and the :ref:`needs_statuses` configuration parameter may restrict its selection.


.. _need_tags:

tags
~~~~
You can give multiple tags by separating each with **;** symbol, like ``tag1;tag2;tag3``. White spaces get removed.

.. _need_links:

links
~~~~~
The ``links`` option can create a link to one or several other needs, no matter the need type.
All you must specify is the ID for the need.

You can easily set links to multiple needs by using **;** as a separator.

.. need-example::

   .. req:: Link example Target
      :id: REQ_LINK_1

      This is the target for a link. Itself has no link set.

   .. req:: Link example Source
      :links: REQ_LINK_1

      This sets a link to id ``REQ_LINK_1``.

.. _need_extra_links:

extra links
+++++++++++

By using :ref:`needs_extra_links <needs_extra_links>`, you can use the configured link-types to set additional **need** options.

.. code-block:: python

   # conf.py
   needs_extra_links = [
      {
         "option": "blocks",
         "incoming": "is blocked by",
         "outgoing": "blocks"
      },
      {
         "option": "tests",
         "incoming": "is tested by",
         "outgoing": "tests",
         "copy": False,
         "color": "#00AA00"
      }
   ]

.. need-example::

   .. req:: test me
      :id: test_req

      A requirement, which needs to be tested

   .. test:: test a requirement
      :id: test_001
      :tests: test_req

      Perform some tests

.. _need_delete:

delete
~~~~~~

There is a **:delete:** option. If the value of the option is set to **True**, the need will be deleted completely
from any NeedLists or NeedDicts including the ``needs.json`` file.

This option allows a user to have multiple need-objects with the same id, but only one is shown in the documentation.

Allowed values (case-insensitive):

:True: empty, ``true`` or ``yes``
:False: ``false`` or ``no``

Default: False

.. note::

   If you delete a need using the :delete: option, the need will not be part of any filter result.

.. need-example::

   .. req:: First Requirement Need
      :id: DELID123
      :status: open
      :delete: true

      Need with ``:delete:`` equal to ``true``.

   .. req:: Second Requirement Need
      :id: DELID123
      :delete: false

      Need with ``:delete:`` equal to ``false``.

      .. spec:: Nested Need without delete option
         :id: DELID124
         :tags: nested-del-need

         Need with ``:delete:`` option not set.


.. _need_hide:

hide
~~~~
There is a **:hide:** option. If this is set to **True**, the need will not be printed in the documentation.
But you can use it with **need filters**.

Allowed values (case-insensitive):

:True: empty, ``true`` or ``yes``
:False: ``false`` or ``no``

Default: False

.. _need_collapse:

collapse
~~~~~~~~
If set to **True**, the details section containing status, links or tags is not visible.
You can view the details by clicking on the forward arrow symbol near the need title.

If set to **False**, the need shows the details section.

Allowed values (case-insensitive):

:True: empty, ``true`` or ``yes``
:False: ``false`` or ``no``

Default: False

.. need-example::

   .. req:: Collapse is set to True
      :tags: collapse; example
      :collapse:

      Only title and content are shown

   .. req:: Collapse is set to False
      :tags: collapse; example
      :collapse: False

      Title, tags, links and everything else is shown directly.

.. _jinja_content:

jinja_content
~~~~~~~~~~~~~

The option activates jinja-parsing for the content of a need.
If the value is set to ``true``, you can specify `Jinja <https://jinja.palletsprojects.com/>`_ syntax in the content.

The **:jinja_content:** option give access to all need data, including the original content
and the data in :ref:`needs_filter_data`.

If you set the option to **False**, you deactivate jinja-parsing for the need's content.

Allowed values (case-insensitive):

:True: empty, ``true`` or ``yes``
:False: ``false`` or ``no``

Default: False

.. note::

   You can set the **:jinja_content:** option using the :ref:`needs_global_options` configuration variable.
   This will enable jinja-parsing for all the need objects in your documentation project.

   .. code-block:: python

      needs_global_options = {
        'jinja_content': 'true'
      }


.. need-example::

    .. req:: First Req Need
       :id: JINJAID123
       :jinja_content: false

       Need with ``:jinja_content:`` equal to ``false``.

       .. spec:: Nested Spec Need
          :id: JINJAID125
          :status: open
          :tags: user;login
          :links: JINJAID126
          :jinja_content:

          Nested need with ``:jinja_content:`` option set to ``true``.
          This requirement has tags: **{{ tags | join(', ') }}**.

          It links to:
          {% for link in links %}
          - {{ link }}
          {% endfor %}


    .. spec:: First Spec Need
       :id: JINJAID126
       :status: open
       :jinja_content:

       Need with ``:jinja_content:`` equal to ``true``.
       This requirement has status: **{{ status }}**.

.. _title_from_content:

title_from_content
~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.3

When this flag is provided on a need, a title will be derived
from the first sentence of the content.  If the title or content is not provided
then the build process will fail.

The derived title will respect the :ref:`needs_max_title_length` and provide an
elided title if needed.  By default there is no limit to the title length.

.. note::

    When using this setting ensure that the first sentence does not contain
    any special formatting you would not want in the title (bulleted lists, nested directives, etc.)

If a title is provided and the flag is present, then the provided title will
be used and a warning will be issued.

.. need-example::

    .. req::
       :title_from_content:

       The first sentence will be the title.  
       Anything after the first sentence will not be part of the title.

.. _need_layout:

layout
~~~~~~

.. versionadded:: 0.4.1

``layout`` can be used to set a specific grid and content mapping.

.. need-example::

   .. req:: My layout requirement 1
      :id: LAYOUT_1
      :tags: layout_example
      :layout: clean

      Some **content** of LAYOUT_1

.. need-example::

   .. req:: My layout requirement 2
      :id: LAYOUT_2
      :tags: layout_example
      :layout: complete

      Some **content** of LAYOUT_2

.. need-example::

   .. req:: My layout requirement 3
      :id: LAYOUT_3
      :tags: layout_example
      :layout: focus

      Some **content** of LAYOUT_3

Please take a look into :ref:`layouts` for more information.


.. _need_style:

style
~~~~~

.. versionadded:: 0.4.1

``style`` can be used to set a specific class-attribute for the need representation.

The class-attribute can then be selected with **CSS** to specify the layout of the need.

.. need-example::

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

By using :ref:`dynamic_functions`, the value of ``style`` can be automatically
derived from the values of other need options.

Here ``style`` is set to ``[[copy('status')]]``,
which leads to the CSS class ``needs_style_open`` if the ``status`` option is set to ``open``.

.. need-example::

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

.. _need_template:

template
~~~~~~~~

.. versionadded:: 0.5.2

By setting ``template``, the content of the need gets replaced by the content of the specified template.

**Sphinx-Needs** templates support the `Jinja <https://jinja.palletsprojects.com/>`_ templating language
and give access to all need data, including the original content.

The template name must be equal to the filename in the **Sphinx-Needs** template folder, without the file extension.
For example, if the filename is ``my_template.need``, you can reference it like this: ``:template: my_template``.
**Sphinx-Needs** templates must have the file extension ``.need``.

You can specify the location of all template files by configuring the :ref:`needs_template_folder`, which is by
default ``needs_templates/``, in the **conf.py** file.

You can have several templates, but can set only one for a need.

.. dropdown:: Template ``spec_template.need``

   .. literalinclude:: /needs_templates/spec_template.need

.. need-example::

   .. spec:: My specification
      :status: open
      :links: STYLE_001, STYLE_002
      :id: TEMPL_SPEC
      :tags: example, template
      :template: spec_template

      This is my **specification** content.

You can find a list of need-value names in the documentation for :ref:`filter_string` or by using
the ``debug`` :ref:`layout <layouts>`.

You can automatically assign templates to specific needs by using :ref:`needs_global_options`.

.. _need_pre_template:

pre_template
~~~~~~~~~~~~

.. versionadded:: 0.5.4

Adds specific content from a template *before* a **need**.
For example, you can use it to set a section name before each **need**.

.. dropdown:: *Template:* ``spec_pre_template.need``

   .. literalinclude:: /needs_templates/spec_pre_template.need

.. need-example::

   .. spec:: My specification
      :id: TEMPL_PRE_SPEC
      :tags: example, template
      :pre_template: spec_pre_template

      This is my **specification** content.

.. _need_post_template:

post_template
~~~~~~~~~~~~~

.. versionadded:: 0.5.4

Adds specific content from a template *after* a **need**.
You can use it to show some need-specific analytics, like dependency diagrams or table of linked needs.

.. dropdown:: *Template:* ``spec_post_template.need``

   .. literalinclude:: /needs_templates/spec_post_template.need

.. need-example::

   .. spec:: My specification
      :id: TEMPL_POST_SPEC
      :tags: example, template
      :links: STYLE_001, STYLE_002
      :post_template: spec_post_template

      This is my **specification** content.

.. _need_duration:

duration
~~~~~~~~

.. versionadded:: 0.5.5

Track the duration of a need.

The need allows any value but the :ref:`needgantt` directive uses and interprets it as days by default.


.. _need_completion:

completion
~~~~~~~~~~

.. versionadded:: 0.5.5

Track the completion of a need.

The need allows any value but the :ref:`needgantt` directive uses and interprets it as percentage by default.


Customized Options
------------------

Sphinx-Needs supports the definition and filtering of customized options for needs.

You can read :ref:`needs_extra_options` for detailed information and examples.
