Performance testing
===================

Config
------
:dummies: {{dummies}}
:needs: {{needs}}
:needtables: {{needtables}}
:keep: {{keep}}
:browser: {{browser}}
:debug: {{debug}}

Content
-------
.. contents::


Test Data
---------

Dummies
~~~~~~~
Amount of dummies: **{{dummies}}**

{% for n in range(dummies) %}
**Dummy {{n}}**

.. note::  This is dummy {{n}}

And some **dummy** *text* for dummy {{n}}

{% endfor %}

Needs
~~~~~
Amount of needs: **{{needs}}**

{% for n in range(needs) %}
.. story:: Test Need {{n}}
   :id: S_{{n}}
   :number: {{n}}
   :links: S_{{needs-n-1}}
{% endfor %}

Needtable
~~~~~~~~~
Amount of needtables: **{{needtables}}**

{% for n in range(needtables) %}
.. needtable::
   :show_filters:
   :filter: int(number) % {{n+1}} >= {{n}}
   :columns: id, title, number, links
{% endfor %}
