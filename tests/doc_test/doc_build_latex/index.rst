TEST DOCUMENT BUILD LATEXPDF
============================

.. raw:: latex

    \listoftables
    \listoffigures


Story
-----

.. story:: A Story
   :id: USER_STORY_001

   This is a user defined custom story.

Figure and Table
----------------

Example figure created:

.. needflow:: Example Figure
   :filter: id in ['USER_STORY_001']


Table generated by Sphinx.

.. list-table:: Table from Sphinx 'list-table' directive
   :widths: 25 25
   :header-rows: 1

   * - Header A
     - Header B
   * - Apple
     - 10
   * - Banana
     - 20

.. table:: Table from Sphinx 'table' directive
   :widths: auto

   =====  =====
     A      B
   =====  =====
   True   False
   =====  =====

Table generated by sphinxcontrib-needs:

.. needtable:: Table from sphinxneeds-contrib 'needtable' directive
    :filter: id in ['USER_STORY_001']
