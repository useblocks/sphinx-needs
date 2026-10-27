.. _filter:

Filtering needs
===============

The filtering of needs and need parts is supported consistently across numerous directives and roles,
either by using filter options or by using a filter string.

.. _filter_options:

Filter options
--------------

The following filter options are supported by directives:

* :ref:`needlist`
* :ref:`needtable`
* :ref:`needflow`
* :ref:`needpie`
* :ref:`needbar`
* :ref:`needextend`

On the two chart directives the options behave a little differently, because a
chart evaluates one filter per content line rather than one filter per
directive: there they select the needs each line is counted over, rather than
the needs that are shown.
See :ref:`needpie_scope` and :ref:`needbar_scope`.

Related to the used directive and its representation, the filter options create a list of needs, which match the
filters for status, tags, types and filter.

For **:status:**, **:tags:** and **:types:** values are separated by "**;**".
**:filter:** gets evaluated.

The logic, if a need belongs to the final result list, is as followed::

    status = (open OR in_progress) AND tags = (user OR login) AND types = (req OR spec) AND filter is true


.. _option_status:

status
~~~~~~
Use the **status** option to filter needs by their status.

You can easily filter for multiple statuses by separating them by ";". Example: *open; in progress; reopen*.

.. dropdown:: Show example

   .. syntax-example::

      .. needlist::
         :status: open
         :show_status:

.. _option_tags:

tags
~~~~

**tags** allows to filter needs by one or multiple tags.

To search for multiple tags, simply separate them by using ";".

.. dropdown:: Show example

   .. syntax-example::

      .. needlist::
         :tags: main_example
         :show_tags:

.. _option_types:

types
~~~~~
For **:types:** the type itself or the human-readable type-title can be used as filter value.

.. dropdown:: Show example

   .. syntax-example::

      .. needtable::
         :types: test

.. _option_sort_by:

sort_by
~~~~~~~
Sorts the result list. Allowed values are ``status`` or any alphanumerical property.

