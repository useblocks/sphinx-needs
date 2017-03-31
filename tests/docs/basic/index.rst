.. needs test docs documentation master file, created by
   sphinx-quickstart on Tue Mar 28 11:37:14 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to needs test docs's documentation!
===========================================

.. spec:: Test my spec
   :id: OwN_iD
   :status: open
   :tags: test; req; awesome
   :links: OWN_IMPL_ID;
   :hide_status:
   :hide_tags:

   It's a *spec*.

   An awesome spec with line breaks.

   Uhh another line break. Awesome!

.. impl:: my Implementation
   :id: OWN_IMPL_ID
   :status: open
   :links: OWN_ID;r_F69E6

   It's an implementation.

.. test:: My greate test case
   :status: closed
   :links: OWN_ID; R_F69E6;OWN_IMPL_ID

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   req


NEEDFILTER
==========

.. needfilter::
   :show_status:
   :show_tags:
   :show_filters:
   :sort_by: id

NEEDFILTER 2
============

.. needfilter::
   :status: open

NEEDFILTER 3
============

.. needfilter::
   :status: open
   :tags: test
   :show_status:
   :show_tags:
   :show_filters:
   :sort_by: id

NEEDFILTER 4 (types)
====================

.. needfilter::
   :types: req;test
   :show_status:
   :show_tags:
   :show_filters:
   :sort_by: id

NEEDFILTER 5 (types)
====================

.. needfilter::
   :types: spec;impl
   :show_status:
   :show_tags:
   :show_filters:
   :sort_by: id


NEEDFILTER TABLE
================

.. needfilter::
   :layout: table

NEEDFILTER DIAGRAM
==================

.. needfilter::
   :layout: diagram

NEEDFILTER DIAGRAM
==================

.. needfilter::
   :layout: diagram
   :show_legend:



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
