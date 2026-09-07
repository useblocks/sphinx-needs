Need Delete Option
==================

.. req:: First Req Need
   :id: DELID123
   :delete: false

   Need with ``:delete:`` equal to ``false``.

   .. impl:: Not Implemented
      :id: DELID124
      :status: open
      :tags: user;del_need

      Need with ``:delete:`` option not set.

   .. spec:: Nested Spec Need
      :id: DELID125
      :status: open
      :tags: user;login
      :delete: true

      Nested need with ``:delete:`` option set to ``true``.

      .. impl:: Nested Implemented Need
         :id: DELID126
         :status: open
         :tags: user;login

         Nested need with ``:delete:`` option not set

.. spec:: First Spec Need
   :id: DELID123
   :status: open
   :delete: true

   Need with ``:delete:`` equal to ``true``.

.. spec:: Second Spec Need
   :id: DELID123
   :delete: true

   Need with ``:delete:`` equal to ``true``.

