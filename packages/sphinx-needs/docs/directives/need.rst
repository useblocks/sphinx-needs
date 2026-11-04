.. _need:

need items
==========

Creates a **need** object with a specified type.
You can define the type using the correct directive, like ``.. req::`` or ``.. test::``.

.. syntax-example::

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

.. _need_diagram:

Diagram support
---------------
A need object can also define its own PlantUML representation.
Therefore Sphinx-Needs looks for the :ref:`needuml` directive inside the content
and stores its PlantUML code under given key from :ref:`needuml` directive under the option name ``arch``.

This diagram data can then be used in other :ref:`needuml` calls to combine and reuse PlantUML elements.

.. syntax-example::

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

.. syntax-example::

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

.. syntax-example::

   .. req:: Link example Target
      :id: REQ_LINK_1

      This is the target for a link. Itself has no link set.

   .. req:: Link example Source
      :links: REQ_LINK_1

      This sets a link to id ``REQ_LINK_1``.

.. _need_conditional_links:

conditional links
+++++++++++++++++

.. versionadded:: 8.0.0

In requirements management, traceability is not just about *whether* two needs are linked,
but whether the link is **valid in context**.
For example, a specification should only link to requirements that are ``"open"`` or ``"approved"``,
or a test should only reference an implementation at a compatible version.

You can attach a condition to any link by appending a :ref:`filter_string` in square brackets after the target ID.
The condition is evaluated against the **targeted** need.
If the condition evaluates to ``False``, a warning is emitted with the subcode ``needs.link_condition_failed``.
If the condition syntax is invalid, a warning is emitted with the subcode ``needs.link_condition_invalid``.

The syntax is ``TARGET_ID[condition]``, for example:

.. code-block:: rst

   .. spec:: My Specification
      :links: REQ_001[status=="open"]

This creates a link from the specification to ``REQ_001``, but emits a warning if ``REQ_001`` does not have ``status`` equal to ``"open"``.

You can use any valid :ref:`filter_string` expression as the condition.
The condition is evaluated with the fields of the **target** need as variables,
so you can check any of its attributes (``status``, ``type``, ``tags``, etc.).

Multiple links can be specified, each with their own condition:

.. code-block:: rst

   .. spec:: Another Specification
      :links: REQ_001[status=="open"], REQ_002[type=="req"]

Links without conditions continue to work as before:

.. code-block:: rst

   .. spec:: Mixed links
      :links: REQ_001[status=="open"], REQ_002

.. note::

   Any number of opening ``[`` brackets can be used to start the condition,
   as long as the same number of closing ``]`` brackets are used to end it.
   This is useful when the condition itself contains square brackets (e.g. for list indexing):
   ``REQ_001[[tags[0]=="important"]]``.

.. note::

   Conditional link syntax is also supported in link strings within ``needs.json`` files
   loaded via :ref:`needimport` or :ref:`needs_external_needs`.
   For example, a need in a JSON file can have
   ``"links": ["REQ_001[status==\"open\"]"]``
   and the condition will be evaluated during the build just as it would for a directive-defined link.

.. seealso::

   :ref:`needs_json_include_link_conditions` — controls whether conditions are included in ``needs.json`` output.

extra links
+++++++++++

By using :ref:`needs_links <needs_links>`, you can use the configured link-types to set additional **need** options.

.. code-block:: python

   # conf.py
   needs_links = {
      "blocks": {
         "incoming": "is blocked by",
         "outgoing": "blocks"
      },
      "tests": {
         "incoming": "is tested by",
         "outgoing": "tests",
         "copy": False,
         "color": "#00AA00"
      }
   }

.. syntax-example::

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

.. syntax-example::

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

.. syntax-example::

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

.. deprecated:: 9.3.0

   ``:jinja_content:`` reports a ``needs.deprecated`` warning at each need it renders, and is removed in
   sphinx-needs 10.0. Move the Jinja into a template file, with ``{{ content }}`` where the need's own body
   goes, and name it with :ref:`need_template` (or give it to every need of a type as a default). A template
   keeps the need's authored body and leaves no Jinja syntax in ``needs.json``.

The option activates jinja-parsing for the content of a need.
If the value is set to ``true``, you can specify `Jinja <https://jinja.palletsprojects.com/>`_ syntax in the content.

