Targets
=======

.. req:: done
   :id: CHAIN_C
   :summary: [[copy('title')]]

.. req:: Chain middle
   :id: CHAIN_B
   :summary: [[copy('summary', need_id='CHAIN_C')]]

.. req:: Hours one
   :id: HRS_1
   :h0: 5
   :hours: [[copy('h0')]]

.. req:: Hours two
   :id: HRS_2
   :h0: 6
   :hours: [[copy('h0')]]

.. req:: Hours three
   :id: HRS_3
   :hours: 3

.. req:: Literal one
   :id: LIT_1
   :h0: 4
   :hours: 4

.. req:: Literal two
   :id: LIT_2
   :h0: 2
   :hours: 2

.. req:: Literal three
   :id: LIT_3
   :h0: 1
   :hours: 1

.. req:: done
   :id: WORK_1
   :status: [[copy('title')]]

.. req:: Work two
   :id: WORK_2
   :status: done

.. req:: Own copy
   :id: OWN_COPY
   :status: [[copy('comment')]]
   :comment: done

.. req:: Variant
   :id: VAR_B
   :band: <<[True]:yes, no>>
