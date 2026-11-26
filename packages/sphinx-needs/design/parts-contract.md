# Need parts

A part is a named, addressable piece of ONE need: an id, a text, and the links that point at
it. It has no fields, no type of its own, no lifecycle and no outgoing links; anything that
needs one of those is a need of its own: it is not a piece of a sentence, it has its own
id, and a link to it does not count for a need it is nested in. Where a need is expected,
a part address reads as its need.

This page states what a part is and how it is addressed. Its executable half is
`tests/fixtures/parts_conformance.toml`, run by `tests/test_parts_conformance.py`; this
repository is its repository of record, and ubCode is to vendor it. Each section below
names the corpus section that pins it. The user's documentation is the `need_part` section
of `docs/roles.rst`. The findings named here (`duplicate part id`, `part outside a need`,
`dead link`, `link target type`, `link condition`, `unresolved reference`,
`unknown part key`) are classes of this contract: each tool reports them under codes of its
own, which the corpus header maps.

## 1. The role and its grammar (corpus: `grammar`)

`:need_part:` and its short name `:np:` mark a part in a need's content. Their text, once
the markup's backslash escapes are removed, is read as `(id) text`: an opening parenthesis
at its very start, an id, a closing parenthesis, and the rest.

- **The id** is one or more characters, each a letter or a number by its Unicode general
  category (L or N, in the Unicode version of the tool that reads it), `_` or `-`. A
  combining mark (general category M) is no id character: a decomposed `é` (`e` followed by
  U+0301) or a letter with a vowel sign means the text has no id. Case is kept; nothing else
  is an id character, so a space, a `.`, a `:` or a `(` inside the parentheses means the text
  has no id.
- **The text** is everything after the closing parenthesis, as the markup gives the role's
  content, with the white space at both of its ends removed: `(p1) first`, `(p1)first` and
  `(p1)` followed by a line break and `first` all have the text `first`, and MyST's
  `` {np}`(p1) first ` `` has it too. White space is exactly the 25 code points of Unicode's
  `White_Space` property: U+0009 to U+000D, U+0020, U+0085, U+00A0, U+1680, U+2000 to
  U+200A, U+2028, U+2029, U+202F, U+205F and U+3000 (not U+001C to U+001F, which Python's
  `str.strip()` would also remove). The text may be empty, and it may span lines, keeping
  the white space and line breaks inside it, without the continuation lines' indentation.
  It is never read as a reference: `(p3) see <target>` has the text `see <target>`.
- **No id.** When the text does not start with `(id)` -- no parenthesis, a character before
  it (`!(p4) text`), or a character that is not an id character -- the part's id is the
  first three hexadecimal digits, upper case, of the SHA-1 of that whole text encoded as
  UTF-8, and its text is that whole text, as written: nothing is removed from its ends.

## 2. Which need a part belongs to (corpus: `placement`, `stated`)

A part belongs to the innermost need whose content holds the role, whatever directive made
each need: a part written inside a nested need is the nested need's, never the outer one's,
a test case nested in a requirement as much as a requirement nested in a test case. Content
is the need's wherever it comes from: its directive's body in reStructuredText or MyST, a
file it includes, a list item of `list2need`, the body of a multi-line need in source code,
or the body of a test file, a test suite or a test case; the needs a test file's options
expand have no body, and so no parts. A role outside every need is one finding,
`part outside a need`, and makes no part.

A need may have parts its content does not mark, stated by the record or the caller that
gives the need: each has its key in the given parts as its id (a record part's own `id` is
not read) and its text as given, but for one rule: a need whose content is read takes a
stated text on one line, each run of white space that holds a line break being one space
(U+0020). A run is a maximal run of characters of Unicode's `White_Space` property; a line
break is one of the `White_Space` characters Unicode's line breaking algorithm (UAX #14)
makes a mandatory break: LF (U+000A), VT (U+000B), FF (U+000C), CR (U+000D), NEL (U+0085),
LS (U+2028) and PS (U+2029). A run holding no line break, and every other character, is
kept. Section 1's removal of white space is the role's, and a stated text keeps its ends (an
end that is a run holding a line break is one space). A need whose content is read has the
parts its content marks and the stated parts whose id its content does not mark; where both
give an id, the content's part is the part, with its text, and there is no finding. A part
id is one word: a stated part whose id holds white space (a character of Unicode's
`White_Space` property) or a control character (one of the general category `Cc`) is not
taken by a need whose content is read, and there is no finding. An external need, whose
content is not part of this project, has its stated parts, their texts as given. A stated
part's back links are this project's: those a record gives it are not read. A record part's
key the format does not define, any but `id`, `content` and the back links of a link type
the project has, is one finding for the need, `unknown part key`, however many of its parts
hold one. It is a finding about the record, made for every part the record states: also for
one the need does not take, and for one whose id the content marks. Such a key costs no
part. A prefix or a namespace given to the ids of imported needs changes the need's id,
never a part's.

