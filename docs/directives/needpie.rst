.. _needpie:

needpie
========

.. versionadded:: 0.5.0

``needpie`` adds a pie-chart to your documentation::

   .. needpie:: My pie chart

      type == 'req'
      type == 'spec'
      10

.. needpie:: My pie chart

   type == 'req'
   type == 'spec'
   10

The argument of the ``needpie`` will be used as title for the pie.

Each content line gets interpreted either as static float/int value or as a :ref:`filter_string`.
The amount of found needs by the filter string is then used as value.

``needpie`` supports also own defined filters with the help of Python code through :ref:`filter_func`.

Options
-------

.. contents::
   :local:

Example with all options used:

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

.. code-block:: rst

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

.. needpie:: Requirement status
   :labels: Open, In progress, Closed

   type == 'req' and status == 'open'
   type == 'req' and status == 'in progress'
   type == 'req' and status == 'closed'

.. code-block:: rst

   .. needpie:: Requirement status
      :labels: Open, In progress, Closed

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'

legend
~~~~~~

If ``:legend:`` is given, a legend will be placed to the right side of the pie chart.

``:legend:`` is a flag and does not support any values.


.. needpie:: Requirement status
   :labels: Open, In progress, Closed
   :legend:

   type == 'req' and status == 'open'
   type == 'req' and status == 'in progress'
   type == 'req' and status == 'closed'

.. code-block:: rst

   .. needpie:: Requirement status
      :labels: Open, In progress, Closed
      :legend:

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'

explode
~~~~~~~

``:explode:`` takes a comma-separated list of floats and defines how much space a specific pie-part
shall be moved of from center.

The amount of values for ``:explode:`` must match the amount of values / content lines.

Useful values for ``:explode:`` are between ``0`` and ``0.3``

.. needpie:: Requirement status
   :explode: 0,0.2,0

   type == 'req' and status == 'open'
   type == 'req' and status == 'in progress'
   type == 'req' and status == 'closed'


.. code-block:: rst

   .. needpie:: Requirement status
      :explode: 0,0.2,0

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'

shadow
~~~~~~

``:shadow:`` activates a shadow in the pie chart. It does not support any further values.

.. needpie:: Requirement status
   :explode: 0,0.2,0
   :shadow:

   type == 'req' and status == 'open'
   type == 'req' and status == 'in progress'
   type == 'req' and status == 'closed'


.. code-block:: rst

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

But beside names also hex-values like ``#ffcc00`` are supported.

.. needpie:: Requirement status
   :colors: lightcoral, gold, #555555

   type == 'req' and status == 'open'
   type == 'req' and status == 'in progress'
   type == 'req' and status == 'closed'


.. code-block:: rst

   .. needpie:: Requirement status
      :colors: lightcoral, gold, #555555

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'

text_color
~~~~~~~~~~

``:text_color:`` defines the color for text inside the pie pieces and the labels.
The legend and title color are not changed.

.. needpie:: Requirement status
   :text_color: w

   type == 'req' and status == 'open'
   type == 'req' and status == 'in progress'
   type == 'req' and status == 'closed'


.. code-block:: rst

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

.. needpie:: Requirement status
   :style: Solarize_Light2

   type == 'req' and status == 'open'
   type == 'req' and status == 'in progress'
   type == 'req' and status == 'closed'


.. code-block:: rst

   .. needpie:: Requirement status
      :style: Solarize_Light2

      type == 'req' and status == 'open'
      type == 'req' and status == 'in progress'
      type == 'req' and status == 'closed'





