.. _open_needs_service:

Open-Needs services
===================

Example
-------
**Code**

.. code-block:: rst

   .. needservice:: open-needs
      :prefix: ONS_
      :params: skip=0;limit=10

   .. needtable::
      :filter: "ONS" in id

**Result**

{% if on_ci != true %}

.. needservice:: open-needs
   :prefix: ONS_
   :params: skip=0;limit=10

.. needtable::
   :filter: "ONS" in id
   :columns: id, title, status, type
   :style: table

{% else %}
.. hint::

   The below examples are just images, as no Open-Needs Server instance was available during documentation build.

.. image:: /_images/ons_example.png
   :align: center
   :width: 60%

.. image:: /_images/ons_table.png
   :align: center
   :width: 60%

{% endif %}