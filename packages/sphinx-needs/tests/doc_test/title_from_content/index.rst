Tests for needs_title_from_content = True
=========================================

This document will test the various scenarios that can occur when
`needs_title_from_content` is set to `True`.

+-----------+------------------------+-----+-----------------------------------+ 
| Has Title | `:title_from_content:` | `id`| Expected Result                   |
+===========+========================+=====+===================================+
| Yes       |  Not Present           | Yes | title == argument, id = id        |
+-----------+------------------------+-----+-----------------------------------+
| Yes       |  Not Present           | No  | title == argument,id = hash title |
+-----------+------------------------+-----+-----------------------------------+
| Yes       |  Present               | Yes | title == argument, id = id, warn  |
+-----------+------------------------+-----+-----------------------------------+
| Yes       |  Present               | No  | title == argument,                |
|           |                        |     | id = hash title, warning issued   |
+-----------+------------------------+-----+-----------------------------------+
| No        |  Not Present           | Yes | title = first sentence, id = id   |
+-----------+------------------------+-----+-----------------------------------+
| No        |  Not Present           | No  | title = first sentence            |
|           |                        |     | id = hash title                   |
+-----------+------------------------+-----+-----------------------------------+
| No        |  Not Present           | No  | title = first sentence (elided)   |
|           |  First Sentence > max  |     | id = hash title                   |
+-----------+------------------------+-----+-----------------------------------+
| No        |  Not Present           | Yes | title = first sentence (elided)   |
|           |  First Sentence > max  |     | id = id                           |
+-----------+------------------------+-----+-----------------------------------+
| No        |  Present &             | Yes | title = first sentence, id = id   |
|           |  First Sentence <= max |     |                                   |
+-----------+------------------------+-----+-----------------------------------+
| No        |  Present &             | No  | title = first sentence,           |
|           |  First Sentence <= max |     | id = hash title                   |
+-----------+------------------------+-----+-----------------------------------+
| No        |  Present &             | Yes | title = first sentence (elided),  |
|           |  First Sentence > max  |     | id = id                           |
+-----------+------------------------+-----+-----------------------------------+ 
| No        |  Present &             | No  | title = first sentence (elided),  |
|           |  First Sentence > max  |     | id = hash title                   |
+-----------+------------------------+-----+-----------------------------------+


Section 1
---------

.. req:: Scenario 1 Title
    :id: R_12345

    This requirement's title and ID should match what was provided


.. req:: Scenario 2 Title

    This requirement's title should match what's above and have an ID generated


.. req:: Scenario 3 Title
    :title_from_content:
    :id: R_12346

    This requirement's title and ID should match above, and a warning should
    be issued


.. req:: Scenario 4 Title
    :title_from_content:

    This requirement should match the title above, generate an ID, and issue
    a warning


.. req::
    :id: R_12347

    Title is first sentence.  ID should match provided.


.. req::

    Title should be first sentence. ID should be generated.


.. req::

    First sentence will be title, but elided since it is long.
    ID should be generated.


.. req::
    :id: R_12348

    First sentence will be title, but elided since it is long.
    ID match provided


.. req::
    :title_from_content:
    :id: R_12349

    Title matches this.  The ID will match above


.. req::
    :title_from_content:

    Title should match this.  The ID should be generated.


.. req::
    :title_from_content:
    :id: R_12350

    First sentence is really long so this should be elided as title.  ID should
    match value above


.. req::
    :title_from_content:

    First sentence is really long so this should be elided as title.  ID should
    be generated


Standard Table
--------------

.. needtable::
    :columns: id;title

Standard List
-------------

.. needlist::


Need Flow
---------

.. needflow::
    :show_legend:

Table of Requirements with Titles
---------------------------------

.. needtable::
    :columns: id;title;content
    :filter: title