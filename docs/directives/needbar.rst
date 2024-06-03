.. _needbar:

needbar
========

.. versionadded:: 0.7.5

``needbar`` adds a bar-chart to your documentation:

.. need-example::

   .. needbar::

      5,20,15
      10,15,10
      15,10,20
      20,15,10

Each content value gets interpreted either as static float/int value or as a :ref:`filter_string`.
The amount of found needs by the filter string is then used as value.

.. note::

    This generates multiple image files per ``needbar`` and allows
    the document engine to pick the appropriate image type (vector or raster).

Options
-------

Example with all options used:

.. need-example::

   .. needbar:: Full bar chart
      :legend:
      :colors: #ffcc88, #ffcc00, #444444
      :text_color: crimson
      :style: dark_background
      :x_axis_title: x_axis_title
      :xlabels_rotation: 90
      :xlabels: a, b, c
      :y_axis_title: y_axis_title
      :ylabels: FROM_DATA
      :ylabels_rotation: 45
      :separator: ;
      :stacked:
      :show_top_sum:
      :show_sum:
      :sum_rotation: 90
      :transpose:
      :horizontal:

      Z; 5;20;15
      Y;10;15;10
      X;15;10;20
      W;20;15;10

title
~~~~~

You can specify the headline of the bar chart using the ``title`` argument.

.. need-example::

   .. needbar:: Title example

      5,20,15
      10,15,10
      15,10,20
      20,15,10

It is possible to create bar charts without title.

.. need-example::

   .. needbar::

      5,20,15
      10,15,10
      15,10,20
      20,15,10

content
~~~~~~~

In the example below, we fetch the ``:xlabels:`` and ``:ylabels:`` options from the content using ``FROM_DATA`` with the `labels`_.
You can use white spaces to format the table to improve readability.

From the content, we interpret each value either as a static float/int value or as a :ref:`filter_string`.
We get the bar chart's data (values) from the amount of **need** objects found by the filter string.

Below is a more realistic example with data fetched from filters, together with hardcoded data:

.. need-example::

   .. needbar:: A more real bar chart
      :legend:
      :xlabels: FROM_DATA
      :ylabels: FROM_DATA

                   ,                           open ,                          in progress ,                          closed ,                          done ,                          implemented , number
        Requirement, type=='req' and status=='open', type=='req' and status=='in progress', type=='req' and status=='closed', type=='req' and status=='done', type=='req' and status=='implemented', 5
               Test, type=='test' and status=='open', type=='test' and status=='in progress', type=='test' and status=='closed', type=='test' and status=='done', type=='test' and status=='implemented', 7
      Specification, type=='spec' and status=='open', type=='spec' and status=='in progress', type=='spec' and status=='closed', type=='spec' and status=='done', type=='spec' and status=='implemented', 9

legend
~~~~~~

You can place a legend on the barchart by setting the ``:legend:`` flag.

The ``:legend:`` flag does not support any values.

.. need-example::

   .. needbar:: Legend example
      :legend:

      5,20,15
      10,15,10
      15,10,20
      20,15,10

axis title
~~~~~~~~~~

You can enable axis titles on the barchart by setting the ``:x_axis_title:`` or ``:y_axis_title:`` options.

.. hint::
   If you use `horizontal`_ or `transpose`_, the meaning of ``:x_axis_title:`` and ``:y_axis_title:`` must be understandable.
   So you have to change the description accordingly.

.. need-example::

   .. needbar:: Axis title example
      :x_axis_title: types
      :y_axis_title: numbers

      5,20,15
      10,15,10
      15,10,20
      20,15,10

labels
~~~~~~

| Use ``:xlabels:`` to set labels for columns of the data.
| Use ``:ylabels:`` to set labels for row of the data.

You can define the ``:xlabels:`` and/or ``:ylabels:`` by setting a comma separated string.
The amount of labels must match the amount of values/lines from content. |br|
Also, you can set the ``:xlabels:`` and/or ``:ylabels:`` value to ``FROM_DATA`` to fetch the labels from the content.

.. hint::
   In a normal bar chart, we use the ``:xlabels:`` as the labels of the x-axis on the chart and the ``:ylabels:`` as the labels of legend.

   But if you use `horizontal`_ or `transpose`_, the meaning of ``:x_axis_title:`` and ``:y_axis_title:`` will change automatically.

.. need-example::

   .. needbar:: Labels example 1
      :legend:
      :xlabels: a, b, c
      :ylabels: Z, Y, X, W

       5,20,15
      10,15,10
      15,10,20
      20,15,10

   .. needbar:: Labels example 2
      :legend:
      :xlabels: FROM_DATA
      :ylabels: FROM_DATA

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


stacked
~~~~~~~

You can render the barchart in a stacked design by setting ``:stacked:`` flag.

The ``:stacked:`` flag does not support any values.

.. need-example::

   .. needbar:: stacked example
      :stacked:

      5,20,15
      10,15,10
      15,10,20
      20,15,10

show_sum
~~~~~~~~

You can render the barchart with detailed information of the height of each bar by setting the ``:show_sum:`` flag.

The ``:show_sum:`` flag does not support any values and it's useful with the ``stacked`` option  enabled.

