TEST Parts
===========

.. spec:: Test need with need parts
   :id: table_001

   :np:`(1) Part 1 of requirement`.

   :np:`(2) Part 2 of requirement`.

   :np:`(3) Part 3 of requirement`.

.. spec:: Specifies part 1
   :id: table_002
   :links: table_001.1

.. spec:: Specifies part 2
   :id: table_003
   :links: table_001.2

.. needtable::
   :filter: is_need
   :show_parts:
   :columns: id;title;outgoing;incoming
   :style: table
