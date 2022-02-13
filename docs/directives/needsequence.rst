.. _needsequence:

needsequence
============

.. versionadded:: 0.5.5

.. versionchanged:: nextversion

   PlantUML dependency (required for needsequence) now moved to optional extra.
   Install the extra via `pip install
   sphinxcontrib-needs[sphinxcontrib-plantuml]` or `sphinxcontrib-needs[all]` to
   enable support for this directive.


``needsequence`` adds a sequence-chart to your documentation::

    .. needsequence:: My sequence chart
       :start: USER_A, USER_D
       :link_types: links, triggers

.. needsequence:: My sequence chart
   :start: USER_A, USER_D
   :link_types: links, triggers

.. container:: toggle

    .. container::  header

        Show used needs for above example...

    .. user:: Mr. A
       :id: USER_A
       :links: ACT_ISSUE
       :style: blue_border

    .. action:: Creates issue
       :id: ACT_ISSUE
       :links: USER_B
       :style: yellow_border

    .. user:: Ms. B
       :id: USER_B
       :links: ACT_ANALYSIS, ACT_SOLUTION
       :style: blue_border

    .. action:: Analysis issue
       :id: ACT_ANALYSIS
       :links: USER_B
       :style: yellow_border

    .. action:: Provides solution
       :id: ACT_SOLUTION
       :links: USER_C
       :style: yellow_border

    .. user:: Expert C
       :id: USER_C
       :links: ACT_REVIEW, ACT_INFORM
       :style: blue_border

    .. action:: Reviews solution
       :id: ACT_REVIEW
       :links: USER_C
       :style: yellow_border

    .. action:: Informs reporter
       :id: ACT_INFORM
       :links: USER_A
       :style: yellow_border

    .. user:: Office Dog
       :id: USER_D
       :triggers: ACT_BARKS
       :style: blue_border

    .. action:: Barks for support
       :id: ACT_BARKS
       :triggers: USER_D
       :style: yellow_border

Sequence diagrams supports special needs-combinations, in which one type represents some kind of an ``participant``
and another, linked need is representing the ``message``.
Examples for this relationship are: Sender-Receiver communication , Role-Activity processes or Tool-Artifact relations.

``needsequence`` needs at least one start-need, defined by its ``id`` in the ``:start:`` option.
This need is the first ``participant``. The next, linked need(s) is representing the ``message``.
Needs linked from a ``message`` are interpreted as ``participant`` again and so on.
So the linking must be really clean to get nice, meaningful sequence diagrams out of it.

The used need-type itself is unimportant.

.. uml::
   :caption: Participant-Message flow
   :scale: 99%

   @startuml

   skinparam defaultTextAlignment center

   rectangle "Interpreted as\n**PARTICIPANT 1**\n(start)" as p1 #ccc
   rectangle "Interpreted as\n**PARTICIPANT 2**" as p2 #ccc
   rectangle "Interpreted as\n**PARTICIPANT 3**" as p3 #ccc


   rectangle "Interpreted as\n**MESSAGE 1**" as m1 #ffcc00
   rectangle "Interpreted as\n**MESSAGE1 **" as m2 #ffcc00

   p1 -> m1 : link
   m1 -> p2 : link
   p2 -> m2 : link
   m2 -> p3 : link
   @enduml

The above, linked example gets interpreted for ``needsequence`` as follows:

.. uml::

   @startuml

   participant "Participant 1\n (start)" as p1
   participant "Participant 2" as p2
   participant "Participant 3" as p3

   p1 -> p2: Message 1
   p2 -> p3: Message 2



   @enduml


Options
-------

.. contents::
   :local:

start
~~~~~

``start`` takes a comma separated list of need ids, which shall be used as starting point for
further examination for sequence data.

First need of ``start`` gets painted first. This includes all related messages and other participants.

After that the next need id is taken from ``start``. And if it was not already part of the prior
examination, it is handled the same way otherwise it is ignored.

link_types
~~~~~~~~~~

``link_types`` takes a comma separated list of link type names, which shall be followed
during examination. Other link_types get ignored and therefore all participants or messages, which
are accessible by the ignored linked type only.


Default: ``links``

filter
~~~~~~

The ``filter`` string is used to filter participants.
All participants must fulfil the filter_string, otherwise they get ignored.
See :ref:`filter_string` for more information.

Default: None (no active filtering)

This function can be used to filter out for instance a specific participant.
As example, same ``needsequence`` from the beginning, but without ``USER_C / Expert``::

    .. needsequence:: My filtered sequence chart
       :start: USER_A, USER_D
       :link_types: links, triggers
       :filter: "Expert" not in title

.. needsequence:: My filtered sequence chart
   :start: USER_A, USER_D
   :link_types: links, triggers
   :filter: "Expert" not in title
