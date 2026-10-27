.. _incremental_builds:

Incremental builds
==================

On an incremental build, Sphinx re-reads the documents whose sources changed, and writes those.
A page can also show needs from other documents, though,
so when a need changes, Sphinx-Needs has Sphinx re-write (not re-read) every page that shows it:

- every page holding a view: a :ref:`needtable`, ``needlist``, :ref:`needflow`, ``needgantt``,
  ``needsequence``, ``needpie``, ``needbar``, ``needextract``, ``needuml`` or ``needarch``, ``needreport``,
  or a ``:need_count:`` or ``:ndf:`` role,
  since which needs a filter selects is only known once the page is written;
- the pages of the needs that changed, and of those a changed :ref:`needextend` names by its id;
- the pages of the needs computing a value from them:
  every need with a :ref:`dynamic function <dynamic_functions>`, whose arguments may name any need,
  and every need whose :ref:`derive rule <needs_derive>` reads one of them
  (over its links or its back links, or ``from`` it), and so on along the chain;
  a rule reading needs it does not name (a ``join``, a ``transitive`` one) counts on every change;
- the pages of the needs they link to, which show them as back links, before and after the change;
- the pages of the needs linking to them, which show them as links;
- the pages whose :ref:`need roles <role_need>` (``:need:``, ``:need_incoming:``, ``:need_outgoing:``) name any of these.

A need *changes* when anything the document gives it changes: a field, a link, its content,
and also its line number, so adding lines above a need in its document counts as a change of that need.
An edit that changes no need, such as a paragraph of prose, re-writes no other page.

Some changes can affect needs that are only known once the needs are resolved:
a changed ``needextend`` with a filter rather than an id,
a ``needextend`` adding links with a dynamic function,
and a need whose links are computed to needs it does not name
(a dynamic function in a link field, a ``links`` derive rule, or a ``content_links`` rule with ``from``).
After such a change, every page that holds a need, a view or a need role is re-written.

Needs loaded with :ref:`needs_external_needs` are not compared:
after the external ``needs.json`` changes, build with ``-E`` to bring the pages showing its needs up to date.