## 3. One id, one part (corpus: `duplicates`)

A need has at most one part of an id. When its content marks an id twice, the first is the
part, its text the first's, and the need gets one finding, `duplicate part id`, for each
repetition; this holds on every route content takes to a need.

## 4. A hidden need has its parts (corpus: `placement`)

Hiding a need changes how it is shown, not what it is: a hidden need has the parts its
content marks, and a link to one of them is live.

## 5. The address (corpus: `addressing`, `stated`)

A link or a reference names a part as `ID.part`, optionally followed by a condition,
`ID.part[condition]`. The condition is taken off first; the rest is split at its FIRST `.`:
the text before it is the need's id, the text after it the part's id. So a part id may hold
a `.` (a record may state one), `EXT_1.a.b` naming the part `a.b` of `EXT_1`, and a `.` in
a condition is never a separator. An address ending in `.` names the empty part, which no
need has. The first `.` always separates: a need whose id holds a `.` cannot be the target
of a link or of a reference.

With namespaced ids, the namespace is split from the need's id only after the part is
split off, and a namespace segment holds no `.`: the grammar of a need id, section 14 of
`packages/ub-needs-exchange/design/exchange-contract.md`, is not restated here. So
`SUP01::REQ_1.p1` is the part `p1` of the need `SUP01::REQ_1`, with namespaced ids on or off.

A stated part (section 2) has the address `NEED.part` like any other; where its need is on
a page, that address is an anchor beside the need's content. A reference naming a part its
need does not have, or a need that does not exist, is one finding, `unresolved reference`.

## 6. A link to a part (corpus: `links`)

- It is **live** when the need exists and has the part, and **dead** otherwise, whether the
  need or only the part is missing: a dead link is one finding, `dead link`, which names the
  address as written, its condition taken off.
- Its **condition** is read on the need, not on the part: `REQ_1.p1[id == "REQ_1"]` holds,
  and a condition that does not hold is one finding, `link condition`.
- The need's type decides it against a link type's **target types**: a part has no type of
  its own, and a link to a need of a type not allowed is one finding, `link target type`.
  A schema's **network rule** validates the need too, as it validates a link to the need.
- It **counts for the need**: it is one of the need's back links, live or dead, and, when
  live, one of the part's. A part's back links hold only links naming that part; a link to
  the need alone, or to another of its parts, is not one of them.
- A prefix given to the ids of imported needs prefixes the need's id of a part link and
  keeps its part.

## 7. What a part answers in a filter that asks for parts (corpus: `answers`)

