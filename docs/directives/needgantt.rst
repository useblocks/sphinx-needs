.. _needgantt:

needgantt
=========

.. versionadded:: 0.5.5

``needgantt`` adds a gantt-chart to your documentation.

.. need-example::

    .. needgantt:: Bug handling gantt
       :tags: gantt_example
       :milestone_filter: type == 'milestone'

.. dropdown:: Show used needs for above example

    .. action:: Find & Report bug
       :id: ACT_BUG
       :tags: gantt_example
       :duration: 5

    .. action:: Analyse bug
       :id: ACT_BUG_ANALYSE
       :tags: gantt_example
       :links: ACT_BUG
       :duration: 7

    .. action:: Create solution ticket
       :id: ACT_TICKET
       :tags: gantt_example
       :links: ACT_BUG_ANALYSE
       :duration: 3

    .. action:: Work on solution ticket
       :id: ACT_TICKET_WORK
       :tags: gantt_example
       :links:  ACT_TICKET
       :duration: 7

    .. milestone:: Solution ticket closed
       :id: MS_TICKET_CLOSED
       :tags: gantt_example
       :links:  ACT_TICKET_WORK

    .. action:: Add solution to release plan
       :id: ACT_RELEASE_PLAN
       :tags: gantt_example
       :links:  MS_TICKET_CLOSED
       :duration: 1

    .. action:: Deploy release
       :id: ACT_DEPLOY
       :tags: gantt_example
       :links: ACT_RELEASE_PLAN
       :duration: 2

    .. action:: Test release
       :id: ACT_TEST
       :tags: gantt_example
       :links: ACT_DEPLOY
       :duration: 12
       :completion: 80

    .. milestone:: Bug solved
       :id: MS_BUG_SOLVED
       :tags: gantt_example
       :links: ACT_TEST

.. hint::

   The Gantt function is quite new in `PlantUML <https://plantuml.com/gantt-diagram>`__ and some features are
   available in the `Beta version <http://beta.plantuml.net/plantuml.jar>`__ only.
   So if you get any syntax errors during the build, please download the
   `latest PlantUML <http://sourceforge.net/projects/plantuml/files/plantuml.jar/download>`__ version.

If ``svg`` is set as output format for PlantUML, we link the tasks elements to their related need.

We take the colors for the chart from the :ref:`needs_types` configuration.
You can deactivate this behavior by setting :ref:`needgantt_no_color`.

``needgantt`` supports the following relationship between tasks and milestones:

* **starts with**: see :ref:`needgantt_starts_with_links`
* **starts after**: see :ref:`needgantt_starts_after_links`
* **ends with**: see :ref:`needgantt_ends_with_links`

By default, the need-option :ref:`need_duration` defines the task length.
We interpret the value in days.

By default, the need-option :ref:`need_completion` defines the task completion.
We interpret the value as percentage and should be between 0 and 100.

Options
-------

.. _needgantt_milestone_filter:

milestone_filter
~~~~~~~~~~~~~~~~

We execute the ``milestone_filter`` on each need found by ``filter`` or any user related filter option.
If it is a match, we represent the need as a milestone instead of a task in gantt chart.

``milestone_filter`` must be a valid :ref:`filter_string`.

.. _needgantt_starts_with_links:

starts_with_links
~~~~~~~~~~~~~~~~~

List of link names used to define task relationship, ``starts_with``.

Default: None

.. need-example::

   .. needgantt:: Starts_with example
      :tags: gantt_ex_starts_with
      :starts_with_links: starts_with

.. dropdown:: Show used needs for above example

    .. action:: Create example
       :id: ACT_CREATE_EX_SW
       :tags: gantt_ex_starts_with
       :duration: 12

    .. action:: Read example
       :id: ACT_READ_EX_SW
       :tags: gantt_ex_starts_with
       :links: ACT_CREATE_EX_SW
       :duration: 8

    .. action:: Understand example
       :id: ACT_UNDERSTAND_EX_SW
       :tags: gantt_ex_starts_with
       :starts_with: ACT_READ_EX_SW
       :duration: 12

.. _needgantt_starts_after_links:

starts_after_links
~~~~~~~~~~~~~~~~~~

