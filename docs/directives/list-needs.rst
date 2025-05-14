.. _list-needs:

list-needs
----------

.. versionadded:: 5.2.0

``list-needs`` provides a shorthand notation to create multiple nested needs in one go.

The content of the directive should contain a standard :external+sphinx:ref:`rst-field-lists` block,
with each item in the list representing a need.

Similar to the :ref:`need directive <need>`, *field name* should start with the need type.
Proceeding options in the field name can then be specified as white-space delimited; keys with no values (``key``),
keys with simple (non-whitespace) values (``key=value``), or keys with quoted values (``key="value with space"``).

Allowed field name options are:
``id``, ``title``, ``status``, ``tags``, ``collapse``, ``delete``, ``hide``, ``layout``, ``style``, ``constraints``,
:ref:`needs_extra_options`, and :ref:`needs_extra_links`.

Unless specified in the field name parameters, the **title** is taken as the first paragraph of the field content,
and the **content** is taken as the rest of the field content.

.. need-example:: Simple ``list-needs`` example

    .. list-needs::

        :req id=LIST-1a: Need example title

            Need example on level 1.
        :req id=LIST-1b:
            Another Need example with nested needs.

            :spec id=LIST-s2a status=open tags=list-tag1,list-tag2 author="John Doe": 
                Sub-Need on level 2 with other options set
            :spec id=LIST-s2b title="Another Sub-Need on level 2.": 
                With the title given in the parameters.

                :test id=LIST-s3 collapse: Sub-Need on level 3.
                
                    Content can contain standard *syntax*.

Options
-------

``defaults``
~~~~~~~~~~~~

This option allows you to set default values for all needs in the list, it is parsed as a field list similar to the :ref:`need directive options <need>`.
Defaults will be overridden by any options set in the field name.

.. need-example:: ``defaults`` option

    .. list-needs::
        :defaults:
            :status: open
            :tags: list-tag1,list-tag2

        :req id=LIST-d1: Need level 1

            :spec id=LIST-d2 status=closed: Sub-Need level 2



``maxdepth``
~~~~~~~~~~~~

The ``maxdepth`` option allows you to limit the depth of converted field lists.

.. need-example:: ``maxdepth`` option

    .. list-needs::
        :maxdepth: 1

        :req id=LIST-m1: Need level 1

            :normal: field list

``links-up`` and ``links-down``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``links-up`` and ``links-down`` options allow you to define links between needs in the list,
according to their structure.
Both are a comma-delimited list, with each item representing a link type for the corresponding level (starting from 1).

.. need-example:: ``links-up`` and ``links-down`` options

    .. list-needs::
        :links-down: blocks, triggers
        :links-up: tests, checks

        :req id=LIST-l1: Need level 1

            :spec id=LIST-l2a: Sub-Need level 2a
            :spec id=LIST-l2b: Sub-Need level 2b

                :test id=LIST-l3: Sub-Need level 3

``flatten``
~~~~~~~~~~~

The ``flatten`` option will flatten all nested needs into a single list.

It can be used in combination with the ``links-up`` and ``links-down`` options,
to define links by structure, without the final representation being nested.

.. need-example:: ``flatten`` option

    .. list-needs::
        :links-down: blocks, triggers
        :links-up: tests, checks
        :flatten:

        :req id=LIST-f1: Need level 1

            :spec id=LIST-f2a: Sub-Need level 2a
            :spec id=LIST-f2b: Sub-Need level 2b

                :test id=LIST-f3: Sub-Need level 3
