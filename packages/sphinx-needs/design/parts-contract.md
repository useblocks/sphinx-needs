# Need parts

A part is a named, addressable piece of ONE need: an id, a text, and the links that point at
it. It has no fields, no type of its own, no lifecycle and no outgoing links; anything that
needs one of those is a child need. Where a need is expected, a part address reads as its need.

This page states what a part is and how it is addressed. Its executable half is
`tests/fixtures/parts_conformance.toml`, run by `tests/test_parts_conformance.py`; this
repository is its repository of record, and ubCode is to vendor it. Each section below
names the corpus section that pins it. The user's documentation is the `need_part` section
of `docs/roles.rst`. The findings named here (`duplicate part id`, `part outside a need`,
`dead link`, `link target type`, `link condition`) are classes of this contract: each tool
reports them under codes of its own, which the corpus header maps.

## 1. The role and its grammar (corpus: `grammar`)

`:need_part:` and its short name `:np:` mark a part in a need's content. Their text is read
as `(id) text`: an opening parenthesis at its very start, an id, a closing parenthesis, and
the rest.

- **The id** is one or more characters, each a Unicode letter or digit (what Python's
  `str.isalnum` accepts), `_` or `-`. Case is kept; nothing else is an id character, so a
  space, a `.`, a `:` or a `(` inside the parentheses means the text has no id.
- **The text** is everything after the closing parenthesis, exactly as the markup gives the
  role's content: a leading space is kept (`(p1) first` has the text ` first`), the text may
  be empty, and it may span lines, keeping its line breaks without the continuation lines'
  indentation. It is never read as a reference: `(p3) see <target>` has the text
  ` see <target>`.
- **No id.** When the text does not start with `(id)` -- no parenthesis, a character before
  it (`!(p4) text`), or a character that is not an id character -- the part's id is the
  first three hexadecimal digits, upper case, of the SHA-1 of the role's whole text as the
  markup gives it (after backslash escapes are removed) encoded as UTF-8, and its text is
  that whole text.

## 2. Which need a part belongs to (corpus: `placement`, `stated`)

A part belongs to the innermost need whose content holds the role: a part written inside a
nested need is the nested need's, never the outer one's. Content is the need's wherever it
comes from: its directive's body in reStructuredText or MyST, a file it includes, a list
item of `list2need`, the body of a multi-line need in source code, or the body of a test
case. A role outside every need is one finding, `part outside a need`, and makes no part.

An external need, whose content is not part of this project, has the parts its record
states, each with the id and the text the record gives.

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
need has.

With namespaced ids, the namespace is split from the need's id only after the part is
split off, and a namespace segment holds no `.`: the grammar of a need id, section 14 of
`packages/ub-needs-exchange/design/exchange-contract.md`, is not restated here. So
`SUP01::REQ_1.p1` is the part `p1` of the need `SUP01::REQ_1`, with namespaced ids on or off.

## 6. A link to a part (corpus: `links`)

- It is **live** when the need exists and has the part, and **dead** otherwise, whether the
  need or only the part is missing: a dead link is one finding, `dead link`, which names the
  address as written, its condition taken off.
- Its **condition** is read on the need, not on the part: `REQ_1.p1[id == "REQ_1"]` holds,
  and a condition that does not hold is one finding, `link condition`.
- The need's type decides it against a link type's **target types**: a part has no type of
  its own, and a link to a need of a type not allowed is one finding, `link target type`.
- It **counts for the need**: it is one of the need's back links, live or dead, and, when
  live, one of the part's. A part's back links hold only links naming that part; a link to
  the need alone, or to another of its parts, is not one of them.
- A prefix given to the ids of imported needs prefixes the need's id of a part link and
  keeps its part.

## 7. What a part answers in a filter that asks for parts (corpus: `answers`)

A filter that asks for parts tests the parts beside the needs. A part answers its own `id`
(the part id), `id_complete` (`ID.part`), `id_parent` (its need's id), `is_part` (true) and
`is_need` (false), its text as `content`, no links out (every link type is empty), and its
own back links (`<link type>_back`). Every other name it answers is its need's: the need's
type, status and fields, and the id facets (`c.id.ns`, `c.id.local`, `c.in_namespace()`)
included. A part's `title` is not settled here (section 9).

## 8. Through a part to its need (corpus: `derived`)

Where a need is expected, a part address reads as its need: a derived field or a function
that follows a link through a part reads the need's values, and a count over back links
counts a part link as a link to the need. The corpus pins this for links, and pins each
other place a need id is given as that place comes to follow it.

## 9. Not settled here

This page is silent on these on purpose; each waits on a ruling of its own.

- The order of a need's parts.
- Parts a need states that its content does not mark.
- Which parts an imported need gets when its record and its content give different parts.
- Whether a filter, a view or a count that does not ask for parts selects them.
- How a view draws a part.
- What a part's `title` is in a filter.
- A need id that holds a `.`.
- How a part is written in `needs.json` format 2.
- Parts in a graph query schema.