The **:jinja_content:** option give access to all need data, including the original content
and the data in :ref:`needs_variant_data`.

If you set the option to **False**, you deactivate jinja-parsing for the need's content.

Allowed values (case-insensitive):

:True: empty, ``true`` or ``yes``
:False: ``false`` or ``no``

Default: False

.. code-block:: rst

    .. spec:: First Spec Need
       :id: JINJAID126
       :status: open
       :jinja_content:

       Need with ``:jinja_content:`` equal to ``true``.
       This requirement has status: **{{ status }}**.

renders the content ``Need with :jinja_content: equal to true. This requirement has status: open.``
The same need through a template, ``needs_templates/status.need``:

.. code-block:: jinja

    {{ content }}
    This requirement has status: **{{ status }}**.

.. code-block:: rst

    .. spec:: First Spec Need
       :id: JINJAID126
       :status: open
       :template: status

       Need with a template.

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

.. syntax-example::

    .. req::
       :title_from_content:

       The first sentence will be the title.  
       Anything after the first sentence will not be part of the title.

.. _need_layout:

layout
~~~~~~

.. versionadded:: 0.4.1

``layout`` can be used to set a specific grid and content mapping.

.. syntax-example::

   .. req:: My layout requirement 1
      :id: LAYOUT_1
      :tags: layout_example
      :layout: clean

      Some **content** of LAYOUT_1

.. syntax-example::

   .. req:: My layout requirement 2
      :id: LAYOUT_2
      :tags: layout_example
      :layout: complete

      Some **content** of LAYOUT_2

.. syntax-example::

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

.. syntax-example::

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

.. syntax-example::

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

.. syntax-example::

   .. spec:: My specification
      :status: open
      :links: STYLE_001, STYLE_002
      :id: TEMPL_SPEC
      :tags: example, template
      :template: spec_template

      This is my **specification** content.

You can find a list of need-value names in the documentation for :ref:`filter_string` or by using
the ``debug`` :ref:`layout <layouts>`.

You can automatically assign templates to specific needs by using :ref:`needs_fields`.

.. _need_pre_template:

pre_template
~~~~~~~~~~~~

.. versionadded:: 0.5.4

Adds specific content from a template *before* a **need**.
For example, you can use it to set a section name before each **need**: a heading in the output opens a section
where the output is, on a reStructuredText page and on a MyST page alike.

.. dropdown:: *Template:* ``spec_pre_template.need``

   .. literalinclude:: /needs_templates/spec_pre_template.need

.. syntax-example::

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

.. syntax-example::

   .. spec:: My specification
      :id: TEMPL_POST_SPEC
      :tags: example, template
      :links: STYLE_001, STYLE_002
      :post_template: spec_post_template

      This is my **specification** content.

.. _need_templates_portability:

How need templates are rendered
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionchanged:: 9.3.0

   A template that cannot be rendered keeps its need; undefined names and unresolved fields are reported;
   template files are dependencies of their documents; a hidden need's pre and post templates are not
   rendered; a heading in pre/post output on a MyST page opens its section in place; ``needimport`` no longer
   applies a record's template names.

:ref:`need_template`, :ref:`need_pre_template`, :ref:`need_post_template` and the deprecated
:ref:`jinja_content` share these rules, whether a template is named on the need, on a :ref:`needimport`, by a
need type's or :ref:`needs_fields`' ``default`` or ``predicates``, or through the API.

**When.** A need's templates are rendered once, when the need is created -- while its document is read. A
template sees the need as it is then: its ``id`` (a generated one included, which is computed from the
authored body before the render), its ``title``, its ``type``, ``type_name`` and the type's other metadata,
where it is (``docname``, ``lineno``, ``doctype``), its authored ``content``, the defaults it was given, and
every field its need type declares (its empty value while unset: ``None``, or ``[]`` for a link type), with
:ref:`needs_render_context` merged over them.
It does not see what is resolved only once every document is read: back links (``links_back`` is empty),
``sections`` and ``section_name``, the value a :ref:`needextend` sets (the template shows the value before
it), and the value of a field holding a :ref:`dynamic function <dynamic_functions>`, a variant or a
:ref:`derived value <needs_derive>`, which renders as its unset value (``None``, or ``[]`` for a link type).
A template naming such a field is reported (``needs.template_unresolved``, naming the field). To show resolved data, write constructs that are resolved
later into the output: a ``:need:`` role, :ref:`needtable` or :ref:`needflow` filters (``'{{id}}' in
links_back``), an ``:ndf:`` dynamic function -- or use a :ref:`layout <layouts>`.

