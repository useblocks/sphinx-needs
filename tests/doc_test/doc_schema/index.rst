
basic test
==========

.. feat:: feat wrong id
   :id: FEAt
   :asil: QM

.. feat:: feat
   :id: FEAT
   :asil: QM

.. feat:: feat
   :id: FEAT_SAFE
   :asil: C

.. feat:: feat
   :id: FEAT_SAFE2
   :asil: D

.. req:: req missing approval
   :id: REQ_MISSING_APPROVAL
   :efforts: 20
   :priority: 1
   :asil: QM

.. req:: req
   :id: REQ
   :efforts: 10
   :priority: 1
   :asil: QM

.. req:: safe req links unsafe feat
   :id: REQ_SAFE_UNSAFE_FEAT
   :efforts: 20
   :priority: 1
   :asil: B
   :links: FEAT, FEAT_SAFE2
   :approved: yes

.. req:: safe req
   :id: REQ_SAFE
   :efforts: 20
   :priority: 1
   :asil: B
   :links: FEAT_SAFE, FEAT_SAFE2
   :approved: yes

.. spec:: spec 1
   :id: SPEC
   :efforts: 30
   :links: REQ

.. spec:: safe spec 2
   :id: SPEC_SAFE
   :asil: A
   :links: REQ_SAFE_UNSAFE_FEAT
