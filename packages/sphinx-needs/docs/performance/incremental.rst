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
- the pages of the needs computing a value from them, and so on along the chain:

  - a :ref:`dynamic function <dynamic_functions>`, written in the need or set on it by a needextend by id,
    is read by its arguments: ``copy`` of the need's own field reads no other need,
    ``copy`` with a need id reads that need,
    and ``check_linked_values`` and a ``calc_sum`` with ``links_only`` read the needs it links to;
    any other call (a function of your own, a ``filter`` argument) may read any need,
    so its need counts as changed on every change;
  - a :ref:`derive rule <needs_derive>` reads the needs it links to (``over`` a link type,
    including the links a needextend adds), those linking to it (``over`` a ``<link type>_back``),
    or the need ``from`` names;
    a rule reading needs it does not name (a ``join``, a ``transitive`` rule, a ``where`` of ``content_links``)
    counts on every change;

- the pages of the needs they link to, which show them as back links, before and after the change,
  including the links a needextend adds or no longer adds;
- the pages of the needs linking to them, which show them as links, including through a needextend;
- the pages whose :ref:`need roles <role_need>` (``:need:``, ``:need_incoming:``, ``:need_outgoing:``) name any of these.

A need *changes* when anything the document gives it changes: a field, a link, its content.
A need that only *moved* -- lines added or removed above it in its document, so that only its line numbers differ --
re-writes the views alone, as a view is the one place a line number shows.
An edit that changes no need, such as a paragraph of prose below the needs, re-writes no other page.

Some needs are only known once the needs are resolved.
In a project that has any of the following, every change of a need re-writes every page that holds a need,
a view or a need role:

- a needextend adding links with a dynamic function;
- a need whose links are computed to needs it does not name
  (a dynamic function in a link field, a ``links`` derive rule, or a ``content_links`` rule with ``from``);
- a needextend with a filter that sets a value with a dynamic function reading needs it does not name.

The same happens after a change of a needextend with a filter rather than an id,
and after a change of a need that a needextend with a filter links to (``:+links:``)
or whose value its dynamic function copies (``copy`` with a need id).

Needs loaded with :ref:`needs_external_needs` are not compared:
after the external ``needs.json`` changes, build with ``-E`` to bring the pages showing its needs up to date.
