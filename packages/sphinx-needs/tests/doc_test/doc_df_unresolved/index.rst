.. ubCode's build fixture ``dynamic_functions_unresolved``
   (``rust/ubc_parser_ctrl/tests/build_fixtures/``), its pages verbatim as on ubCode's
   main branch at 47ceb2f; ``ubproject.toml`` says what differs. The text below describes
   ubCode's phase 0, whose ``needs.derive_unresolved`` findings neither tool gives any
   more; ubCode's phase-1 change rewrites it, and this copy is to be re-synced once that
   change is merged. ``test_ubcode_fixture`` asserts what the dependency-ordered pass
   gives: the chained values, the cycle, and the one ``need.<attr>`` selector.

A derivation that reads a value not resolved yet
================================================

Every need on this page carries a ``[[…]]`` or a ``<<…>>`` that reads a value
which another call evaluates in the same resolution pass, so it reads the value stored before resolution
(the field's empty value, or only the literal part of a list),
and ``needs.derive_unresolved`` (Info) names the read:
one finding per reader per call, never one per summand.
On a ubCode that does not report ``needs.derive_unresolved`` this fixture is red by design:
nothing is reported there, so its ``diagnostics`` and ``needs`` snapshots differ.
The call-carrying targets are on ``targets.rst``; the patches edit that page and
``extends.rst`` only, so no reader here is re-resolved because its own item moved.

Each reader, and what it is red for:

- ``CHAIN_A`` reads ``CHAIN_B``, which reads ``CHAIN_C`` (a chain ``A ← B ← C``, positional and keyword ``need_id``):
  a finding on ``CHAIN_A`` and on ``CHAIN_B``, none on ``CHAIN_C``, whose ``title`` is authored.
  Red if a cross-need ``copy`` does not note its read.
- ``SAME_NEED``: ``status ← comment ← title`` on one need: a finding on ``status`` only.
  Red if an own-field ``copy`` does not note its read.
- ``SUM_ALL`` and ``SUM_ALL2``: two carriers of ``calc_sum('hours')`` (two spellings, one memoised column):
  one finding each, naming every call-carrying summand of the column by count.
  ``SUM_ALL2`` is red if only the carrier that computed the column's total is told what it read.
- ``SUM_LINKS``: ``calc_sum('hours', links_only=True)`` over ``HRS_1`` (a call) and ``HRS_3`` (authored):
  names ``HRS_1`` only. Red if a ``links_only`` sum does not note its reads.
- ``OWN_LINKS``: ``calc_sum('hours', links_only=True)`` over its OWN ``links``, which mix the authored ``HRS_3``
  and a call: the sum sees ``HRS_3`` only, and the finding names ``links`` on ``OWN_LINKS``.
  Red if a ``links_only`` sum does not note its own link list.
- ``GATE_1``: ``check_linked_values`` reading ``WORK_1``'s ``status``, a call.
  Red if ``check_linked_values`` does not note its reads.
- ``CYC_A`` and ``CYC_B`` read each other: two findings (the cycle finding is phase 1).
- ``VAR_COND``: a variant condition naming ``f1``, which a call on the same need computes.
  Red if a variant condition does not note its reads.
- ``MIRROR_VAR`` reads ``VAR_B``'s ``band``, which a variant computes: a variant is a computed value too.
- ``MIRROR_LIT`` reads ``LIT_1``'s ``hours``, authored until patch ``01`` makes it a call:
  red if the finding rests on anything but the target's calls as they are now.
- ``NEED_ATTR``: ``copy('summary', need.parent)`` whose ``parent`` is a call: the finding explains the
  ``needs.dynamic_function`` warning beside it (``copy() found no need with id ''``).
  Red if a ``need.<attr>`` argument does not note its read, or if a failing call drops its finding.

Patches: ``01`` a literal becomes a call (``LIT_1.hours``), ``02`` an own field becomes a call
(``OWN_COPY.comment``, read by ``OWN_COPY``'s own ``status``), ``03`` an extend sets a summand to a call
(``LIT_2.hours``), ``04`` a call becomes a literal (``HRS_2.hours``), ``05`` an extend that set a call is
removed (``LIT_3``), ``06`` a call's text changes and the field stays a call (``CHAIN_B``: no finding moves).
No patch adds or removes a need.

Nothing is recorded at a post-resolution surface (an ``:ndf:`` role, a needtable ``:style_row:``), where every value
is final: an in-need role and a ``:style_row:`` build their context through ``with_df_context``, which records nothing
(a document-scope role builds none); the tier predicate is fenced by ``a_post_resolution_read_records_nothing``;
this build oracle does not hydrate pages, so ``ubc build html`` of such a project was checked by hand instead.

.. toctree::

   targets
   extends

.. req:: Chain start
   :id: CHAIN_A
   :summary: [[copy('summary', 'CHAIN_B')]]

.. req:: The title
   :id: SAME_NEED
   :status: [[copy('comment')]]
   :comment: [[copy('title')]]

.. req:: Every need's hours
   :id: SUM_ALL
   :total: [[calc_sum('hours')]]

.. req:: Every need's hours, double-quoted
   :id: SUM_ALL2
   :total: [[calc_sum("hours")]]

.. req:: The linked hours
   :id: SUM_LINKS
   :links: HRS_1, HRS_3
   :total: [[calc_sum('hours', links_only=True)]]

.. req:: Gate
   :id: GATE_1
   :links: WORK_1, WORK_2
   :summary: [[check_linked_values('ready', 'status', 'done')]]

.. req:: Cycle, first half
   :id: CYC_A
   :summary: [[copy('summary', 'CYC_B')]]

.. req:: Cycle, second half
   :id: CYC_B
   :summary: [[copy('summary', 'CYC_A')]]

.. req:: T
   :id: VAR_COND
   :f1: [[copy('title')]]
   :band: <<[f1 == "T"]:matched, unmatched>>

.. req:: Reads a variant
   :id: MIRROR_VAR
   :summary: [[copy('band', 'VAR_B')]]

.. req:: Reads an authored value, until a patch makes it a call
   :id: MIRROR_LIT
   :total: [[copy('hours', 'LIT_1')]]

.. req:: Reads through a need attribute that is a call
   :id: NEED_ATTR
   :comment: HRS_3
   :parent: [[copy('comment')]]
   :summary: [[copy('summary', need.parent)]]

.. req:: Sums over its own links, which carry a call
   :id: OWN_LINKS
   :parent: LIT_1
   :links: HRS_3, [[copy('parent')]]
   :total: [[calc_sum('hours', links_only=True)]]
