TEST DOCUMENT NEEDUML
=====================

.. req:: Test req 1
   :id: REQ_1
   :duration: 5

   Some content

.. req:: Message
   :id: REQ_2
   :duration: 3
   :links: REQ_1

   Some content

.. req:: Test req 3
   :id: REQ_3
   :duration: 3
   :links: REQ_2

   Some content

.. needuml::
   :scale: 50%
   :align: center
   :config: mixing

   class "{{needs['REQ_1'].title}}" {
   }

.. needflow::

.. needgantt::

.. needsequence::
   :start: REQ_1, REQ_3
   :link_types: links
