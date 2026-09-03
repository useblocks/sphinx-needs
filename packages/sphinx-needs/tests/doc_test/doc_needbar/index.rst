TEST DOCUMENT Needbar
=====================

.. req:: Req 1
    :id: REQ_1
    :tags: a

.. req:: Req 2
    :id: REQ_2
    :tags: b

.. req:: Req 3
    :id: REQ_3
    :tags: b

.. spec:: Spec 1
    :id: SPEC_1
    :tags: a

.. spec:: Spec 2
    :id: SPEC_2
    :tags: a

.. spec:: Spec 3
    :id: SPEC_3
    :tags: b

.. needbar:: Bar Title
    :legend:
    :xlabels: FROM_DATA
    :ylabels: FROM_DATA

         , A                           , B
    Req  , type=='req' and 'a' in tags , type=='req' and 'a' in tags
    Spec , type=='spec' and 'b' in tags, type=='spec' and 'b' in tags
