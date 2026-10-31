Views
=====

.. needtable::
   :columns: id, title, linked

.. needlist::

.. needextract::
   :filter: id == 'SPEC_1'

.. needflow::
   :engine: graphviz

.. needflow::
   :engine: plantuml

.. needpie::

   type == 'req'
   type == 'spec'

.. needbar::
   :xlabels: FROM_DATA
   :ylabels: FROM_DATA

   ,a,b
   x,type == 'req',type == 'spec'

.. needgantt::
   :filter: id == 'SPEC_1'

.. needsequence::
   :start: SPEC_1

.. needreport::
   :types:
   :links:
   :options:

.. if:: var.arch == "arm"

   .. req:: Only on arm
      :id: REQ_ARM

.. choose::

   .. when:: var.arch == "x86"

      x86 content.

   .. otherwise::

      .. req:: Otherwise
         :id: REQ_OTHER
