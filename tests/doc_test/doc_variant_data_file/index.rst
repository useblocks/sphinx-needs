Variant Data File Test
======================

.. req:: Staging Requirement
   :id: REQ_STAGING

.. req:: Production Requirement
   :id: REQ_PROD

Filtered by overridden env (inline overrides file)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. needtable:: Staging Needs
   :filter: var.env == "staging"
   :style: table

File-only field still accessible
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. needtable:: US East Needs
   :filter: var.region == "us-east"
   :style: table
