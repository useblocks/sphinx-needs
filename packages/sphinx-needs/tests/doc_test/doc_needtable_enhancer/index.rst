NEEDTABLE ENHANCER
==================

Twelve needs, sorted by id, so that the default page size of ten puts ``S_02`` and
``S_03`` on the second page.

.. req:: Alpha requirement
   :id: R_01
   :status: open
   :tags: alpha
   :amount: 100
   :due: 2025-11-30

.. req:: Beta requirement
   :id: R_02
   :status: closed
   :tags: beta
   :amount: 10
   :due: 2024-01-15

.. req:: Gamma requirement
   :id: R_03
   :status: open
   :amount: 2
   :due: 2023-06-02

.. req:: Delta requirement
   :id: R_04
   :status: closed
   :amount: 25

.. req:: Epsilon requirement
   :id: R_05
   :status: open
   :amount: 7
   :due: 2026-02-28

.. req:: Zeta requirement
   :id: R_06
   :status: closed
   :amount: 3
   :due: 2022-12-31

.. req:: Eta requirement
   :id: R_07
   :status: open
   :amount: 42
   :due: 2025-01-01

.. req:: Theta requirement
   :id: R_08
   :status: closed
   :amount: 8
   :due: 2024-07-04

.. req:: Iota requirement
   :id: R_09
   :status: open
   :amount: 15
   :due: 2023-03-09

.. spec:: Kappa specification
   :id: S_01
   :status: open
   :links: R_01
   :amount: 1
   :due: 2021-05-05

.. spec:: Comma, and "quotes" in a title
   :id: S_02
   :status: closed
   :links: R_02, R_03
   :amount: 4
   :due: 2020-10-10

   Contains :np:`(P1) zebracrossing alpha` and :np:`(P2) zebracrossing beta`.

.. spec:: Omega specification
   :id: S_03
   :status: open
   :links: R_09

The interactive table
---------------------

.. needtable:: Every column
   :columns: id;title;status;amount;due;outgoing
   :colwidths: 15,35,10,10,15,15
   :style_row: needs_[[copy('status')]]
   :filter: is_need
   :show_parts:
   :show_filters:

The small interactive table
---------------------------

Three rows, so its pager has a single page and must be hidden.

.. needtable:: Specifications only
   :columns: id;title;status
   :types: spec

The plain table
---------------

.. needtable:: Plain
   :style: table
   :columns: id;title
   :types: spec
