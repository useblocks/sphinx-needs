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
- the pages of the needs computing a value from them, and so on along the chain.
  What a computed value reads is decided from what is written, and only a shape known here is read narrowly;
  anything else -- a variant (``<<…>>``), a function of your own, a filter that names ``needs``,
  a kind of rule or call not listed below -- is taken to read every need,
  so it errs toward re-writing a page, never toward leaving one stale:

  - a :ref:`dynamic function <dynamic_functions>`, written in the need or set on it by a needextend by id,
    is read by its arguments: ``copy`` of the need's own field reads no other need,
    ``copy`` with a need id reads that need,
    and ``check_linked_values`` and a ``calc_sum`` with ``links_only`` read the needs it links to;
    a back-link field (``<link type>_back``) is written by the needs linking to the need it is read on,
    so ``copy("links_back")`` reads the needs linking to its own need, and with a need id, those linking to that need;
    the other fields the needs decide when they are resolved -- ``has_dead_links``, ``has_forbidden_dead_links``,
    the constraint results, ``modifications`` and ``is_modified``, ``parts`` -- are taken to read every need
    wherever they are read, by a call, a rule or a filter;
    any other call (a function of your own, a ``filter`` argument, ``copy`` whose need id is a ``need.<field>``)
    may read any need, so its need counts as changed on every change;
  - a :ref:`derive rule <needs_derive>` reads the needs it links to (``over`` a link type,
    including the links a needextend adds), those linking to it (``over`` a ``<link type>_back``),
    or the need ``from`` names, back links read as above;
    a ``where`` narrowing those needs (beside a ``copy`` too) reads them alone, unless it names a back link
    or reads ``needs``, and ``c.is_a(...)`` in it reads their type and the need types' ``inherits``;
    a rule reading needs it does not name (a ``join``, a ``transitive`` rule, a ``where`` of ``content_links``)
    counts on every change;

- the pages of the needs they link to, which show them as back links, before and after the change,
  including the links a needextend adds or no longer adds;
- the pages of the needs linking to them, which show them as links, including through a needextend;
- the pages whose :ref:`need roles <role_need>` (``:need:``, ``:need_incoming:``, ``:need_outgoing:``) name any of these.

A need *changes* when anything the document gives it changes: a field, a link, its content.
A need that only *moved* -- lines added or removed above it in its document, so that only its line numbers
(``lineno``, ``lineno_content``) differ -- re-writes the views and the pages whose need roles name it,
either of which may show a line number (a needtable column, a role's text or :ref:`needs_role_need_template`),
but only when nothing else in the project can read one:
no computed value (a call, a variant, a derive rule, on a need or set by a needextend) that names a line number
or may read any field, no needextend filter, link condition or constraint naming one, and no layout naming one.
If anything might, a moved need counts as changed and the rules above apply.
An edit that changes no need, such as a paragraph of prose below the needs, re-writes no other page.

Some needs are only known once the needs are resolved.
In a project that has any of the following, every change of a need re-writes every page that holds a need,
a view or a need role:

- a needextend adding links with a dynamic function;
- a need whose links are computed to needs it does not name
  (a dynamic function in a link field, a ``links`` derive rule, a ``content_links`` rule with ``from``,
  a ``collect`` on a link type, which links a chain's far ends, or a ``copy`` on a link type over a link type
  a rule computes, see :ref:`needs_derive_link_chain`);
- a needextend with a filter that sets a value with a dynamic function reading needs it does not name.

The same happens after a change of a needextend with a filter rather than an id,
and after a change of a need that a needextend with a filter links to (``:+links:``)
or whose value its dynamic function copies (``copy`` with a need id).

A change of the need types -- :ref:`needs_types`, or the ``[needs.types]`` of ``ubproject.toml``,
including an ``inherits`` (which ``c.is_a(...)`` follows, see :ref:`filter_is_a`),
the fields and links a type declares, and its ``id_regex`` -- re-reads every document,
and so re-writes every page.
What the schema reports of a need, a type's count of the links it receives (:ref:`need_types_incoming`)
and a declaration's ``severity`` included, is checked over every need on every build, incremental or not,
so a link removed on one page is reported for the need it pointed to though that need's page is not re-read.

Needs loaded with :ref:`needs_external_needs` are not compared:
after the external ``needs.json`` changes, build with ``-E`` to bring the pages showing its needs up to date.
