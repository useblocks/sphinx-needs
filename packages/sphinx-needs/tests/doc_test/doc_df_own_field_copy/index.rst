Own-field copy
==============

The point of this fixture is the ``copy`` the incremental widening EXEMPTS:
``copy('<field>')``, one string literal and nothing else, reads only the need it is
written on, so a warm build re-resolves it when that need, or a needextend on it,
changes — never because another need did. Each own-field reader below is reached
through its own seed (``OWN_EXTENDED`` through an edited needextend, ``OWN_MOVED``
through a moved line: its integer ``line`` goes from 4 to 6), and ``OWN_BESIDE`` sits
beside an edited need without being re-resolved at all; the oracle proves the seeds were enough.

``MIRROR_POS`` is the counter-row: the same call with a second positional argument
reads another need, so it must still widen, and it fails the oracle the day the
exemption admits a second argument.

``BACKLINK`` copies its own backlinks into an ARRAY field. No need links to it on the cold build,
so the call reads ``Null``; patch ``01`` links ``WORK_1`` to it, and the warm build reads ``WORK_1``:
a change no edit of ``BACKLINK`` made, so the widening must reach it — which the ``_back`` rule does —
and the oracle sees it if it does not.

.. toctree::

   moved
   extends

.. req:: Own field beside an edited need
   :id: OWN_BESIDE
   :status: open
   :summary: [[copy('status')]]

.. req:: Own field set by a needextend
   :id: OWN_EXTENDED
   :summary: [[copy('status')]]

.. req:: Reads another need positionally
   :id: MIRROR_POS
   :summary: [[copy('status', 'WORK_1')]]

.. req:: Copies a backlink
   :id: BACKLINK
   :incoming: [[copy('links_back')]]

.. req:: Work
   :id: WORK_1
   :status: open
