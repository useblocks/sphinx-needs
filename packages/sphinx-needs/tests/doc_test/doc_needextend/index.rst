Need extend
===========

.. toctree::

   page_1
   page_2

.. story:: needextend Example 3
   :id: extend_test_003

   Had no outgoing links.
   Got an outgoing link ``extend_test_004``.

.. story:: needextend Example 4
   :id: extend_test_004

   Had no links.
   Got an incoming links ``extend_test_003`` and ``extend_test_006``.

.. story:: needextend Example 5
   :id: extend_test_005
   :links: extend_test_003, extend_test_004

   Had the two links: ``extend_test_003`` and ``extend_test_004``.
   Both got deleted.

.. story:: needextend Example 6
   :id: extend_test_006
   :links: extend_test_003

   Had the link ``extend_test_003``, got another one ``extend_test_004``.

.. story:: needextend Example 7
   :id: extend_test_007
   :links: extend_test_003


.. needextend:: extend_test_003
   :links: extend_test_004

.. needextend:: extend_test_005
   :-links:

.. needextend:: extend_test_006
   :+links: extend_test_004

.. needextend:: extend_test_006
   :+links: extend_test_004

.. needextend:: extend_test_007
   :+links: extend_test_004, extend_test_005