.. need-example::

   .. needbar:: show_sum example 1
      :show_sum:

      5,20,15
      10,15,10
      15,10,20
      20,15,10

   .. needbar:: show_sum example 2
      :stacked:
      :show_sum:

      5,20,15
      10,15,10
      15,10,20
      20,15,10


show_top_sum
~~~~~~~~~~~~

You can render the barchart with detailed information of the height of each bar above by setting the ``:show_top_sum:`` flag.

The ``:show_sum:`` flag does not support any values and it's useful with the ``stacked`` option  enabled.

.. need-example::

   .. needbar:: show_top_sum example 1
      :show_top_sum:

      5,20,15
      10,15,10
      15,10,20
      20,15,10

   .. needbar:: show_top_sum example 2
      :stacked:
      :show_sum:
      :show_top_sum:

      5,20,15
      10,15,10
      15,10,20
      20,15,10

horizontal
~~~~~~~~~~

You can render the bar chart with horizontal bars by setting the ``:horizontal:`` flag.

The ``:horizontal:`` flag does not support any values and it's useful with the ``stacked`` option  enabled.

.. hint::
   The meaning of `labels`_ will change automatically with the usage of ``:horizontal:``. We will use the
   ``:x_axis_title:`` as labels for the y-axis and use the ``:y_axis_title:`` as the values in the `legend`_.

.. need-example::

   .. needbar:: horizontal example 1
      :horizontal:

      5,20,15
      10,15,10
      15,10,20
      20,15,10

   .. needbar:: horizontal example 2
      :stacked:
      :legend:
      :show_sum:
      :horizontal:
      :xlabels: FROM_DATA
      :ylabels: FROM_DATA

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10

transpose
~~~~~~~~~

You can `transpose <https://en.wikipedia.org/wiki/Transpose>`_ the data in the content by setting the ``:transpose:`` flag.
The idea is, you can try to see the data from different point of view, without refactoring.

The ``:transpose:`` flag does not support any values and it's useful with big content tables.

.. hint::
   * Using the ``:transpose:`` flag, transposes the ``:x_axis_title:`` and ``:y_axis_title:`` fetched from the content data or specified with `labels`_ but does not transpose the extra `axis title`_.
   * Remember that with the ``:transpose:`` flag, the length and height of the content data changes, not to think about the width of matching elements, like `colors`_. Please review the impact of ``:transpose:`` before using it.

.. need-example::

   .. needbar:: transpose example 1
      :transpose:

      5,20,15
      10,15,10
      15,10,20
      20,15,10

   .. needbar:: transpose example 2
      :legend:
      :stacked:
      :show_sum:
      :transpose:
      :xlabels: FROM_DATA
      :ylabels: FROM_DATA

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


rotation
~~~~~~~~

| Use ``:xlabels_rotation:`` to set rotation of labels for x-axis on the diagram.
| Use ``:ylabels_rotation:`` to set rotation of labels for y-axis on the diagram.
| Use ``:sum_rotation:`` to set rotation of labels for bars on the diagram.


.. need-example::

   .. needbar:: rotation example
      :legend:
      :xlabels: a, b, c
      :xlabels_rotation: 90
      :ylabels: Z, Y, X, W
      :ylabels_rotation: 40
      :show_top_sum:
      :show_sum:
      :sum_rotation: 90

       5,20,15
      10,15,10
      15,10,20
      20,15,10

separator
~~~~~~~~~

You can specify a custom separator between the values in the content by setting the ``:separator:`` flag.
This ensures the use of ``,`` (the default separator) in a filter rule. Other options will be processed as defined there.

The ``:separator:`` is a string that supports any symbols.

.. need-example::

   .. needbar:: separator example
      :separator: -

      5-20-15
      10-15-10
      15-10-20
      20-15-10

colors
~~~~~~

``:colors:`` takes a comma separated list of color names and uses them for the bar charts.

See `Matplotlib documentation of supported colors <https://matplotlib.org/stable/gallery/color/named_colors.html>`_
for a complete list of color names.

But besides names, ``:colors:`` options also supports hex-values like ``#ffcc00``.

.. hint::
   In a normal bar chart, we use the ``:colors:`` for the legend and bars itself.
   When you use `horizontal`_ or `transpose`_, the bar's length must be equal to ``:xlabels:`` or ``:ylabels:``.
   If the length does not fit, it will fill the bar with the colors again and you will get a warning.

.. need-example::

   .. needbar:: colors example
      :legend:
      :colors: lightcoral, gold, #555555, #888888
      :xlabels: FROM_DATA
      :ylabels: FROM_DATA

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10

text_color
~~~~~~~~~~

``:text_color:`` defines the color for text inside the bar chart and the labels.

.. need-example::

   .. needbar:: text_color example
      :legend:
      :text_color: green
      :xlabels: FROM_DATA
      :ylabels: FROM_DATA

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10

style
~~~~~

``:style:`` activates a complete style (colors, font, sizes) for a bar chart.
It takes a string, which must match the
`supported Matplotlib style names <https://matplotlib.org/3.1.1/gallery/style_sheets/style_sheets_reference.html>`_.

Useful styles are for example:

* default
* classic
* Solarize_Light2
* dark_background
* grayscale

.. need-example::

   .. needbar:: style example
      :legend:
      :style: Solarize_Light2
      :xlabels: FROM_DATA
      :ylabels: FROM_DATA

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10
