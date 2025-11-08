
basic test
==========

.. feat:: feat wrong id
   :id: FEAt
   :asil: QM

.. feat:: feat
   :id: FEAT
   :asil: QM

.. feat:: feat safe
   :id: FEAT_SAFE
   :asil: C

.. feat:: feat safe 2
   :id: FEAT_SAFE2
   :asil: D

.. spec:: spec missing approval
   :id: SPEC_MISSING_APPROVAL
   :efforts: 20
   :priority: 1
   :asil: QM

.. spec:: spec
   :id: SPEC
   :efforts: 10
   :priority: 1
   :asil: QM

.. spec:: safe spec links unsafe feat
   :id: SPEC_SAFE_UNSAFE_FEAT
   :efforts: 20
   :priority: 1
   :asil: B
   :links: FEAT
   :approved: yes

.. spec:: safe spec additional items
   :id: SPEC_SAFE_ADD_UNSAFE_FEAT
   :efforts: 20
   :priority: 1
   :asil: B
   :links: FEAT, FEAT_SAFE2
   :approved: yes

.. spec:: safe spec
   :id: SPEC_SAFE
   :efforts: 20
   :priority: 1
   :asil: B
   :links: FEAT_SAFE, FEAT_SAFE2
   :approved: yes

.. impl:: impl
   :id: IMPL
   :efforts: 30
   :links: SPEC

.. impl:: safe impl
   :id: IMPL_SAFE
   :asil: A
   :links: SPEC_SAFE_UNSAFE_FEAT

.. impl:: Impl for array test
   :id: IMPL_ARRAY_TEST
   :departments: dep1, dep2, dep3
   :scores: 0.8, 0.9, 1_000.5