A filter that asks for parts tests the parts beside the needs. A part answers its own `id`
(the part id), `id_complete` (`ID.part`), `id_parent` (its need's id), `is_part` (true) and
`is_need` (false), its text as `content` and as `title`, no links out (every link type is
empty), and its own back links (`<link type>_back`). Every other name it answers is its
need's: the need's type, status and fields, and the id facets (`c.id.ns`, `c.id.local`,
`c.in_namespace()`) included. A part answers the same where a `links` rule's `where` or
`join`, `links_from_filter` or `links_from_match` asks for parts (the corpus pins its
`title` there, in `derived`).

## 8. Through a part to its need (corpus: `derived`)

Where a need is expected, a part address reads as its need: a derived field or a function
that follows a link through a part reads the need's values, and a count over back links
counts a part link as a link to the need. The corpus pins this for links, and pins each
other place a need id is given as that place comes to follow it. A derived field's rule
`from` (`copy` and `content_links`) and the `need_id` of `links_from_content` follow it:
given a part address they read the part's need, `content_links` the need's whole content,
not the part's text; `tests/fixtures/derive_conformance.toml` pins them. There as
elsewhere, a part the need does not have names nothing, as an id naming no need does.

Two places that take a need id ask which needs link to it, and given a part address they
answer for the part: `:need_incoming:` lists the part's back links, and a needflow
`:root_id:` naming a part takes its first incoming step through them. Every other place
answers for the part's need, also where it reads a back-link field by name: `copy` of a
`<link type>_back` field copies the need's. No warning is given, and a write still
refuses.

## 9. What a view selects (corpus: `selection`)

A view's filter is tested on the needs of the project, and on their parts where the
project says so: `views_include_parts` in the `[needs]` table of `ubproject.toml`
(`needs_views_include_parts` in `conf.py`). A view is a needtable, a needlist, a needflow
or a needgantt; a needpie's lines and a needbar's cells, and the scope of either; and
`:need_count:`. Its filter is its `:filter:` and its `:status:`, `:tags:` and `:types:`,
filter code and a filter function.

- **True**: every need and every part is a candidate, and a part that passes is an item of
  the view of its own: a row, a line, a node, an element, a count of one.
- **False**: only needs are candidates. A part is not selected, `is_part` selects
  nothing, and `id_parent == "X"` selects the need `X` alone, a need answering its own id
  as `id_parent`. A part is shown only where the view asks for it: a needtable's
  `:show_parts:` lists the parts of each need it lists, each once, under it.

Every other filter is no view, and the value does not reach it: a filter that asks for
parts (section 7), a derived field's rule, a function, a `needextend`, a warning check.
A project that does not write the value gets its tool's default: Sphinx-Needs reads it
as true through its 9.x series and as false from 10.0. A tool may select needs alone
whatever the value says; the corpus marks where one does.

## 10. The order of a need's parts (corpus: `stated`)

A need's parts are in order: the parts its content marks, in the order written (the first
role of each id), then its stated parts whose id its content does not mark, in the order
given. The stored need keeps that order, and in sphinx-needs so do the places that list a
need's parts from it: the block of stated parts, needextract, a needtable's `:show_parts:`
rows, needlist and needflow. Two do not: a needtable whose filter selects parts sorts them as
it sorts its rows, and `links_from_match` and a derived join take them in part-id order. The
`needs.json` Sphinx-Needs writes (format 1) lists a need's parts sorted by id and cannot
carry the order, so the corpus reads it from the stored need (`order.<ID>`).

## 11. What a view lists and draws (corpus: `views`)

A needtable with `:show_parts:` lists each part of a need it lists once, under the need,
in the need's stored order (section 10). A part's row lists the part's address, its id
linking the part's anchor. For an external need's part: where the need's URL's fragment,
the text after its `#`, is the need's id, whole or without the `id_prefix` of one of the
project's external sources, the part's link is that URL with `.<part>` added; otherwise it
is the need's URL. Its other cells are its need's fields, no outgoing link (a part has none), and the
part's own back links. A cell naming a part links the part's anchor; a dead part link is
its address, as text.

A needflow that draws needs alone (`views_include_parts` false) draws a link to a part of
a need it draws as an edge to that need. The links of one need, of one link type, naming
parts of one need are ONE edge, labelled with the ids of those parts: bare, in the need's
stored order, each once, joined `, `. A link naming the need whole stays its own edge,
unlabelled; each link type draws its own edge; a link to a part the need does not have, to
a part of a need that does not exist, or to a part of a need the needflow does not draw is
no edge and names no part. A need's link to its own part is an edge from the need to
itself. Where the needflow labels its edges with the link type's name, the edge to the
need has one label of two lines: the name, then the part ids. Sphinx-Needs draws the edge
in the link type's `style_part`.

How a needflow draws a need's parts inside the need is not on this page yet.

## 12. Not on this page yet

These are decided but not yet built in both tools; each joins this page and the corpus
with the change that builds it. Two are open: whether a need id that holds a `.` is
warned on or refused, and parts in a graph query schema.

- How a needflow draws a need's parts inside the need.
- A need id that holds a `.`.
- How a part is written in `needs.json` format 2.
- Parts in a graph query schema.
