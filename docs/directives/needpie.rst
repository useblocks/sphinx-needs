.. _needpie:

needpie
========

.. versionadded:: 0.5.0

``needpie`` adds a pie-chart to your documentation.

.. syntax-example::

   .. needpie:: My pie chart

      type == 'req'
      type == 'spec'
      10

If you provide an argument for the ``needpie``, we use it as the title.

Each content line gets interpreted either as a static value or as a :ref:`filter_string`.
The amount of found needs by the filter string is then used as value.

A static value has to be written as a non-negative integer, like ``10``.
Anything else, ``10.5`` and ``-5`` included, is read as a filter string.
Those two then give a ``needs.filter`` warning and count as zero,
because a filter is expected to evaluate to a boolean and a number does not.

Not every non-boolean filter is rejected that way, though:
a simple enough expression, such as the bare field name ``tags``,
is answered by the query fast path, which coerces the result with ``bool()``
and counts the matching needs instead of warning.

You can use :ref:`filter_func` with Python codes to define custom filters for ``needpie``.
Give either content lines or ``:filter-func:``: if both are given,
or neither, the chart has no data and an error is logged.

``needpie`` takes no other filter options,
so ``:filter:``, ``:status:``, ``:tags:`` and ``:types:`` are not available on it.
The ubCode-only ``cypher`` option is accepted and then ignored,
which for ``needpie`` means the content lines are counted over the whole project
rather than over the needs the query selects;
see :ref:`ubCode compatibility <ubcode_compat_options>`.

.. note::

    One image file is written per ``needpie``,
    in the first image type the document engine accepts that Matplotlib can produce.
    For the HTML builders that is SVG.

Options
-------

**Example with all options used:**

.. syntax-example::

   .. needpie:: Requirement status
      :labels: Open, In progress, Closed
      :legend:
      :shadow:
      :explode: 0, 0.3, 0
      :colors: #ffcc00, #444444, limegreen
      :text_color: crimson
      :style: dark_background

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'


labels
~~~~~~

Use ``:labels:`` to set labels for each value.

``:labels:`` must get a comma separated string and the amount of labels must match the amount of
values/lines from content.

.. warning::

   A different amount of labels than values currently ends the build
   with a Matplotlib error, rather than a warning.

.. syntax-example::

   .. needpie:: Requirement status
      :labels: Open, In progress, Closed

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'


legend
~~~~~~

You can place a legend on the right side of the pie chart by setting the ``:legend:`` flag.

The ``:legend:`` flag does not support any values.

.. syntax-example::

   .. needpie:: Requirement status
      :labels: Open, In progress, Closed
      :legend:

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'


explode
~~~~~~~

``:explode:`` takes a comma-separated list of floats and defines how much space a specific pie-part
moves of from center.

The amount of values for ``:explode:`` must match the amount of values / content lines.

Useful values for ``:explode:`` are between ``0`` and ``0.3``

.. warning::

   As with ``:labels:``, a differing amount of values ends the build with a Matplotlib
   error. A value that is not a number ends it while the document is being read.

.. syntax-example::

   .. needpie:: Requirement status
      :explode: 0,0.2,0

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'


shadow
~~~~~~

``:shadow:`` activates a shadow in the pie chart. It does not support any further values.

.. syntax-example::

   .. needpie:: Requirement status
      :explode: 0,0.2,0
      :shadow:

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'

colors
~~~~~~

``:color:`` takes a comma separated list of color names and uses them for the pie pieces.

See `Matplotlib documentation of supported colors <https://matplotlib.org/stable/gallery/color/named_colors.html>`_
for a complete list of color names.

But besides names, the ``:colors:`` option also supports hex-values like ``#ffcc00``.

.. syntax-example::

   .. needpie:: Requirement status
      :colors: lightcoral, gold, #555555

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'

text_color
~~~~~~~~~~

``:text_color:`` defines the color for text inside the pie pieces and the labels.

.. note:: Setting the ``:text_color:`` option does not change the legend and title color.

.. syntax-example::

   .. needpie:: Requirement status
      :text_color: w

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'

style
~~~~~

``:style:`` activates a complete style (colors, font, sizes) for a pie chart.
It takes a string, which must match the
`supported Matplotlib style names <https://matplotlib.org/3.1.1/gallery/style_sheets/style_sheets_reference.html>`_.

Useful styles are for example:

* default
* classic
* Solarize_Light2
* dark_background
* grayscale

.. syntax-example::

   .. needpie:: Requirement status
      :style: Solarize_Light2

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'

filter_warning
~~~~~~~~~~~~~~

A pie whose values are all zero is not drawn.
``:filter_warning:`` sets the text that is shown in its place.

Without the option, the text is "No needs passed the filters".
Give the option without a value to show nothing at all.

.. syntax-example::

   .. needpie:: Requirement status
      :labels: Open, Closed
      :filter_warning: No requirement has one of these statuses

      type == 'req' and status == 'no_such_status_a'
      type == 'req' and status == 'no_such_status_b'


overlapping labels
~~~~~~~~~~~~~~~~~~

In the past we had overlapping labels. See following diagram.

.. image:: /_images/need_pie_overlapping_labels.png
  :alt: Example of a needpie with overlapping labels

Now overlapping labels are removed, and we automatically add a legend with removed information.

.. syntax-example::

   .. needpie:: Requirement status
      :labels: New, Open, In progress, Closed, Outdated, Removed

      90
      7
      6
      5
      0
      0
