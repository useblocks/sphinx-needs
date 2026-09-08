A TABLE WIDER THAN THE PAGE
===========================

Ten columns of unbreakable text, so the table cannot fit the content column at any
ordinary window width and the scroll frame has something to scroll.

.. req:: Averyveryverylongunbreakabletitlewordforthescrollframetest
   :id: W_01
   :status: unbreakablestatusvaluethatcannotwrap
   :tags: unbreakabletagvaluethatcannotwrap
   :amount: 1
   :due: 2024-01-01

.. req:: Asecondveryverylongunbreakabletitlewordforthescrollframetest
   :id: W_02
   :status: anotherunbreakablestatusvaluehere
   :tags: anotherunbreakabletagvaluehere
   :links: W_01
   :amount: 2
   :due: 2024-02-02

.. needtable::
   :columns: id;title;status;amount;due;outgoing;incoming;tags;type;docname
   :filter: is_need and docname == "wide"
