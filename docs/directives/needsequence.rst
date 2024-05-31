.. _needsequence:

needsequence
============

.. versionadded:: 0.5.5

``needsequence`` adds a sequence-chart to your documentation.

.. need-example::

    .. needsequence:: My sequence chart
       :start: USER_A, USER_D
       :link_types: links, triggers

.. dropdown:: Show the needs used in the above example

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

Sequence diagrams supports special needs-combinations, in which one type represents some kind of a ``participant``
and another, linked need is representing the ``message``. |br|
Examples for this relationship are: Sender-Receiver communication , Role-Activity processes or Tool-Artifact relations.

``needsequence`` needs at least one start-need, defined by its ``id`` in the ``:start:`` option.

The first need represents the ``participant``. The next, linked need(s) is representing the ``message``.
Needs linked from a ``message`` are interpreted as ``participant`` again and so on. |br|
So the linking must be really clean to get nice, meaningful sequence diagrams out of it.

The used need-type is unimportant.

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

start
~~~~~

The ``:start:`` option takes a comma separated list of need ids and uses it as the starting point for
further examination of sequence data.

First need of ``:start:`` gets painted first. The need includes all related messages and other participants.

After the first need, we take the next need id from the ``:start:`` option.
And if it was not already part of the prior examination, we handle it the same way, otherwise, we ignore it.

link_types
~~~~~~~~~~

``:link_types:`` option takes a comma separated list of link type names followed during examination. |br|
Because of that, we ignore other link_types and all participants or messages accessible by the ignored link_types.

Default: ``links``

filter
~~~~~~

You can use the ``:filter:`` option to filter participants.
We ignore all participants that does not fulfill the filter_string.
See :ref:`filter_string` for more information.

Default: None (no active filtering)

You can use this function to filter out a specific participant.
As an example, we use the same ``needsequence`` from the beginning, but without ``USER_C / Expert``:

.. need-example::

    .. needsequence:: My filtered sequence chart
       :start: USER_A, USER_D
       :link_types: links, triggers
       :filter: "Expert" not in title