List of link names used to define task relationship, ``starts_after``.

Default: links

.. need-example::

   .. needgantt:: Starts_after example
      :tags: gantt_ex_starts_after
      :starts_after_links: starts_after

.. dropdown:: Show the needs used in the above example

    .. action:: Create example
       :id: ACT_CREATE_EX_SA
       :tags: gantt_ex_starts_after
       :duration: 12

    .. action:: Read example
       :id: ACT_READ_EX_SA
       :tags: gantt_ex_starts_after
       :starts_after: ACT_CREATE_EX_SA
       :duration: 8

.. _needgantt_ends_with_links:

ends_with_links
~~~~~~~~~~~~~~~

List of link names used to define task relationship, ``ends_with``.

Default: None

.. need-example::

   .. needgantt:: Ends_with example
      :tags: gantt_ex_ends_with
      :ends_with_links: ends_with

.. dropdown:: Show the needs used in the above example

    .. action:: Create example
       :id: ACT_CREATE_EX_EW
       :tags: gantt_ex_ends_with
       :duration: 12

    .. action:: Read example
       :id: ACT_READ_EX_EW
       :tags: gantt_ex_ends_with
       :ends_with: ACT_CREATE_EX_EW
       :duration: 8

.. _needgantt_start_date:

start_date
~~~~~~~~~~~

Optional start date for the gantt chart.
We calculate all tasks and milestones dates based on the ``:start_date:`` option's value.

Date format must be ``YYYY-MM-DD``. Example: 2020-03-25

.. need-example::

   .. needgantt:: Bug handling gantt
      :tags: gantt_example
      :milestone_filter: type == 'milestone'
      :start_date: 2020-03-25

.. _needgantt_timeline:

timeline
~~~~~~~~

Defines the timeline scale.

Allowed values: ``daily``, ``weekly``, ``monthly``.

Default: ``daily``

Works only, if you set :ref:`needgantt_start_date` option.

.. need-example::

   .. needgantt:: Bug handling gantt
      :tags: gantt_example
      :milestone_filter: type == 'milestone'
      :start_date: 2020-03-25
      :timeline: weekly

.. _needgantt_no_color:

no_color
~~~~~~~~

We derive the tasks and milestone color from the need-type configuration,
else we use the default PlantUML colors.

.. needgantt:: Bug handling gantt
   :tags: gantt_example
   :milestone_filter: type == 'milestone'
   :no_color:

.. _needgantt_duration_option:

duration_option
~~~~~~~~~~~~~~~

Defines the option to use as the duration value.
We interpret the value in days, no matter what the name of the option is.

You can set the duration option globally by using :ref:`needs_duration_option` in **conf.py**.

Default: :ref:`need_duration`

.. need-example::

   .. needgantt:: Duration example
      :tags: gantt_ex_duration
      :duration_option: hours

.. dropdown:: Show the needs used in the above example

    .. action:: Create example
       :id: ACT_CREATE_EX
       :tags: gantt_ex_duration
       :hours: 12

    .. action:: Read example
       :id: ACT_READ_EX
       :tags: gantt_ex_duration
       :links: ACT_CREATE_EX
       :hours: 3
       :duration: 100


       ``duration`` option gets ignored in the above ``needgantt``.


.. _needgantt_completion_option:

completion_option
~~~~~~~~~~~~~~~~~

Defines the option to use as the completion value.
We interpret the value in percentage.

You can set the completion option globally by using :ref:`needs_completion_option` in **conf.py**.

Default: :ref:`need_completion`

.. need-example::

   .. needgantt:: Completion example
      :tags: gantt_ex_completion
      :completion_option: amount

.. dropdown:: Show the needs used in the above example

    .. action:: Create example
       :id: ACT_CREATE_EX_C
       :tags: gantt_ex_completion
       :duration: 12
       :amount: 90


    .. action:: Read example
       :id: ACT_READ_EX_C
       :tags: gantt_ex_completion
       :links: ACT_CREATE_EX_C
       :duration: 12
       :amount: 40


common filters
~~~~~~~~~~~~~~

* :ref:`option_status`
* :ref:`option_tags`
* :ref:`option_types`
* :ref:`option_filter`