A need whose value is unset (``None``) comes first, whatever the field's type, as one with an empty string does.
The other values are grouped, so that values of different types are never compared: booleans, then numbers, then text.
Text is compared as it is (so ``"Z"`` comes before ``"a"``, unlike a :ref:`needtable`'s :ref:`sort <needtable_sort>`),
a list as its values joined with ``", "``, and any other value as its text.
Needs with equal values are ordered by id.

.. versionchanged:: 9.1.0

   An unset value used to be compared as an empty string, which stopped the build beside a number;
   a list was compared item by item, and equal values kept the needs' own order.

.. dropdown:: Show example

   .. syntax-example::

      .. needtable::
         :sort_by: id
         :status: open

.. _option_filter:

filter
~~~~~~

The filter option allows the definition of a complex query string, which gets evaluated via eval() in Python.
Please see :ref:`filter_string` for more details.

.. _filter_string:

Filter string
-------------

The usage of a filter string is supported/required by:

* :ref:`Conditional links <need_conditional_links>` (to assert properties of a link target)
* :ref:`need_count`
* :ref:`needlist`
* :ref:`needtable`
* :ref:`needflow`
* :ref:`needpie`
* :ref:`needbar`
* :ref:`needuml` / :ref:`needarch`


The filter string must be a valid Python expression:

.. syntax-example::

   :need_count:`type=='spec' and status != 'open'`

A filter string gets evaluated on needs and need_parts!
A need_part inherits all options from its parent need, if the need_part has no own content for this option.
E.g. the need_part *content* is kept, but the *status* attribute is taken from its parent need.

.. note::

   The following attributes are kept inside a need_part: id, title, links_back

This allows to perform searches for need_parts, where search options are based on parent attributes.

The following filter will find all need_parts, which are part of a need, which has a tag called *important*.

.. syntax-example::

   :need_count:`is_part and 'car' in tags`

Inside a filter string all the fields of :py:class:`.NeedsInfoType` can be used, including.

Additional variables for :ref:`need_part`:

* **id_parent** as Python string, which contains the id of the parent need. (compare like ``id_parent == "ABC_01"``)
* **id_complete** as Python string. Contains the concatenated ids of parent need and need_part.
  (compare like ``id_complete != 'ABC_01.03'``)

.. note:: If extra fields were specified using :ref:`needs_fields` then
          those will be available for use in filter expressions as well.

Finally, the following are available:

* :ref:`re_search`, as Python function for performing searches with a regular expression
* **needs** as :class:`.NeedsAndPartsListView` object, which contains all needs and need_parts.

A filter is read for its truth: if your expression is valid and its value is true by Python's rules, whatever its type,
the related need is added to the filter result list -- an empty string, an empty list, ``0`` and ``None`` are false,
so ``tags`` selects the needs that have tags.
If it is invalid or its value is false, the related need is not taken into account for the current filter.

A filter that is a constant alone says nothing about a need, as its value is the same on every need:
a literal (a string, bytes, a number with one sign or none, ``None`` or ``...``),
a tuple, list, set or dict display that unpacks nothing, whatever it holds
(``[1]``, ``{1}``, ``{}``, and so the trailing-comma typo ``status == 'open',``),
a generator expression (``(t for t in tags)``, which is true whatever it would yield),
or an f-string with no placeholder, parenthesised or not, after any leading spaces and tabs.
``True`` and ``False`` are the exception: ``True`` selects every need, and ``False`` none.
``--5`` and ``-True`` are arithmetic, and a display that unpacks (``[*tags]``), a list, set or dict comprehension
or an f-string with a placeholder is read by its truth, as is a constant inside a larger filter (``True and owner``).

The directives and roles that list or count needs -- :ref:`needlist`, :ref:`needtable` and the other views,
:ref:`need_count`, a content line of :ref:`needpie` or :ref:`needbar`, :ref:`needextend` -- and
:ref:`needs_warnings`, :ref:`needs_builder_filter`, the ``filter()`` of :ref:`needuml <needuml_jinja_filter>` and
the dynamic function ``copy(filter=...)`` refuse a constant before it is evaluated, with one ``needs.filter`` warning,
and select nothing.
:ref:`needimport`, a predicate of :ref:`needs_fields`, ``links_from_filter`` and ``links_from_match`` refuse it the same
way, with the warning they give for a filter that fails.
Anywhere else, a constant fails the way a filter that cannot be evaluated fails there.

.. dropdown:: Show example

   .. syntax-example:: ``filter`` option

      needs:

      .. req:: Requirement A
         :tags: A; filter_example
         :status: open
         :hide:

      .. req:: Requirement B
         :tags: B; filter_example
         :status: closed
         :hide:

      .. spec:: Specification A
         :tags: A; filter_example
         :status: closed
         :hide:

      .. spec:: Specification B
         :tags: B; filter_example
         :status: open
         :hide:

      .. test:: Test 1
         :tags: filter_example
         :hide:

      .. needlist::
         :filter: "filter_example" in tags and (("B" in tags or ("spec" == type and "closed" == status)) or "test" == type)

.. _filter_variant_data:

Using variant data (``var``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 8.2.0

If :ref:`needs_variant_data` or :ref:`needs_variant_data_file` is configured,
a ``var`` namespace is available in filter expressions, providing dot-access to nested structured data.

This is useful for switching build outputs based on external configuration (CPU architecture, debug/release mode, feature flags, etc.)
without polluting the need field namespace.

The dot-access syntax mirrors `Jinja2 template syntax <https://jinja.palletsprojects.com/en/latest/templates/#variables>`__,
making it familiar to Sphinx users.

**Examples:**

.. code-block:: rst

   .. needtable::
      :filter: var.cpu == "arm"

   .. needlist::
      :filter: var.build.debug == True and var.build.optimization > 1

   .. needtable::
      :filter: "feature_a" in var.build.features

Accessing a key that doesn't exist raises an error, which helps catch typos:

.. code-block:: rst

   .. needlist::
      :filter: var.typo == "x"
      .. this will raise AttributeError: Unknown variant key: var.typo

See :ref:`needs_variant_data` for configuration details and allowed data shapes.

.. _filter_current_page:

Filtering for needs on the current page
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 5.0.0

Additionally, to common :ref:`filter_string` variables,
the ``c.this_doc()`` function is for most directives,
to filter for needs only in the same document as the directive.

.. syntax-example::

   .. needtable::
      :filter: c.this_doc()
      :style: datatables

It is available in the filters of the need-listing and diagram directives —
including ``needsequence`` ``:filter:``, ``needflow`` ``:highlight:``,
``needgantt`` ``:milestone_filter:`` and, on ``needpie`` and ``needbar``,
both the filter lines and the scope ``:filter:``.
It is *not* available to filters configured in **conf.py**,
such as :ref:`needs_constraints` and :ref:`needs_warnings`,
since those are not written in any document;
using it there raises ``this_doc can not be used in this context``.
It is likewise unavailable in ``needimport`` ``:filter:``, which runs against
needs imported from another project, and in ``needuml`` content filters.

.. _filter_type_ancestors:

Filtering for a type and the types inheriting from it
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 9.2.0

``type == 'req'`` compares the type's name: it selects the needs of type ``req`` and no other,
not those of a type that :ref:`inherits <needs_types_fields>` from ``req``.
Every need carries ``type_ancestors``, its type and then each type it inherits from, nearest first,
so a filter can follow ``inherits`` with the membership test of the portable filter language:

.. code-block:: toml

   [needs.types.safety_req]
   title = "Safety requirement"
   prefix = "SR_"
   inherits = "req"

.. code-block:: rst

   .. needtable::
      :filter: 'req' in type_ancestors

selects every ``req`` and every ``safety_req``; a ``safety_req`` need has ``type_ancestors`` ``["safety_req", "req"]``.

- A type that inherits from no other type has itself alone, ``["req"]``,
  as has a type whose ``inherits`` names no need type or is on a cycle:
  that ``inherits`` is ignored, with a ``needs.type_inherits`` warning.
- A name that is no need type selects nothing, and is not reported: ``'rq' in type_ancestors`` is false on every need,
  as ``type == 'rq'`` is.
- A need part has its need's.
- It is computed from the project's need types, and cannot be set: it is no directive option,
  :ref:`needextend` cannot change it, and a :ref:`needs_fields` entry of that name declares no field.
  A need read from a ``needs.json`` (:ref:`needimport`, :ref:`needs_external_needs`)
  takes the value the reading project's need types give it, whatever the file says.
- It is not written to the :ref:`needs.json <needs_builder>`:
  to write it, set :ref:`needs_json_exclude_fields` to a list without it.

It is a field like any other where a field is read:
in a derived field's ``where`` (:ref:`needs_derive`), in a :ref:`needtable` column,
and in a :ref:`schema rule <schema_validation>`, as ``type_ancestors: {contains: {const: req}}``.

``c.is_a('req')`` says the same as ``'req' in type_ancestors``, and reads better in a longer filter:

.. code-block:: rst

   .. needtable::
      :filter: c.is_a('req') and not c.is_a('safety_req')

selects the ``req`` needs and the needs of every other type inheriting from ``req``, but not the ``safety_req`` ones.
Its argument is a string literal in the portable filter language: ``c.is_a(type)`` or ``c.is_a('req') == True``
is evaluated by ``eval``, as ``c.this_doc() == True`` is.
Unlike :ref:`c.this_doc() <filter_current_page>` it reads the need alone, so it is available wherever a filter string is,
in **conf.py** too, and in a derived field's ``where``.

.. _re_search:

search
~~~~~~

search(pattern, variable) is based on
`Pythons re.search() function <https://docs.python.org/3/library/re.html#re.search>`_

The first parameter must be a regular expression pattern.
The second parameter should be one of the above variables(status, id, content, ..)

In the :ref:`portable filter language <filter_string_performance>` the pattern is a plain string literal:
it has no raw strings (``r"..."``), so a backslash is written twice (``"\\d+"``), or avoided with a
character class (``"[.]"``). The pattern is read with Python's regular expression syntax;
look-around, backreferences and ``{,n}`` are Python's own and not part of the portable language.

.. dropdown:: Show example

   This example uses a regular expressions to find all needs with an e-mail address in title.

   .. syntax-example::

      .. req:: Set admin e-mail to admin@mycompany.com

      .. needlist::
         :filter: search("([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+[.][a-zA-Z0-9-.]+$)", title)

.. _filter_string_performance:

Filter string performance
~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 4.0.0

.. versionchanged:: 9.1.0
   The second tier compiles the whole portable filter language,
   and :ref:`needs_debug_filters` records which tier answered each filter.

The filter string is evaluated for each need and need part
and, therefore, can become a performance bottleneck for projects with large numbers of needs.
Sphinx-Needs answers a filter string with the first of three tiers that takes it,
so writing filters the first two take is recommended:

1. **The index path.** A few shapes are answered from indexes the needs keep,
   without evaluating the filter need by need:

   - ``is_external`` / ``is_external == True`` / ``is_external == False``
   - ``id == 'value'`` / ``'value' == id`` / ``id in ['value1', 'value2', ...]``
   - ``type == 'value'`` / ``'value' == type`` / ``type in ['value1', 'value2', ...]``
   - ``status == 'value'`` / ``'value' == status`` / ``status in ['value1', 'value2', ...]``
   - ``'value' in tags``
   - ``True`` / ``False``

   A filter of the form ``a and b and ...`` is split, and each of its parts of these shapes narrows the needs first:
   ``type == 'spec' and other == 'value'`` is filtered by ``type == 'spec'`` from the index,
   and only the remaining needs are evaluated for ``other == 'value'``.

2. **The portable filter language.** A string written in it is compiled once
   and evaluated need by need without Python's ``eval``, reading only the fields it names,
   which makes it five to six times faster than ``eval`` for the same string.
   A conformance corpus (``tests/fixtures/filter_conformance.toml`` in the Sphinx-Needs repository)
   defines the language and pins every form's answers; the language is also the one
   `ubCode <https://ubcode.useblocks.com>`__ reads, so a filter written in it works there too.
   It has:

   - **operands**: a field (any field of the need, a :ref:`needs_filter_data` key,
     a :ref:`variant data <filter_variant_data>` key such as ``var.build.debug``),
     ``len(field)``, ``field.lower()`` and ``field.upper()``;
   - **literals**: a string in single or double quotes, an integer or a float (``-1``, ``2.5``, ``1e-3``),
     ``True``, ``False``, ``None``, and a list of those after ``in``;
   - **comparisons** ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=`` between an operand and a literal, either way round
     (``<`` and the others with a number literal only), or between two operands:
     ``status == 'open'``, ``5 <= priority``, ``owner == lead``, ``len(tags) > 0``;
   - **membership**: an operand ``in`` / ``not in`` a list of literals,
     and a literal ``in`` / ``not in`` an operand -- an item of a list, a substring of a string:
     ``type in ['req', 'spec']``, ``'safety' in tags``, ``'login' not in title.lower()``,
     ``'req' in type_ancestors`` (see :ref:`filter_type_ancestors`);
   - ``x is None`` / ``x is not None``;
   - ``x.startswith('...')`` / ``x.endswith('...')`` after an operand: ``id.lower().startswith('req')``;
   - ``search('pattern', x)`` (see :ref:`re_search`), with a plain string literal as the pattern;
   - ``c.this_doc()`` (see :ref:`filter_current_page`), and ``c.is_a('...')`` with a string literal
     (see :ref:`filter_type_ancestors`);
   - ``and``, ``or``, ``not``, parentheses, and an operand alone, which is read by its truthiness.

   Not in it, and so evaluated by ``eval``: a field ``in`` a field (``sphinx_tag in tags``),
   a list beside ``==`` or ``!=`` (``tags == ['a']``; write ``len(tags) == 1 and 'a' in tags``),
   arithmetic, subscripts (``sections[0]``), comprehensions, any other call or method (``any(...)``, ``bool(x)``, ``x.strip()``),
   ``is`` with anything but ``None``, a chain of comparisons (``1 < x < 5``), a dotted name not under ``var.``,
   and the names ``needs`` and ``current_need``.

3. **Python's** ``eval``, for every other string: it is evaluated need by need against a context holding every field of the need,
   which costs far more than the first two tiers, nearly all of it building that context.

The three tiers give the same answers, with three exceptions:

- **A field or** :ref:`needs_filter_data` **key named** ``len``: ``eval`` calls it in ``len(x)``, the portable
  language calls Python's ``len``.
- **The name of a Python builtin alone under** ``not``, ``and`` **or** ``or`` (``filter and status == 'open'``):
  ``eval`` reads the builtin, the portable language reports the name as undefined. As the whole filter
  (``filter``), the portable language reports it as undefined too, where ``eval`` would read the builtin, which is true.
- ``search`` **and the** ``__dunder__`` **names** (``__name__``, ``__debug__``) **compared with a literal, or alone**
  (``search == 'x'``, ``__name__ == 'builtins'``, ``__debug__``): ``eval`` reads its own binding -- the regular
  expression function, the builtins module's attributes -- and the portable language reports the name as undefined,
  as it did before 9.1.0. Beside a field (``owner != search``) the string falls to ``eval`` and answers as it does.

A few forms the second tier answers are older than the portable language and not part of it:
``<`` and the other orderings between a field and a literal that is no number (``title < 'M'``, ``owner > True``,
``owner < None``), a tuple or a set after ``in``, a constant the language has no literal for beside a field
(``status == b"x"``, ``status == ...``, ``status == 1j``), and ``not not x`` (write ``not (not x)``).
The second tier also reads a string's syntax rather than its spelling, and puts no limit on its size,
so it answers what the language leaves out for spelling or size alone: an integer outside the signed 64-bit range, more than 10 000
terms once the filter is expanded into alternatives of conjunctions, nesting deeper than 64, a string longer than
16 KiB, and spellings such as a parenthesised operand (``len((tags)) > 0``), a trailing comma, a comment, triple
quotes, ``.5``, ``1e+5``, ``-(1)`` or a name that is not ASCII. Each answers as ``eval`` answers it, and in
``search()`` look-around, backreferences and ``{,n}`` are Python's own.

To see which tier answers each filter of a project's view directives, and why one reaches ``eval``,
enable :ref:`needs_debug_filters`: every record says ``tier`` (``"index"``, ``"fast"`` for the portable language, ``"eval"``,
or ``"refused"`` for a constant) and, for ``"eval"``, ``fallback_reason``, the construct that kept the string out of the portable language.

To guard against long running filters, the :ref:`needs_filter_max_time` configuration option can be used to set a maximum time limit for filter evaluation.
Also see :ref:`needs_uml_process_max_time`, to guard against long running ``needuml`` / ``needarch`` processes containing :ref:`filters <needuml_jinja_filter>`.

To debug which filters are being used across your project, their run times and the tier answering each, you can enable the :ref:`needs_debug_filters` configuration option.

.. _export_id:
.. deprecated:: 4.0.0

   The directive option ``export_id`` was previously used to export filter information in the ``needs.json`` file.
   This is deprecated and will be removed in a future version.
   Instead use the above :ref:`needs_debug_filters` configuration option.

.. _ubcode_compat_options:
.. note::

   **Options accepted for ubCode compatibility.**
   The `ubCode <https://ubcode.useblocks.com>`__ editor extension supports a few directive options that Sphinx-Needs
   has no equivalent for:

   * ``cypher`` on :ref:`needlist`, :ref:`needtable`, :ref:`needflow`, :ref:`needpie`
     and :ref:`needbar`
   * ``width`` and ``height`` on :ref:`needflow` and :ref:`needsequence`

   Sphinx-Needs accepts all of these options and then ignores them, so that a document authored for ubCode also
   builds with Sphinx-Needs instead of failing with an ``unknown option`` error.
   They never reach the rendered output, the ``needs.json`` file, or any filter.

   This includes ``width`` and ``height``: a diagram is rendered at its usual size and no warning is emitted,
   so nothing reports that the requested size had no effect.

   ``cypher`` on a chart is the one option whose no-op changes a rendered number:
   ubCode reads the query as the scope the content lines are counted over,
   whereas a Sphinx build ignores it,
   so the same chart can show different numbers here than in the ubCode preview.
   Write the same scope with ``:filter:``, ``:status:``, ``:tags:`` or ``:types:``
   beside the query and both tools select the same needs;
   see :ref:`needpie_scope` and :ref:`needbar_scope`.

   These options may gain native implementations in future Sphinx-Needs releases,
   in which case they would take effect here as well rather than being ignored.
   ``max_items`` was such a case: it is no longer ignored, but limits how many items a view shows,
   see :ref:`needs_views_max_items`.

.. _filter_code:

Filter code
-----------

.. versionadded:: 0.5.3

The content of a :ref:`needlist`, :ref:`needtable` or :ref:`needflow` can be used to define own filters
with the help of Python.

The used code must define a variable ``results``, which must be a list and contains the filtered needs.

The code also has access to a variable called ``needs``, which is a :class:`.NeedsAndPartsListView` instance.

.. syntax-example::

   .. needtable::
      :columns: id, title, type, links, links_back
      :style: table

      # Collect all requirements and specs,
      # which are linked to each other.

      results = []
      
      for need in needs.filter_types(["req"]):
         for links_id in need['links']:
            linked_need = needs.get_need(links_id)
            if linked_need and linked_need['type'] == 'spec':
               results.append(need)
               results.append(linked_need)

This mechanism can also be a good alternative for complex filter strings to save performance.
For example if a filter string is using list comprehensions to get access to linked needs.

If ``filter code`` is used, all other filter related options (like ``status`` or ``filters``) are ignored.

.. warning::

   This feature executes every given Python code.
   So be sure to trust the input/writers.


.. _filter_func:

Filter function
---------------

.. versionadded:: 0.7.3

Nearly same behavior as :ref:`filter_code`, but the code gets read from an external python file and a function must be
referenced.

:option name: filter-func
:default: None

Usage inside a rst file:

.. code-block:: rst

    .. needtable:: Filter function example
       :filter-func: filter_file.own_filter_code

The code of the referenced file ``filter_file.py`` with function ``own_filter_code``:

.. code-block:: python

   def own_filter_code(needs, results, **kwargs):
       for need in needs:
           if need["type"] == "test":
               results.append(need)

The function gets executed by **Sphinx-Needs** and it must provide two keyword arguments: ``needs`` and ``results``.

Also the given package/module must be importable by the used Python environment.
So it must be part of the Python Path variable. To update this, add
``sys.path.insert(0, os.path.abspath("folder/to/filter_files"))`` to your **conf.py** file.

Arguments
~~~~~~~~~
.. versionadded:: 0.7.6

Filter function are supporting arguments: ``filter_file.own_filter_code(value_1,value_2)``.

Please note, that the part between ``(...)`` is just a comma separated list and each element will be given as string
to the function.

The functions get the values as part of ``**kwargs`` with the name is ``arg<pos>``, starting from ``1``.

Example:

.. code-block:: rst

    .. needtable:: Filter function example
       :filter-func: filter_file.own_filter_code(1,2.5,open)


.. code-block::

   def own_filter_code(needs, results, **kwargs):
       for need in needs:
           if int(need["price"]) > int(kwargs["arg1"]) or need["status"] == kwargs["arg3"]:
               results.append(need)

The function developer is responsible to perform any needed typecast.

Needpie
~~~~~~~
:ref:`needpie` also supports filter-code.
But instead of needs, a list of resulting numbers must be returned.

Example:

.. code-block:: rst

   .. needpie:: Filter code func pie
      :labels: new,done
      :filter-func: filter_code_func.my_pie_filter_code_args(new,done)


.. code-block:: python

   def my_pie_filter_code_args(needs, results, **kwargs):
       cnt_x = 0
       cnt_y = 0
       for need in needs:
           if need["status"] == kwargs['arg1']:
               cnt_x += 1
           if need["status"] == kwargs['arg2']:
               cnt_y += 1

      results.append(cnt_x)
      results.append(cnt_y)

Filter matches nothing
----------------------

Depending on the directive used a filter that matches no needs may add text to inform that no needs are found.

The default text "No needs passed the filter".

If this is not intended, add the option

.. _option_filter_warning:

filter_warning
~~~~~~~~~~~~~~

Add specific text with this option or add no text to display nothing. The default text will not be shown.

The specified output could be styled with the css class ``needs_filter_warning``

More Examples
-------------

.. dropdown:: Setup

   .. syntax-example::

      .. req:: My first requirement
         :status: open
         :tags: requirement; test; awesome

         This is my **first** requirement!!

         .. note:: You can use any rst code inside it :)

      .. spec:: Specification of a requirement
         :id: OWN_ID_123
         :links: R_F4722

         Outgoing links of this spec: :need_outgoing:`OWN_ID_123`.

      .. impl:: Implementation for specification
         :id: IMPL_01
         :links: OWN_ID_123

         Incoming links of this spec: :need_incoming:`IMPL_01`.

      .. test:: Test for XY
         :status: implemented
         :tags: test; user_interface; python27
         :links: OWN_ID_123; IMPL_01

         This test checks :need:`IMPL_01` for :need:`OWN_ID_123` inside a
         Python 2.7 environment.


.. syntax-example:: Filter result as table

   .. needtable::
      :tags: test
      :status: implemented; open

.. syntax-example:: Filter result as diagram

   .. needflow::
      :filter: "More Examples" == section_name
