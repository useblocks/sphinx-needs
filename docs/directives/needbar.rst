.. _needbar:

needbar
========

.. versionadded:: 0.7.5

``needbar`` adds a bar-chart to your documentation:

.. code-block:: rst

   .. needbar:: My bar chart

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10

.. needbar:: My bar chart

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10

Most of the examples are using the same static data, to show the functionality of the options.
So here is an more realistic example with data fetched from filters, together with hard coded data:

.. code-block:: rst

   .. needbar:: A more real bar chart
      :legend:

                   ,                           open ,                          in progress ,                          closed ,                          done ,                          implemented , number
        Requirement,  type=='req' and status=='open', type=='req' and status=='in progress', type=='req' and status=='closed', type=='req' and status=='done', type=='req' and status=='implemented', 5
               Test, type=='test' and status=='open',type=='test' and status=='in progress',type=='test' and status=='closed',type=='test' and status=='done',type=='test' and status=='implemented', 7
      Specification, type=='spec' and status=='open',type=='spec' and status=='in progress',type=='spec' and status=='closed',type=='spec' and status=='done',type=='spec' and status=='implemented', 9

.. needbar:: A more real bar chart
   :legend:

                ,                           open ,                          in progress ,                          closed ,                          done ,                          implemented , number
     Requirement,  type=='req' and status=='open', type=='req' and status=='in progress', type=='req' and status=='closed', type=='req' and status=='done', type=='req' and status=='implemented', 5
            Test, type=='test' and status=='open',type=='test' and status=='in progress',type=='test' and status=='closed',type=='test' and status=='done',type=='test' and status=='implemented', 7
   Specification, type=='spec' and status=='open',type=='spec' and status=='in progress',type=='spec' and status=='closed',type=='spec' and status=='done',type=='spec' and status=='implemented', 9


The argument of the ``needbar`` will be used as title for the bar.

Each content value gets interpreted either as static float/int value or as a :ref:`filter_string`.
The amount of found needs by the filter string is then used as value.

Options
-------

.. contents::
   :local:

Example with all options used:

.. needbar:: My full bar chart
   :legend:
   :colors: #ffcc88, #ffcc00, #444444
   :text_color: crimson
   :style: dark_background
   :x_axis_title: x_axis_title
   :xlabels_rotation: 90
   :xlabels: a, b, c
   :y_axis_title: y_axis_title
   :ylabels: Z, Y, X, W
   :ylabels_rotation: 45
   :separator: ;
   :stacked:
   :show_sum:
   :transpose:
   :horizontal:

    5;20;15
   10;15;10
   15;10;20
   20;15;10


.. code-block:: rst

   .. needbar:: My full bar chart
      :legend:
      :colors: #ffcc88, #ffcc00, #444444
      :text_color: crimson
      :style: dark_background
      :x_axis_title: x_axis_title
      :xlabels_rotation: 90
      :xlabels: a, b, c
      :y_axis_title: y_axis_title
      :ylabels: Z, Y, X, W
      :ylabels_rotation: 45
      :separator: ;
      :stacked:
      :show_sum:
      :transpose:
      :horizontal:

       5;20;15
      10;15;10
      15;10;20
      20;15;10


legend
~~~~~~

If ``:legend:`` is given, a legend will be placed in the bar chart.

``:legend:`` is a flag and does not support any values.


.. needbar:: Legend example
   :legend:

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10

.. code-block:: rst

   .. needbar:: Legend example
      :legend:

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


axis title
~~~~~~~~~~

If titles are given via ``:x_axis_title:`` or ``:y_axis_title:``, the axis get titles placed in the bar chart.

.. hint::
   If you use `horizontal`_ or `transpose`_, the meaning of ``:x_axis_title:`` and ``:y_axis_title:`` still have to old meaning.
   So you have to change the description accordingly.

.. needbar:: Axis title example
   :legend:
   :x_axis_title: types
   :y_axis_title: numbers

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10

.. code-block:: rst

   .. needbar:: Legend example
      :legend:
      :x_axis_title: types
      :y_axis_title: numbers

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


labels
~~~~~~

| Use ``:xlabels:`` to set labels for columns of the data.
| Use ``:ylabels:`` to set labels for row of the data.

``:xlabels:`` and/or ``:xlabels:`` must get a comma separated string and the amount of labels must match the amount of
values/lines from content.

.. hint::
   In a normal bar chart, the ``:xlabels:`` are used for the labels of the x-axis on the chart.
   The ``:ylabels:`` are used for the labels of legend.
   But if you use `horizontal`_ or `transpose`_, the meaning of ``:x_axis_title:`` and ``:y_axis_title:`` will automatically be changed.

.. needbar:: Labels example
   :legend:
   :xlabels: a, b, c
   :ylabels: Z, Y, X, W

    5,20,15
   10,15,10
   15,10,20
   20,15,10


.. code-block:: rst

   .. needbar:: Labels example
      :legend:
      :xlabels: a, b, c
      :ylabels: Z, Y, X, W

       5,20,15
      10,15,10
      15,10,20
      20,15,10


stacked
~~~~~~~

If ``:stacked:`` is given, the bar chart will be rendered in a stacked design.

``:stacked:`` is a flag and does not support any values.

.. needbar:: stacked example
   :legend:
   :stacked:

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10

.. code-block:: rst

   .. needbar:: stacked example
      :legend:
      :stacked:

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


show_sum
~~~~~~~~

