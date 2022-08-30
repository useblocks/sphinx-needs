Need Jinja Content Option
=========================

.. req:: First Req Need
   :id: JINJAID123
   :jinja_content: false

   Need with ``:jinja_content:`` equal to ``false``.

   .. impl:: Jinja Content Not Implemented
      :id: JINJAID124
      :status: open
      :tags: user

      Need with ``:jinja_content:`` option not set.

   .. spec:: Nested Spec Need
      :id: JINJAID125
      :status: open
      :tags: user;login
      :links: JINJAID126
      :jinja_content: true

      Nested need with ``:jinja_content:`` option set to ``true``.
      This requirement has tags: **{{ tags | join(', ') }}**.

      It links to:
      {% for link in links %}
      - {{ link }}
      {% endfor %}


.. spec:: First Spec Need
   :id: JINJAID126
   :status: open
   :jinja_content: true

   Need with ``:jinja_content:`` equal to ``true``.
   This requirement has status: **{{ status }}**.
