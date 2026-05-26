Variant Data Test
=================

.. req:: ARM Requirement
   :id: REQ_001
   :platform: arm

.. req:: x86 Requirement
   :id: REQ_002
   :platform: x86

.. req:: Any Requirement
   :id: REQ_003

Needtable filtered by variant data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. needtable:: ARM Needs
   :filter: var.platform == platform
   :style: table

Needlist filtered by variant data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. needlist::
   :filter: "arm" in var.archs

Needcount using variant data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Debug mode needs: :need_count:`var.build.debug == True`
