needextend unknown id
=====================

.. story:: needextend Example 3
   :id: extend_test_003

   Had no outgoing links.
   Got an outgoing link ``extend_test_004``.

.. story:: needextend Example 4
   :id: extend_test_004

   Had no links.
   Got an incoming links ``extend_test_003`` and ``extend_test_006``.

.. needextend:: extend_test_003
   :links: extend_test_004

.. needextend:: unknown_id
   :status: open