If ``:show_sum:`` is given, the bar chart will be rendered with detailed information of the height of each bar.
Especially useful in ``stacked`` option.

``:show_sum:`` is a flag and does not support any values.

.. needbar:: show_sum example 1
   :legend:
   :show_sum:

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10

.. code-block:: rst

   .. needbar:: show_sum example 1
      :legend:
      :show_sum:

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


.. needbar:: show_sum example 2
   :legend:
   :stacked:
   :show_sum:

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10

.. code-block:: rst

   .. needbar:: show_sum example 2
      :legend:
      :stacked:
      :show_sum:

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


horizontal
~~~~~~~~~~

If ``:horizontal:`` is given, the bar chart will be rendered with horizontal bars.

``:horizontal:`` is a flag and does not support any values.

.. hint::
   The meaning of `labels`_ will be automatically change with the usage of ``:horizontal:``.
   ``:x_axis_title:`` or is now been used as labels for the y axis. ``:y_axis_title:`` is still the values in the `legend`_. 

.. needbar:: horizontal example 1
   :legend:
   :show_sum:
   :horizontal:

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10

.. code-block:: rst

   .. needbar:: horizontal example 1
      :legend:
      :show_sum:
      :horizontal:

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


.. needbar:: horizontal example 2
   :legend:
   :stacked:
   :show_sum:
   :horizontal:

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10

.. code-block:: rst

   .. needbar:: horizontal example 2
      :legend:
      :stacked:
      :show_sum:
      :horizontal:

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


transpose
~~~~~~~~~

If ``:transpose:`` is given, the data in the content are `transposed <https://en.wikipedia.org/wiki/Transpose>`_.
The idea is, you can try to see the data from different point of view, without refactoring.
Especially helpful with big content tables.

``:transpose:`` is a flag and does not support any values.

.. hint::
   ``:x_axis_title:`` and ``:y_axis_title:`` fetched from the content data or specified with `labels`_ are transposed, too. 
   But extra given `axis title`_ not.
   Please remember with transpose the length and height of the content data get changed,
   so think even about the length of matching elements, like `colors`_.
   So please review the impact of ``:transpose:``.

.. needbar:: transpose example 1
   :legend:
   :show_sum:
   :transpose:

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10

.. code-block:: rst

   .. needbar:: transpose example 1
      :legend:
      :show_sum:
      :transpose:

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


.. needbar:: transpose example 2
   :legend:
   :stacked:
   :show_sum:
   :transpose:

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10

.. code-block:: rst

   .. needbar:: transpose example 2
      :legend:
      :stacked:
      :show_sum:
      :transpose:

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


rotation
~~~~~~~~

| Use ``:xlabels_rotation:`` to set rotation of labels for x-axis on the diagram.
| Use ``:ylabels_rotation:`` to set rotation of labels for y-axis on the diagram.

.. needbar:: rotation example
   :legend:
   :xlabels: a, b, c
   :xlabels_rotation: 90
   :ylabels: Z, Y, X, W
   :ylabels_rotation: 40

    5,20,15
   10,15,10
   15,10,20
   20,15,10


.. code-block:: rst

   .. needbar:: rotation example
      :legend:
      :xlabels: a, b, c
      :xlabels_rotation: 90
      :ylabels: Z, Y, X, W
      :ylabels_rotation: 40

       5,20,15
      10,15,10
      15,10,20
      20,15,10


separator
~~~~~~~~~

With ``:separator:`` a customized separator between the values in the data of the content can be specified.
Idea is to overcome possible use of ``,`` in a filter rule. 

``:separator:`` is a string and support any symbols.

.. needbar:: separator example
   :legend:
   :separator: ;

    ;  a; b; c
   Z;  5;20;15
   Y; 10;15;10
   X; 15;10;20
   W; 20;15;10

.. code-block:: rst

   .. needbar:: separator example
      :legend:
      :separator: ;

       ;  a; b; c
      Z;  5;20;15
      Y; 10;15;10
      X; 15;10;20
      W; 20;15;10


colors
~~~~~~

``:colors:`` takes a comma separated list of color names and uses them for the bar charts.

See `Matplotlib documentation of supported colors <https://matplotlib.org/stable/gallery/color/named_colors.html>`_
for a complete list of color names.

But beside names also hex-values like ``#ffcc00`` are supported.

.. hint::
   In a normal bar chart, the ``:colors:`` are used for the legend and bars itself.
   So depending on horizontal or transpose, the length have to be same to ``:xlabels:`` or ``:ylabels:``.
   If the length does not fit, it will be filled with the colors again and you will get a warning.

.. needbar:: colors example
   :legend:
   :colors: lightcoral, gold, #555555, #888888

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10


.. code-block:: rst

   .. needbar:: colors example
      :legend:
      :colors: lightcoral, gold, #555555, #888888

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10


text_color
~~~~~~~~~~

``:text_color:`` defines the color for text inside the bar chart and the labels.

.. needbar:: text_color example
   :legend:
   :text_color: green

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10


.. code-block:: rst

   .. needbar:: text_color example
      :legend:
      text_color: green

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

.. needbar:: style example
   :legend:
   :style: Solarize_Light2

    , a, b, c
   Z, 5,20,15
   Y,10,15,10
   X,15,10,20
   W,20,15,10


.. code-block:: rst

   .. needbar:: style example
      :legend:
      :style: Solarize_Light2

       , a, b, c
      Z, 5,20,15
      Y,10,15,10
      X,15,10,20
      W,20,15,10