**Undefined names** render empty, and are reported: a template is rendered strictly first and, when it uses
an undefined value, leniently again, with one ``needs.template_undefined`` warning naming the template and the
expression. An undefined value is an undefined name (a typo, a field another need type declares), a missing key
or attribute (``{{ mapping.missing }}``, an attribute of an unset field, which is ``None``), or an item of an
empty list (``{{ links|first }}``, ``{{ tags[0] }}`` where there is none), used anywhere but in an
``is defined`` test or the ``default`` filter: testing one for truth (``{% if typo %}``) is a use. Every
declared field is defined; test a value only some needs have with ``{% if x is defined %}`` or give it a
``default``, which report nothing. A few uses of an undefined name are not reported, as the engine lets them
pass: an ``is none`` or ``is string`` test of it, and ``|join`` over it. The output is the same as without the
warning. A call of a function given directly in :ref:`needs_render_context` that returned a plain value
(a string, a number, a boolean, ``None``) is replayed in the second render, so it is made once, as with a single
render; any other call runs again -- one returning a list, a mapping, a generator or another object, and every
call of a class, a callable object, or a method or function reached through a value of the render context. One
of those with side effects may change the output. An attribute of an undefined NAME
(``{{ typo.attr }}``) is an error even then: the whole template's output is empty, as ``needs.template_render``
reports.

**Values** display as Python prints them: ``None``, ``True``, ``3``, ``1.0``. How a list or a map displays
is not guaranteed; join a list (``{{ tags | join(", ") }}``).

**Markup.** The output is written in the markup of the page the need is on: MyST on a MyST page,
reStructuredText on a reStructuredText page (and for a need written in reStructuredText on a MyST page:
inside ``{eval-rst}``, or in the reStructuredText output of a sphinx-ub-directives template). The need's
``doctype`` says which.
Content output is the need's content; pre and post output are placed before and after the need, and a heading
in them opens a section there.

**A hidden need** (:ref:`need_hide`) shows no template output: its pre and post templates are not rendered at
all, while its content template is, for ``needs.json``.

**A template that cannot be rendered** -- a file the template folder does not hold, a syntax error, an error
while rendering -- never costs the need: it is created with that template's output empty, and one warning is
reported at it (``needs.template_missing``, ``needs.template_syntax`` or ``needs.template_render``).

**Incremental builds.** Each template file a need reads, or tries to read, is a dependency of its document:
editing, creating or deleting it re-reads the document. Until a missing template exists, its document is re-read
on every build, as Sphinx re-reads a document with any missing dependency (it is reported each time, as
``needs.template_missing``). A record's pre or post template a :ref:`needimport` looks for and does not find is
not a dependency: the import page is re-read once the template is created, or when the template folder or the
render context changes, and not on every build before.
Changing :ref:`needs_template_folder`, or a value of :ref:`needs_render_context` that can be compared between
builds, re-reads every document with a templated need. A value is compared when it survives a pickle unchanged
-- data, and a function defined at the top of a module, which changing re-reads too; a ``lambda``, a closure or
an object without equality is not compared, and changing it re-reads nothing. A value that differs on each build
(a time stamp) re-reads the templated documents on each build.

**needs.json** holds what the templates rendered: ``content`` is the rendered body, ``pre_content`` and
``post_content`` the rendered decorations, and ``template``, ``pre_template``, ``post_template`` and
``jinja_content`` name what produced them, as provenance. A reader of the file -- :ref:`needimport`,
:ref:`needs_external_needs`, ubCode -- never applies its ``template`` or ``jinja_content`` again: ``content``
with ``doctype`` is a complete, final description of the need's body, which ``needimport`` parses in its
``doctype`` with :ref:`needs_import_parse_by_doctype` (:ref:`needimport_parse_by_doctype`). ``needimport``
still applies a record's ``pre_template`` / ``post_template`` where the importing project has the template,
deprecated, until 10.0. See :ref:`needimport_templates`.

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

You can read :ref:`needs_fields` for detailed information and examples.
