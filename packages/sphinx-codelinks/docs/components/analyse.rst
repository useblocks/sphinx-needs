.. _analyse:

Source Analyse
==============

The **Source Analyse** module is a powerful component of **Sphinx-CodeLinks** that extracts documentation-related content from source code comments. It provides both CLI and API interfaces for flexible integration into documentation workflows.

**Key Capabilities:**

- Extract **Sphinx-Needs** ID references from source code comments
- Process custom one-line comment patterns for rapid documentation
- Extract multi-line needs: a need's fields and its body written across the lines of a comment
- Generate structured JSON output for further processing
- Support for multiple programming language comment styles

Overview
--------

Source Analyse works by parsing source code files and identifying specially marked comments that contain documentation information. This enables developers to embed documentation directly in their source code while maintaining clean separation between code and documentation.

The module supports three primary extraction modes:

1. **Sphinx-Needs ID References** - Links between code and requirements/specifications
2. **One-line Needs** - Simplified syntax for creating documentation needs
3. **Multi-line Needs** - A need's fields and its body, in reStructuredText or Markdown, written across the lines of a comment

Supported Content Types
-----------------------

Sphinx-Needs ID References
~~~~~~~~~~~~~~~~~~~~~~~~~~

Extract references to **Sphinx-Needs** items directly from source code comments, enabling traceability between code implementations and requirements.

One-line Needs
~~~~~~~~~~~~~~

Use simplified comment patterns to define **Sphinx-Needs** items without complex RST syntax. See :ref:`OneLineCommentStyle <oneline>` for detailed information.

Multi-line Needs
~~~~~~~~~~~~~~~~

Write a whole need in a comment -- its type, title and options, and a body in reStructuredText or Markdown -- between an ``@need`` line and an ``@endneed`` line. See :ref:`multiline_needs`.

Limitations
-----------

**Current Limitations:**

- **Language Support**: C/C++ (``//``, ``/* */``), C# (``//``, ``/* */``, ``///``), TypeScript/JavaScript (``//``, ``/* */``, and the legacy one-line ``<!--``), Python (``#``), YAML (``#``), Rust (``//``, ``/* */``, ``///``), Go (``//``, ``/* */``), JSONC (``//``, ``/* */``), Bash (``#``), PowerShell (``#``, ``<# #>``), VHDL (``--``, ``/* */``) and Swift (``//``, ``/* */``, ``///``, ``/** */``) comment styles are supported
- **Single Comment Style**: Each analysis run processes only one comment style at a time
- **UTF-8 Only**: A source file is read as UTF-8, by both engines. A file that is not UTF-8 (saved as Latin-1 or
  UTF-16, for example), or that holds a NUL byte in its first 2048 bytes and so is taken for a binary file, is
  skipped with a warning naming it and the position and line of the first byte that stops it:
  ``/project/src/x.cpp:3: WARNING: codelinks: skipping /project/src/x.cpp — not UTF-8 (invalid continuation byte):
  byte 0xe9 at position 3046, line 3; save the file as UTF-8 to trace it [codelinks.not_text]``. Every other file keeps its
  needs. ``suppress_warnings = ["codelinks.not_text"]`` silences it; ``codelinks analyse`` prints it too.

.. _attachment:

Which code a marker is attached to
----------------------------------

Every marker -- a one-line need, a multi-line need (by the comment holding its open line) or an ``@need-ids:``
reference -- is attached to at most one **code entity**: a function, a method, a class, a namespace, a module.
The analysis records it in two forms: ``tagged_scope``, the entity's full text, and ``scope``, the entity named:

.. code-block:: json

   "scope": {
       "kind": "function_definition", "start": 33, "end": 37, "language": "cpp",
       "entity_kind": "method", "qualified_name": "ns::Widget::draw",
       "semantic": [
           {"kind": "namespace", "name": "ns"},
           {"kind": "class", "name": "Widget"},
           {"kind": "method", "name": "draw"}
       ],
       "mechanism": "leading"
   }

- ``kind`` -- the syntax node of the entity (tree-sitter's name for it);
- ``start`` and ``end`` -- its first and last line, 1-based, as the grammar spans the definition: a Rust attribute, a
  Python decorator, a decorator on a TypeScript class member and a C++ template header above it are not part of it; a
  C# attribute list, a C++ attribute and a decorator on a TypeScript class are (unless the class is exported: then the
  decorator is the export's);
- ``language`` -- the file's language, by its name, as editors' language identifiers spell it.
  The project's ``comment_type`` gives the language family and the grammar,
  and the suffix picks ``c`` among C and C++ and ``javascript`` among the ``ts`` type's files:

  .. list-table::
     :header-rows: 1
     :widths: 20 80

     * - ``language``
       - Files
     * - ``c``
       - A ``.c`` file. The suffix is compared as written: a ``.C`` file, which compilers read as C++, is ``cpp``.
     * - ``cpp``
       - Every other C and C++ file: ``.cpp``, ``.cc``, ``.cxx``, ``.hpp``, ``.hh``, ``.hxx``, ``.h``, ``.ci``,
         ``.ihl`` and ``.C``.
         A ``.h`` header is ``cpp``: its name does not say whether it is C or C++, and it is analysed as C++.
     * - ``csharp``
       - ``.cs``
     * - ``typescript``
       - ``.ts``, ``.mts``, ``.cts`` and ``.tsx``, and every other file of the ``ts`` comment type that is not
         JavaScript.
     * - ``javascript``
       - ``.js``, ``.mjs``, ``.cjs`` and ``.jsx``, the suffix compared in any case.
     * - ``python``
       - ``.py``
     * - ``rust``
       - ``.rs``
     * - ``go``
       - ``.go``
     * - ``yaml``
       - ``.yaml`` and ``.yml``
     * - ``jsonc``
       - ``.jsonc``, and a ``.json`` file that opens with a comment: JSON with comments.
     * - ``bash``
       - Every shell file the bash grammar reads: ``.sh``, ``.bash``, ``.zsh`` and ``.ksh``.
     * - ``powershell``
       - ``.ps1``, ``.psm1`` and ``.psd1``
     * - ``vhdl``
       - ``.vhd`` and ``.vhdl``
     * - ``swift``
       - ``.swift``

  One language is one name, so the value groups files that editors may tell apart:
  a ``.h`` header is ``cpp`` whether C or C++ includes it,
  a TSX file is ``typescript`` and a JSX file ``javascript``,
  the whole shell family is ``bash`` (the one value editors spell otherwise, as ``shellscript``),
  and a ``.json`` file with comments is ``jsonc``.
  Beyond ``.c`` and the JavaScript suffixes, the comment type alone names the file:
  a file that type does not discover, such as a ``src-trace`` ``:file:`` target with another suffix,
  is parsed with that type's grammar and records its language --
  a ``.py`` file named in a project with ``comment_type = "cpp"`` is parsed as C++ and records ``cpp``,
  and under ``comment_type = "ts"`` every file but a JavaScript one records ``typescript``.
  A ``.c`` file is read with the C++ grammar too, though it records ``c``, and its names follow C++'s rule;
- ``entity_kind`` -- ``function``, ``method``, ``constructor``, ``destructor``, ``operator``, ``class``, ``struct``,
  ``union``, ``enum``, ``interface``, ``trait``, ``impl``, ``record``, ``namespace``, ``module``, ``type``, ``macro``,
  ``property``, ``event``, ``indexer`` or ``delegate``; ``test`` for a Pester ``It`` block (a ``Describe`` or a
  ``Context`` is a ``namespace``); in YAML and JSON ``key`` or ``item``.
  VHDL takes these kinds where one fits: an entity is a ``module``, its architecture an ``impl``, a package (its
  declaration, its body, an instance of it) a ``namespace``, a component an ``interface``, a function or a procedure
  (declared, defined or instantiated) a ``function``, an enumeration, record or protected type (or protected body)
  an ``enum``, ``record`` or ``class``, and any other type or subtype a ``type``. Every other VHDL design element --
  a configuration, a context, a process, a block, a generate, a component instance, a concurrent signal assignment,
  assertion or procedure call, a signal, constant, variable, file or alias, a generic, a port, a parameter -- has
  ``null``, and is named all the same (see ``semantic``).
  Swift takes these kinds too: a class, a struct and an enum are themselves, an actor is a ``class``, an extension
  an ``impl`` (named after the type it extends, as a Rust impl is), a protocol an ``interface``; a function is a
  ``method`` in the body of a type, an extension or a protocol and a ``function`` anywhere else (a local function
  included), an operator function an ``operator``; an initializer is a ``constructor``, ``deinit`` a
  ``destructor``, a subscript an ``indexer``; a property of a type (stored or computed) and a protocol's property
  requirement a ``property``; a ``typealias`` and an ``associatedtype`` a ``type``; a macro a ``macro``;
- ``qualified_name`` -- the entity's name within its file, qualified by the containers the file shows:
  ``ns::Widget::draw`` in C++, ``Shape.area`` and ``outer.<locals>.inner`` in Python (its ``__qualname__``),
  ``Widget::new`` and ``<Widget as Shape>::area`` (and ``<dyn Shape>::area`` for a type that is no path) in Rust,
  ``Acme.Gfx.Widget.Draw`` in C#, ``Widget.Area`` in Go, ``Gfx.Widget.draw`` in TypeScript,
  ``counter.rtl.p_main`` in VHDL (as VHDL's expanded names are written, with an architecture under the entity its
  ``of`` clause names, as the source spells it: VHDL is case-insensitive, and the name is not folded; an extended
  identifier keeps its backslashes, an operator function its quotes, ``"+"``),
  ``Shape.Area`` in PowerShell, where a Pester block is named after the blocks around it, joined with ``.`` as
  Pester joins a test's path (``px.starts`` for ``It 'starts'`` in ``Describe 'px'``). A block's own name is its
  ``-Name`` argument, else its first positional argument past Pester's switches (``-Skip``) and its parameters with
  their values (``-Tag Unit``), as the source writes it: a string without its quotes, a here-string's included, and
  never expanded (``It 'adds <a>'`` stays ``adds <a>``, ``It "starts $x"`` stays ``starts $x``). A block named by a
  variable or an expression, or past a parameter Pester does not declare, has no name, and neither has any block
  inside it.
  ``Widget.greet(name:_:)`` in Swift, where a function, an initializer, a subscript and an operator are named by
  their full name, as Swift itself writes it: the base name and the argument labels, each followed by ``:``
  (``init(x:)``, ``subscript(_:)``, ``==(_:_:)``, ``f()`` without parameters), so that overloads that differ by
  their labels alone (``init(x:)`` and ``init(y:)``) are different entities. A label is the parameter's external
  name where it declares one (``for`` in ``for x: Int``, ``_`` in ``_ x: Int``), else its name; a subscript's and an
  operator's parameters have no label unless they declare one (``subscript(index: Int)`` is ``subscript(_:)``). A
  parameter's type, default value, ``inout`` and ``...`` are not part of the name, a failable ``init?`` is
  ``init``, and ``deinit``, a type, a property, a ``typealias`` and a macro are named by their name alone. A local
  function is named after the functions around it (``Widget.greet(name:_:).repeated(_:)``), and a member of an
  extension after the extended type, without its generic arguments (``Array.dedup()`` in
  ``extension Array where Element: Equatable``). Identifiers are written as the source writes them, backticks
  included.
  No module, crate or package prefix: the file's path decides that. A Swift extension of a type qualified by its
  module (``extension Foundation.Date``) keeps the module as a part of the name (``Foundation.Date.f()``): the syntax
  cannot tell a module from a type.
  ``null`` in YAML and JSON, and for an entity without a name -- in VHDL an unlabelled process or statement, a
  declaration of several names (``signal a, b : bit``), and anything inside one of them; in Swift a property
  declaring several names (``var a = 0, b = 0``) or a tuple pattern (``var (a, b) = t``), and anything inside one;
- ``semantic`` -- that name in its parts, outermost first and the entity itself last, each a ``kind`` and a ``name``
  (``null`` exactly when ``qualified_name`` is). The kinds are those of ``entity_kind`` but ``key`` and ``item``
  (a YAML or JSON entry has no name, so no parts), and one more, for what the syntax alone cannot classify:
  ``scope``, a C++ qualifier such as the ``ns`` of ``void ns::W::f() {}`` (the qualifier right before a method,
  a constructor, a destructor or a conversion operator is its ``class``; so is the ``ns`` of a free function defined
  with a namespace qualifier, ``void ns::f() {}``, which reads as a method), and a VHDL design element no kind fits,
  whose ``entity_kind`` is ``null`` (``module counter``, ``impl rtl``, ``scope p_main``, ``scope v`` for a variable
  of a process).
  The type a Go method's receiver names is a part of kind ``type``.
  A Swift extension is a part of kind ``impl`` named after the type it extends, and a dotted path is split, the
  types before the last a ``scope`` each (``extension Outer.Inner`` is ``scope Outer``, ``impl Inner``), with no
  ``trait`` key for the protocols it conforms to.
  A Rust ``impl`` is a part of kind ``impl`` named after its self type as written
  (``Widget``, ``dyn Shape``), with a ``trait`` key for a trait impl (the trait as ``qualified_name`` spells it); the
  in-file modules an impl is written in are parts of their own before it (``mod m { impl G {} }`` is ``module m``,
  ``impl G``), and a path from the crate root keeps its ``crate::`` where that decides what it names
  (``crate::Q`` in ``mod k``); nested Python functions are consecutive ``function`` parts (``<locals>`` is no part); a
  name that is an expression, the left-hand side of a JavaScript assignment (``module.exports.f``), is one part; and a
  C++ name keeps the arguments of a specialisation, explicit or partial (``Box<bool>``, ``P<T,4>``), and drops a class
  template's own parameters (``Box::get``), as ``qualified_name`` does (see :ref:`cpp_names` below).
  Joined by the rule of the ``language`` -- ``::`` for C, C++ and Rust
  (with ``<Widget as Shape>`` from a ``trait``, ``<dyn Shape>`` for a self type that is no path, and the modules before
  an impl folded into a self type written bare, ``m::G``, but not into a path, a primitive or a type that is no path),
  ``.`` for Python (with ``<locals>`` after a function or a method another part follows) and every other language --
  the parts are ``qualified_name``, exactly.

  **Kinds describe, names identify.** A kind is a best-effort classification, for filtering and rendering, and one
  entity's kinds can depend on how it is written: a method defined in its class is ``namespace ns``, ``class W``,
  ``method f``, and the same method defined out of line is ``scope ns``, ``class W``, ``method f``. Whether two
  ``semantic`` lists name the same entity, or one is inside the other, is decided by their *name chains*, the
  identity-bearing part of their rendering: the names, a ``trait`` (``<Widget as Shape>::area`` and
  ``<Widget as Other>::area`` differ by their ``trait`` alone) and Python's ``<locals>`` boundaries (``A.f.g``, the
  method of a nested class, is not ``A.f.<locals>.g``, a function in a method) -- never by their kinds. So a Rust
  impl's methods are inside the module the impl is written in, as its free functions are, and a Swift method written
  in an extension has the name chain it has written in its type. A name chain cannot tell
  apart what the qualified name cannot: overloads (but for Swift's, whose names carry their argument labels;
  ``f(x: Int)`` and ``f(x: String)`` still share one), a C ``struct stat`` and a function ``stat()``, C# classes
  that differ in their number of type parameters;
- ``mechanism`` -- how the marker was attached: ``doc_comment`` (a documentation comment -- ``///``, ``//!``, ``/**``,
  ``/*!``, a C# ``///``, a JSDoc ``/**``, a VHDL ``--!`` (not ``--!!``), a Swift ``///`` or ``/**`` -- a Python
  docstring, or PowerShell comment-based help first in a function's body),
  ``leading`` (a comment on the lines before the entity, or directly inside or right after an attribute, a decorator
  or a template header in its head), ``trailing`` (after code on the entity's own line) or ``enclosing`` (inside its
  body).

``scope`` is ``null`` exactly when ``tagged_scope`` is: the marker is attached to no entity (the file), and always
under the libclang engine.
The record then carries no ``language`` either, since ``language`` is recorded only inside ``scope``.
The names are best effort, from the syntax alone: overloads share a name,
a free function defined with a namespace qualifier (``void ns::f() {}``) reads as a method,
and a function a macro defines (``TEST(LoginTest, RateLimited) {...}``) is bound but not named,
since the compiler's function is the macro's expansion
(a macro whose arguments are not names, such as Catch2's ``TEST_CASE("…")``, may not be bound at all).
A class declared with an export macro (``class EXPORT_API Widget``) is misread by the grammar:
it is bound without a name, or not at all.
A ``friend`` declaration is no entity a marker before it can bind: such a marker is attached to the class.
In Rust, an ``impl`` inside a function is named without the function's path,
and an ``impl W`` for a ``W`` brought in with ``use`` is named in the module the ``impl`` is written in.
The needs ``src-trace`` creates carry no field for the entity: it is recorded here, in the analysis output,
and will be exposed on the need together with the need's source record.

.. _cpp_names:

C++ names
~~~~~~~~~

A C++ name follows the one clang prints for the entity, where that differs from what one node of the syntax shows,
so that it can be joined with what a compiler reports, and so that two spellings of one function meet:

- **An inline namespace adds nothing** to the names of what it holds:
  an ``f`` in ``inline namespace v1`` inside ``lib`` is ``lib::f``, as clang prints ``nlohmann::basic_json``
  rather than ``nlohmann::json_abi_v3_12_0::basic_json`` (a library's ABI namespace changes with every release).
  The inline namespace itself keeps its own name (``lib::v1``), and so does the ``inline`` part of a C++20 nested
  name (``namespace a::inline v1`` is ``a::v1``, the ``f`` in it ``a::f``).
  It adds nothing either to a name in a reopening of it without ``inline`` (C++ makes the reopening inline),
  or to a name written out of line through it in the same file: a function (``void lib::v1::f(int) {}`` is ``lib::f``,
  as its declaration in ``inline namespace v1`` is), a class (``struct lib::v1::X {…}`` is ``lib::X``, and so are
  its members' names) or a conversion operator.
- **A friend is named in its namespace.** A function a ``friend`` declaration declares or defines is named in its
  innermost enclosing namespace, not in the class (``ns::operator==``, a hidden friend's ``ns::touch``),
  so a friend declared in its class and defined in its namespace has one name;
  a qualified friend keeps its qualifier (``friend void Other::h();`` is ``ns::Other::h``).
- Both are left out **except where two definitions of the file would then share a name and parameters**:
  two classes' hidden ``operator==``, one function in two inline namespaces,
  the ``#if`` and ``#else`` arms of an ABI version (``inline namespace v1`` and ``v2``).
  Then every entity of that name and parameters that leaves a container out keeps its full chain, declarations
  included (``ns::List::iterator::operator==``, ``lib::v1::g`` and ``lib::v2::g``),
  and so does everything but a friend that a class or namespace that keeps its full chain holds
  (``lib::v1::Widget::draw`` beside another ``Widget`` in ``lib``; a friend there is still ``lib::swap``),
  so a marker never names another definition.
  clang keeps an inline namespace wherever the name alone would be ambiguous;
  this decides by the name and parameters among the file's definitions,
  and for friends, and for the arms of an ``#if`` (a compiler sees one of them), keeping the chain is a choice to fail
  safe.
- **A partial specialisation keeps its arguments**, as an explicit specialisation does,
  spelled as the name is everywhere: whitespace squeezed (a space only between two words)
  and comments inside the list left out (``template <typename T> struct P<T, /* four */ 4>`` is ``P<T,4>``,
  its members ``P<T,4>::fill``, apart from the primary template's ``P::fill``).
- **Out of line, a qualifier's arguments are dropped only when they are the template's own parameters**:
  exactly the parameter names of the template header around the definition, in order
  (``template <typename T> void Box<T>::get()`` is ``Box::get``, the primary template's member).
  A qualifier the same as a partial specialisation the file defines, but for its parameter names,
  is spelled as that specialisation spells it
  (``template <typename U> void P<U, 4>::fill()`` is ``P<T,4>::fill`` beside ``template <typename T> struct P<T, 4> {…}``)
  when exactly one specialisation with a body in that scope matches:
  a pack is not a plain parameter (``S<A, B>`` is spelled as ``S<T, U>``, never as ``S<T, Ts...>``),
  a forward declaration never sets the spelling,
  and specialisations of one template name in two namespaces or two classes never share one.
  A qualifier that names none of the header's parameters is kept, and takes no header but an empty ``template <>``
  (``template <> template <class U> void Outer<int>::Inner<U>::n()`` is ``Outer<int>::Inner::n``).
  So a member's declaration in its class and its definition out of line share a name.
- **A namespace macro the file defines itself is read**:
  what lies between its invocations is named in the namespaces it opens (``json.hpp``'s
  ``NLOHMANN_JSON_NAMESPACE_BEGIN`` opens ``nlohmann``, its inline ABI namespace left out),
  an anonymous namespace there too.
  It is read when it is an object-like macro the file defines (one way, or identically),
  whose body is only ``namespace … {`` (not an all-capitals name) or ``inline namespace … {``,
  invoked alone on its line, in code, its openings and closings balanced.
  The file is parsed from a copy with each opening invocation written as ``extern"C++"{``
  and each closing one as ``}``, padded to their length: every line, column, name and tagged scope
  is the file's as written.
  An opening the parse does not read as that block (a macro statement on the line before it) is left as written,
  and so is every pair inside it or right after one of its invocations;
  if a pair still does not read as its block, the whole file is read as written: no function is lost.

What the macro rule does not read:

- A macro defined in another header, as fmt's ``FMT_BEGIN_NAMESPACE`` is, is not seen:
  the names inside it lack its namespace.
- An opening shorter than 12 characters (``NS_OPEN``) is left as written, and so is any pair inside it:
  the markers around it are attached as before, and the names inside it lack its namespace.
- A function-like macro (``PYBIND11_NAMESPACE_BEGIN(name)``) is not read, nor a macro the code also uses beside
  other code on a line; an invocation written ``NAME;`` leaves the whole file unread when the pair's other invocation
  is written alone, and only that macro when both are written ``NAME;``.
- A pair inside a namespace, a class or an ``extern "C"`` block is named without the macro's namespace.
- A marker right before an opening or a closing invocation, or on its line, is attached to no entity,
  as one before an ``extern "C++" {`` block is
  (clang gives a documentation comment there to the namespace, which no entity stands for);
  before an opening shorter than 12 characters, it is attached as before.
- A ``.c`` file is C: its macros are never read.

What the inline-namespace rule does not see:

- An inline namespace only another file declares: a qualifier written through it keeps it
  (``void lib::v1::f() {}`` is ``lib::v1::f``), and a reopening of it without ``inline`` is read as a plain one.
- A qualifier that skips an outer inline namespace keeps the inner one
  (``void lib::abi::f() {}`` is ``lib::abi::f`` where ``abi`` is declared inside ``inline namespace v1``, both inline).
- A class defined inside a function in an inline namespace is named without both (``lib::Local``),
  so two such classes of one name in two functions share their members' names.
- An inline namespace a namespace macro opens is left out of every name,
  even where two definitions then share a name and parameters.
- A declaration in an inline namespace beside a definition of the same name and parameters in its parent
  (``namespace lib { void g() {} inline namespace v1 { void g(); } }``) is named as that definition (``lib::g``):
  only definitions decide what is kept apart.
- A ``friend`` of a class defined out of line through a qualifier
  (``struct lib::v2::X { friend void swap(X&, X&) {} };``) is named in the namespace around that definition,
  not the qualifier's (``swap``, where clang prints ``lib::swap``).

The rules
~~~~~~~~~

In this order:

1. **YAML and JSON**: the key/value pair or item on the comment's line, else the next one, else the enclosing one.
2. **A Python docstring** documents the function or class it is in.
3. **A Rust inner doc comment** (``//!``, ``/*!``) documents what it is inside: the module, or the file.
   **PowerShell comment-based help** first in a function's or a filter's body documents that function, even when a
   nested function follows: a ``<# #>`` comment, or a run of ``#`` comments on consecutive lines, holding one of
   PowerShell's comment-based-help keyword lines, with nothing but other comments before it in the body. A keyword
   line holds a keyword alone (``.SYNOPSIS``, ``.DESCRIPTION``, ``.EXAMPLE``, ``.INPUTS``, ``.OUTPUTS``, ``.NOTES``,
   ``.LINK``, ``.COMPONENT``, ``.ROLE``, ``.FUNCTIONALITY``), or a keyword that takes an argument with that one
   argument (``.PARAMETER``, ``.FORWARDHELPTARGETNAME``, ``.FORWARDHELPCATEGORY``, ``.REMOTEHELPRUNSPACE``,
   ``.EXTERNALHELP``), in any letter case and with whitespace around: ``.PARAMETER Path`` is one, ``.NOTES: detail``
   and ``.SYNOPSIS Starts it.`` are not. A plain comment there follows rule 6, and help before the function, or at
   the end of its body, is attached as any comment is (rules 6 and 8).
4. **A trailing marker** -- code before it on its line -- belongs to the entity on that line (a Doxygen ``///<`` after
   a function declaration is the classic case; after a data member or an enumerator it belongs to the enclosing class,
   struct or enum), else to the entity it is inside: ``trailing`` when that entity starts on the marker's line
   (``def f():  # @...``, a VHDL ``function f return t is -- @...``), ``enclosing`` otherwise.
   In VHDL, the entity on the line is the innermost design element that ends there: the signal of
   ``signal s : bit; -- @...``, the port of ``clk : in std_logic; -- @...``, but never a subprogram's parameter: after
   ``procedure inc(variable v : inout integer); -- @...`` it is the procedure. An attribute, a decorator or a template header before the marker
   is not code: the marker leads the item they precede (an inner attribute, ``#![...]``, precedes none: it applies to
   what it is inside). So are a Swift declaration's attributes and modifiers: ``@MainActor // @...`` leads the
   class on the next line.
5. **The comments before a file's first item**, when a blank line separates the last of them from it, belong to the
   file -- documentation comments (``///``, ``/** */``, ``/*!``, a VHDL ``--!``) excepted: they document the next
   item, blank lines or not, as rustc and Doxygen read them, unless the comment holding the marker says it documents
   the file (``@file``, ``\file``, ``@fileoverview``, ``@packageDocumentation`` or ``@module``, as a whole word at
   the start of the comment or after whitespace, ``*``, ``/`` or ``!``).
   That exception holds only for the comments before the first item: a ``@file`` block after ``#pragma once`` or
   inside an include guard documents the next item like any documentation comment, and so does a ``///`` line whose
   ``\file`` is on another line of the run.
   In VHDL, whose only documentation comment is a line comment, a run of ``--!`` lines on consecutive lines is one
   comment, as Doxygen reads it: a ``--! @file`` line makes every line of its run document the file.
   A VHDL design unit's first item is the unit itself, its ``library``, ``use`` and ``context`` clauses included, so
   a licence banner before them, and a blank line after the banner, is the file's.
   A Swift shebang line (``#!/usr/bin/env swift``) is no item: the comments after it are the ones before the first
   item.
6. **A leading marker** belongs to the entity right after it, when only *trivia* stands between: other comments,
   blank lines, attributes (Rust ``#[...]``, C++ ``[[...]]``) and decorators (TypeScript). The entity is looked for
   through what wraps it: a Python decorator, a C++ ``template <...>`` header or ``extern "C"``, a TypeScript
   ``export`` or ``declare``. In Python, a comment between ``def f():`` and the first line of its body belongs to that
   first line's entity, if it is one. In VHDL, a comment before a design unit's context clauses belongs to the unit
   they open, and a comment before the first declaration of a process, a block or a generate, or before the first
   generic or port of a list, belongs to that declaration, generic or port, if it is an entity.
   In Swift, a declaration's attributes and modifiers are part of it, so a marker between them and the declaration
   (``@Published`` on one line, the marker on the next, ``var count`` after it) leads it, and a comment before the
   first statement of a body (a function's, a closure's, an accessor's) belongs to that statement's entity, if it is
   one: a local function.
7. **A marker directly above a preprocessor conditional**, in C and C++ (and in Swift, as below) -- with only other
   comments, and no blank line, between it and an ``#if``, ``#ifdef``, ``#ifndef``, ``#elif``, ``#elifdef``,
   ``#elifndef``, ``#else`` or ``#endif`` line -- belongs to the file anywhere outside a function's body (at file level, in a namespace, class,
   struct, union or enum body, or in an ``extern "C"`` block), where the namespace, class, struct, union or enum around
   it would otherwise hold it, and a namespace or class would then trace every function inside, whichever arm is
   compiled.
   clang reads it so: a comment documents no declaration across a ``#`` line.
   The directive is read as the grammar reads it, so a spelling the grammar does not read as one, such as a digraph
   (``%:if``), is no conditional to this rule, though it is to a compiler.
   The analyser warns about each marker this rule places, at the marker's line (a multi-line need's open line),
   whatever kind of marker it is:
   ``src/x.cpp:2: WARNING: marker_above_conditional: directly above a preprocessor conditional, so attached to no
   entity: put the marker inside the arm, above the definition [codelinks.marker_above_conditional]``.
   ``suppress_warnings = ["codelinks.marker_above_conditional"]`` silences it; ``codelinks analyse`` prints it with
   the other analyser warnings, and a project that no ``src-trace`` directive traces reports none, as for every
   analyser warning. The libclang engine attaches no marker to any entity, so it never gives this warning.
   To trace an arm's definition, write the marker inside the arm, directly above the definition (rule 6); to mean the
   namespace or class as a whole, leave a blank line between the marker and the directive (rule 8).
   In a function's body (a lambda's, or a class defined in one, included), rule 8 holds.
   **In Swift**, the rule reads ``#if`` lines alone (not ``#elseif``, ``#else`` or ``#endif``): a marker directly
   above one, among declarations -- at file level, or in the body of a type, an extension or a protocol, not in any
   body of code (a function's, a closure's, an accessor's, an ``if``'s; a type declared in a function's body
   included) -- belongs to no entity, with the same warning, as swiftc attaches a documentation comment there to
   the conditional compilation block rather than to a declaration inside it. A marker inside the block, above a
   declaration, leads that declaration (rule 6).
8. **Otherwise**, the entity the marker is inside, if any: ``leading`` when the marker is directly inside, or right
   after, an attribute, a decorator or a template header the entity owns (its head; a comment nested deeper, in such a
   head's argument list, is not), ``trailing`` when it trails code on the entity's first line, ``enclosing``
   otherwise.

Anything else between a leading marker and an entity -- a statement, a variable, a macro call,
a preprocessor directive (``#include``, ``#define``, ``#pragma``, ``#if``) -- breaks the attachment:
the marker belongs to the entity it is inside, or to the file, and always to the file directly above a conditional
outside a function's body (rule 7). A marker is never attached across code.

What counts as an entity
~~~~~~~~~~~~~~~~~~~~~~~~

- **C and C++**: functions, prototypes, in-class method declarations and conversion operators (not a function
  pointer, nor a local that merely parses like a prototype), classes, structs, unions and enums with a body (not a
  forward declaration), namespaces. A class member inside ``#if`` / ``#else`` is still a member (a constructor, a
  destructor, a method).
- **Python**: functions and classes.
- **Rust**: functions, required trait methods, structs, enums, unions, traits, impl blocks, modules, type aliases,
  ``macro_rules!`` definitions.
- **C#**: methods, constructors, destructors, properties, indexers, operators, conversion operators, events, delegates,
  local functions, classes, structs, interfaces, records, enums, namespaces (block or file-scoped).
- **Go**: functions, methods, type declarations, interface methods.
- **TypeScript and JavaScript**: functions, classes, interfaces, enums, type aliases, namespaces, methods and method
  signatures; a ``const``, ``let`` or ``var``, a class field, an assignment or a default export only when it holds a
  function or a class (one written with ``declare`` always does).
- **Bash**: functions.
- **VHDL**: entities, architectures, packages and package bodies, package instances, configurations, contexts;
  functions and procedures, declared, defined or instantiated; types, subtypes and components; signals, constants,
  variables, files and aliases; generics, ports and parameters; processes, blocks, generates (``for``, ``if`` and
  ``case``), component instances, and concurrent signal assignments, assertions and procedure calls. A sequential
  statement, a record field, an ``attribute`` declaration or specification is none: a marker before one is attached to
  the entity it is inside.
- **PowerShell**: functions, filters and workflows (each a ``function``, named without a ``global:``, ``script:``,
  ``private:`` or ``local:`` scope modifier, as it is called), classes, methods, constructors (a method named as its
  class, in any letter case, without a return type), properties, enums, and Pester's ``Describe``, ``Context`` and
  ``It`` blocks (in any letter case, bare or as ``Pester\It``, known by that name alone, so a function or an alias of
  the script's own of that name is taken for Pester's); no other command, a DSC ``Configuration`` included. A
  pipeline, or a chain of them (``&&``, ``||``), is the first of its commands that is an entity: a marker above
  ``Describe 'x' { } | Out-Null`` or trailing ``It 'x' { } | Out-Null`` is attached to that block, one above
  ``Get-Thing | It 'y' { }`` to the ``It``; a marker inside another command of the pipeline (in a
  ``ForEach-Object { }`` block after it) is not in that block, but in the entity around the pipeline. The
  ``tree-sitter-powershell`` grammar cannot read an attribute before a class or an enum (``[DscResource()]``,
  ``[Flags()]``), so a marker above such an attribute is attached to no entity; with the attribute on a line of its
  own, a marker trailing the ``class`` or ``enum`` line is attached to it.
- **Swift**: classes, structs, enums, actors, extensions, protocols; functions (free, local and member), operator
  functions, protocol requirements, initializers, ``deinit``, subscripts; the properties of a type, stored or
  computed, and a protocol's property requirements; ``typealias``, ``associatedtype`` and macro declarations. Not
  entities: a top-level or local ``var`` or ``let``, an enum ``case``, an ``import``, an ``operator`` or
  ``precedencegroup`` declaration, a closure, an accessor (a marker in a ``get``, ``set``, ``willSet`` or ``didSet``
  of a type's property is attached to that property; a top-level computed ``var`` is a variable, so a marker in its
  accessor is attached to the file) and a macro expansion such as ``#Preview``. A swift-testing ``@Test`` function or
  an XCTest ``test…`` method is a ``function`` or a ``method``, not a ``test``. Four limits of the
  ``tree-sitter-swift`` grammar, documented rather than worked around:

  - A block comment followed by code on its own line at statement level (at file level or in a body of code, not in
    a type's body) -- ``/* @Title, ID_1, impl */ func f() {}`` -- is parsed as a syntax error. After a declaration
    or an ``import``, the error takes the statements before it in. After a statement that ends in an expression
    (``let x = 1``, a call, ``typealias T = Int``), the comment and the code after it on its line are read into that
    expression, so a declaration there is no entity. Either way its marker is still extracted, but it and the markers
    around it may lose their entity, and the comments before the file's first item may no longer be its header. Put
    the block comment on a line of its own, or use ``//``.
  - A bare regular expression literal with an escaped slash at the end of a line (``let r = /a\/b/``) swallows the
    lines after it: a marker there is still extracted, but attached to the wrong entity. Write it as an extended
    literal, ``#/a/b/#``.
  - Experimental or very new syntax (``@_lifetime(...)``, ``unsafe`` expressions, ``@_extern``) can parse as a
    syntax error: markers in such a file are still extracted (in a sample of public code, 8 comment lines in
    81,000 were lost, all in one file), but their attachment around the error degrades.
  - A string whose text opens ``/*`` (``let open = "/*"``) is read as one comment inside the string up to the next
    ``*/``. When that ``*/`` is in another string (``"/*"`` … ``"*/"``), there is no syntax error: the code between,
    its markers included, is silently lost. When it is anywhere else (a ``//`` comment, say), the string is left open,
    which is a syntax error, and the code after the ``*/`` is lost too, up to the next ``"`` or the end of the file.
    Write such a string as ``"/" + "*"``, or close the ``/*`` in the same string.

Data members, variables, lambdas bound to a name and macro invocations are not entities, nor, yet, a C
``typedef struct {...} T;``: a marker above one is attached to the entity it is inside, or to the file.
VHDL is the deliberate exception: a hardware design traces its ports and signals, so its data elements are entities,
without a kind.

Extraction Examples
-------------------

The following examples are configured with :ref:`the analyse configuration <analyse_config>`,

Sphinx-Needs ID References
~~~~~~~~~~~~~~~~~~~~~~~~~~

Below is an example of a C++ source file containing need ID references and the corresponding JSON output from the analyse.

.. tabs::

   .. code-tab:: cpp

        #include <iostream>

        // @need-ids: need_001, need_002, need_003, need_004
        void dummy_func1(){
            //...
        }

        // @need-ids: need_003
        int main() {
            std::cout << "Starting demo_1..." << std::endl;
            dummy_func1();
            std::cout << "Demo_1 finished." << std::endl;
            return 0;
        }

   .. code-tab:: json

        [
            {
                "filepath": "tests/data/need_id_refs/dummy_1.cpp",
                "remote_url": "https://github.com/useblocks/sphinx-codelinks/blob/fa5a9129d60203355ae9fe4a725246a88522c60c/tests/data/need_id_refs/dummy_1.cpp#L3",
                "source_map": {
                    "start": { "row": 2, "column": 14 },
                    "end": { "row": 2, "column": 52 }
                },
                "tagged_scope": "void dummy_func1(){\n     //...\n }",
                "scope": {
                    "kind": "function_definition", "start": 4, "end": 6, "language": "cpp",
                    "entity_kind": "function", "qualified_name": "dummy_func1",
                    "semantic": [{ "kind": "function", "name": "dummy_func1" }], "mechanism": "leading"
                },
                "need_ids": ["need_001", "need_002", "need_003", "need_004"],
                "marker": "@need-ids:",
                "type": "need-id-refs"
            },
            {
                "filepath": "tests/data/need_id_refs/dummy_1.cpp",
                "remote_url": "https://github.com/useblocks/sphinx-codelinks/blob/fa5a9129d60203355ae9fe4a725246a88522c60c/tests/data/need_id_refs/dummy_1.cpp#L8",
                "source_map": {
                    "start": { "row": 7, "column": 14 },
                    "end": { "row": 7, "column": 22 }
                },
                "tagged_scope": "int main() {\n   std::cout << \"Starting demo_1...\" << std::endl;\n   dummy_func1();\n   std::cout << \"Demo_1 finished.\" << std::endl;\n   return 0;\n }",
                "scope": {
                    "kind": "function_definition", "start": 9, "end": 14, "language": "cpp",
                    "entity_kind": "function", "qualified_name": "main",
                    "semantic": [{ "kind": "function", "name": "main" }], "mechanism": "leading"
                },
                "need_ids": ["need_003"],
                "marker": "@need-ids:",
                "type": "need-id-refs"
            }
        ]

**Output Structure:**

- ``filepath`` - Path to the source file containing the reference
- ``remote_url`` - URL to the source code in the remote repository
- ``source_map`` - Location information (row/column) of the marker
- ``tagged_scope`` - The full text of the code entity the marker is attached to, or ``null``
- ``scope`` - That entity, named: its kind, lines, language, name and the name's parts, and how the
  marker was attached (see :ref:`attachment`), or ``null``
- ``need_ids`` - List of referenced need IDs
- ``marker`` - The marker string used for identification
- ``type`` - Type of extraction ("need-id-refs")

.. _need_id_refs_matching:

How a marker is found
^^^^^^^^^^^^^^^^^^^^^

Each line of a comment is scanned from left to right for the configured markers
(:ref:`analyse.need_id_refs <need_id_refs_config>`):

- **A marker that ends in a letter, a digit or** ``_`` **matches a whole word only**: the character after it must not
  be one of those (or the line ends there). A letter or a digit here is any Unicode letter or number -- a character
  whose general category is L* or N* -- so a circled letter (``ⓐ``) or a combining mark is neither. The
  classification follows the Unicode tables of the Python that runs the build, so a character newer than another
  tool's tables can be classed differently there. With the marker
  ``\verifies``, ``\verifiesall REQ_2`` holds no reference.
  A marker that ends in anything else matches wherever it occurs: ``@need-ids:REQ_1`` is the reference ``REQ_1``.
  Nothing is required before a marker.
- **At one position, the longest marker wins**, and the scan goes on after it, so two matches never overlap: with
  both ``\verifies`` and ``\verifiesall`` configured, ``\verifiesall REQ_3`` is a ``\verifiesall`` reference.
- **A marker's ids run to the next marker on the line**, or to the end of the line: ``\satisfies REQ_1 \verifies
  REQ_2`` gives ``\satisfies`` the id ``REQ_1`` and ``\verifies`` the id ``REQ_2``. The ids are split on commas and
  whitespace; a ``*/`` closing the line is not an id. A marker with no id after it gives no reference.
- **Every match counts**: the same marker twice on a line gives both its references.
- A line whose first marker has no letter or number before it (after the comment's own decoration; the same Unicode
  letters and numbers) is a reference line, and never a one-line need.

.. _need_id_refs_in_build:

Need ID references in the build
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``src-trace`` directive attaches the ``@need-ids:`` references in the files it analyses to the needs they name, during the build -- the need may be defined in any document, before or after the directive. Each referenced need gets a list in its project's :ref:`ref_url_field` (default ``code_url``) -- or, for a marker given as a table, in the marker's own ``field`` (:ref:`need_id_refs_config`) -- one entry per reference, in source order:

.. code-block:: json

   "REQ_001": {
       "code_url": [
           "https://github.com/org/repo/blob/<commit>/src/refs.cpp#L1",
           "https://github.com/org/repo/blob/<commit>/src/refs.cpp#L3"
       ]
   }

- **The entries** are the project's ``remote_url_pattern`` filled in for the marker's line when :ref:`set_remote_url` is on, else the local link (as ``local-url`` gives it: the source file copied into the build output, relative to the need's document). On the need's card a remote entry renders as a link named ``src/refs.cpp#L1``; a value of the local shape (``<file>.<ext>#L<line>``) links to the generated source page. Outside a git repository, or in one without a commit yet, there is no remote URL (#2045): the local link is used when local URLs are on, else nothing is attached. With local URLs only, a file referenced by ``@need-ids:`` is copied into the output and gets a source page, as a file with a one-line need is (see :ref:`set_local_url` for when the copies and pages are written).
- **A need nothing references** carries ``null``, which is removed before schema validation, so a schema with ``unevaluatedProperties: false`` never sees the field on it. A schema with ``unevaluatedProperties: false`` on a type that code references must declare ``code_url``, or every referenced need of that type fails validation.
- **An unknown id** warns at the source line: ``src/refs.cpp:5: WARNING: @need-ids reference to unknown need 'NOSUCH_ID' [codelinks.need_id_ref]``. ``suppress_warnings = ["codelinks.need_id_ref"]`` silences it. Each project with attached references also reports ``codelinks [<project>]: N references attached, M unknown``; one marker naming an unknown id warns once, even when two fields cover its file.
- **A comment that starts with a configured marker** is a reference and never a one-line need, even on the default one-line style, whose start sequence ``@`` would match ``// @need-ids: A, B`` too.
- **Precedence.** The references replace any value the need's own directive or a ``needs_global_options`` default gave the field (ubCode's rule); a user's :external+needs:ref:`needextend <needextend>` overrides them, as the references are attached after every need is read and before any ``needextend`` is applied. ``:+code_url:`` appends to the attached list, but on a need nothing references it fails the build until `sphinx-needs #2038 <https://github.com/useblocks/sphinx-needs/issues/2038>`__ is fixed -- set the field (``:code_url:``) instead. The need is not marked as modified.
- **Overlapping scans** attach each reference once: two directives over the same file, or two projects whose source directories overlap. When those two projects' patterns differ, the reference keeps the URL of the first project by name. Files under different roots are different files, each kept: ``src/main.cpp`` in two repositories gives two references. Two projects naming different fields fill each its own field. A one-line need two such scans find is created once (:ref:`oneline_overlap`).
- **Incremental builds.** A file added to, removed from or edited in a directive's scope re-reads the document hosting the directive on the next build, for its references as for the needs it defines; the cost is one directory walk per scope per build, with no parsing: roughly 0.1 s per 2,000 discovered files on an Apple M2 Pro laptop, whatever their size -- the walk is the directive's own discovery plus a ``stat`` per file -- while parsing them costs tens of times more (2,000 200-line C++ files: ~0.1 s of walk against ~9 s of analysis). No build output is ever traced: the build's own output and doctree directories are skipped, and every builder writes an ``.ignore`` file (``*``) at the root of its output and doctree directories, so with ``gitignore = true`` (the default) nothing any builder writes -- the extension's source copies, Sphinx's ``_downloads/`` copies of a traced source, another builder's whole tree -- is traced, wherever the output sits: in ``_build/``, beside ``docs/`` in ``build/<builder>``, or inside a traced source directory, whose other files are traced as usual. With ``gitignore = false`` no ignore file is read, so the directory containing the output and doctree directories is skipped too when it lies inside the documentation source directory (``_build/`` in the Makefile layout), and an output directory elsewhere inside ``src_dir`` needs an ``exclude`` rule. A need whose references changed has its card rewritten, whichever document it is in: that document is written again, not read again. A ``needtable`` (or any other filter) in a third document that selects on the field is not rewritten -- the cross-document class ``needextend`` has today.

**Migrating from** ``analyse`` **→** ``write rst`` **→** ``include``: remove the ``.. include::`` of the generated file (and the steps that generate it); the references now arrive by themselves, in ``code_url`` rather than in the ``remote-url`` (or ``remote_url``) field the generated ``needextend`` directives set, and as a list rather than one comma-joined string. A project that keeps including the generated file gets both. If you declared the field yourself for that route (``needs_fields``), remove the declaration: the extension registers it, and a declaration of your own warns -- the extension's ``codelinks.config`` warning names the cure -- and, as a string field, fails schema validation on every referenced need.

**The field holds every reference**: a list, one entry per reference, and a reference to an unknown need warns. Another tool reading the same ``ref_url_field`` from a ``ubproject.toml`` may keep a single value instead.

Projects without a src-trace directive
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A project that no ``src-trace`` directive traces still has its ``@need-ids:`` references attached, as in ubCode: its whole source directory (``src_dir`` of :ref:`discover_config`) is discovered and analysed, and the references reach the needs they name exactly as a directive's do -- the same field, URLs, warnings and ``codelinks [<project>]: N references attached, M unknown`` line. The gate is the directive's own, and there is no switch of its own: local or remote URLs on, references extracted, at least one marker, and a :ref:`ref_url_field` that is not ``""``. A project that at least one directive traces is left to its directives.

- **No need is created.** One-line and multi-line needs in such a project's files are not rendered -- there is no directive, and so no document, to hold them. The project's line counts them: ``codelinks [src]: 12 files, 30 references, 2 one-line needs not created (no src-trace directive)``.
- **When it is analysed.** Every build walks the project's source directory and compares the files, their modification times and sizes with the last analysis; it analyses the project again only when they differ or the configuration changed. The cost of an unchanged build is that walk, with no parsing (see *Incremental builds* above for what the walk costs). A build that analysed the project again rewrites the cards of the needs whose references changed -- or, when none did, writes the root document -- so that Sphinx keeps the result and the next build analyses nothing.
- **Errors do not stop the build.** A missing source directory, or a discovery or analysis failure, warns once per project and build (``codelinks.need_id_ref``), and that project's references are not attached. A file whose target lies outside the source directory is skipped with a ``codelinks.outside_src_dir`` warning on every build, since the directory is walked every build -- a directive's scope warns only when its document is read.

.. _codelinks_doxygen:

Coming from Doxygen
^^^^^^^^^^^^^^^^^^^

Doxygen's ``\satisfies`` and ``\verifies`` commands (or their ``@`` forms) already say which requirement a function
implements and which one a test verifies. Configure them as reference markers, each with the field it fills, and the
requirement collects both kinds of reference:

.. code-block:: toml

   [codelinks]
   set_remote_url = true

   [codelinks.projects.app]
   remote_url_pattern = "https://github.com/org/repo/blob/{commit}/{path}#L{line}"

   [codelinks.projects.app.analyse.oneline_comment_style]
   start_sequence = "@@"

   [codelinks.projects.app.analyse.need_id_refs]
   markers = [
     "@need-ids:",
     { marker = "\\satisfies", field = "impl_url" },
     { marker = "@satisfies", field = "impl_url" },
     { marker = "\\verifies", field = "test_url" },
     { marker = "@verifies", field = "test_url" },
   ]

.. code-block:: cpp

   /// \brief Start the motor.
   /// \satisfies REQ_1
   void start(int rpm);

   /// \verifies REQ_1
   void test_start();

- **What it does.** ``REQ_1`` gets ``impl_url`` with the link to ``start`` and ``test_url`` with the link to
  ``test_start`` (see :ref:`need_id_refs_in_build`); the plain ``@need-ids:`` marker still fills
  :ref:`ref_url_field`. A filter such as ``type == "req" and not test_url`` lists the requirements no test verifies.
- **URL generation must be on.** The references are attached only when :ref:`set_remote_url` (with the project's
  ``remote_url_pattern``, as above) or :ref:`set_local_url` is on. Without it nothing is attached, ``impl_url`` and
  ``test_url`` are not registered, and a filter naming them is invalid.
- **Why** ``start_sequence = "@@"``. The default one-line start sequence is ``@``, so a Doxygen line such as
  ``@param a, b`` -- it holds the field separator -- is read as a one-line need (see
  :ref:`the note on documentation tags <oneline_doc_tags>`). Any start sequence Doxygen does not use avoids that.
- **One id per command.** Everything after a marker, up to the next marker on the line, is read as ids: Doxygen's
  optional ``(short description)`` after the id (``\satisfies REQ_2 (stops it, safely)``) is read as the ids
  ``(stops``, ``it`` and ``safely)``, which warn as unknown needs. Leave the description out.
- **Brace aliases are not read.** ``@implements{REQ_1}`` is no reference unless ``@implements`` is a marker, and then
  its id is ``{REQ_1}``.
- **A trailing** ``///<`` **on a data member** is recorded against the entity around it: data members are not entities
  (see :ref:`attachment`). The reference still reaches the requirement.
- **Documented entities do not become needs**: a reference fills a field of the requirement, and makes no need on the
  code side. That is not supported yet.

.. _multiline_needs:

Multi-line Needs
~~~~~~~~~~~~~~~~

A multi-line need is one need written across the lines of a comment: an open line with the
need's type and title, its options, a body in a declared markup, and a close line.

.. tabs::

   .. code-tab:: c

      #include <stdbool.h>

      /**
       * @need req: Login must be rate limited
       * :id: REQ_LOGIN_1
       * :links: SPEC_AUTH, SPEC_LOCK
       * :status: open
       *
       * After **five** failed attempts the account is locked;
       * see :need:`SPEC_AUTH`.
       * @endneed
       */
      bool login(const char *user, const char *password) {
          return false;
      }

   .. code-tab:: python

      # @need[md] impl: Exponential back-off
      # :id: IMPL_BACKOFF
      # :links: REQ_LOGIN_1
      #
      # Doubles the delay after each failure, see {need}`REQ_LOGIN_1`.
      # @endneed
      def backoff(attempt: int) -> float: ...

The first block's body is reStructuredText, the project default; the second declares Markdown
(MyST) with ``@need[md]``. The body is written in its declared markup and is parsed, when the need
is rendered, by Sphinx-Needs -- so roles and links into the documentation work as in a ``.. req::``
directive's content. The rest of the block is this tool's own grammar, neither RST nor MyST.

The grammar
^^^^^^^^^^^

After the comment's prefixes are stripped (see below), a block is:

.. code-block:: text

   @need[<markup>] <type>: <title>     the open line
   :<key>: <value>                     option lines, immediately after
       <continuation>                  a line indented deeper than its option line continues the value
   <body>                              the first line that is neither an option nor a continuation starts the body
   @endneed                            the close line

- **The open line** starts with the open word (``@need``), optionally followed by a markup tag in
  brackets, then whitespace, the need type and a colon, then the title -- the rest of the line,
  which may be empty. The open word counts only when ``[``, whitespace or the line end follows it:
  ``@need-ids:`` and ``@needle`` open nothing. The type is a need type's name (ASCII letters,
  digits, ``_`` and ``-``); it is checked when the need is rendered, not here. Write the whitespace:
  ``@need[md]req: T`` and ``@need req:T`` are refused.
- **The markup tag** is looked up in the project's ``markups`` table, which gives the need's
  ``doctype`` (``rst`` → ``.rst`` and ``md`` → ``.md`` by default); without a tag the project's
  ``default_markup`` applies (``rst``). The tag is matched exactly as written: ``[RST]``,
  ``[ md ]`` and an empty ``[]`` are unknown tags.
- **Options** are ``:key: value`` lines right after the open line. They may sit at any indentation
  -- at the open line's, as MyST writes a directive's options, or indented under it as in RST.
  Their values are kept as written, as directive strings: ``:links: SPEC_AUTH, SPEC_LOCK`` is the
  string ``"SPEC_AUTH, SPEC_LOCK"``, converted with the project's field definitions when the need
  is rendered, as a directive's options are. A key is ASCII letters, digits, ``_`` and ``-``, and
  whitespace must follow it (``:prïority: 3`` and ``:id:R1`` are body text). A line indented
  deeper than its option line continues the value, joined with one space, so **separate the
  options from the body with a blank line**: an indented first body line written directly after
  an option is read as that option's continuation.
- **The body** is every line after the options up to the close line: dedented by its common
  indentation (a TAB counts as one character), never re-flowed, with leading and trailing blank
  lines trimmed; it may be indented or not. A comment line holding only its prefix (``//``, ``#``,
  or a lone ``*`` in a block whose lines carry the ``*`` leader) inside it is a blank body line.
- **The close line** holds the close word (``@endneed``) alone, surrounding whitespace allowed. To
  write the close word at the start of a body line, escape it: a body line starting
  ``\@endneed`` -- after its indentation, so inside an indented literal block too -- is emitted
  as ``@endneed``, its indentation kept. Nothing else is escaped.

One need per block: the open word starting a body line is body text, and is noted with a warning.

Comment runs and prefixes
^^^^^^^^^^^^^^^^^^^^^^^^^

A block lives in one **comment run**: one block comment (``/* … */``, ``/** … */``, ``/*! … */``),
one Python string statement (a docstring, or any bare string statement), or consecutive line
comments (``//``, ``///``, ``//!``, ``--``, ``---``, ``--!``, ``#``) on consecutive rows with
the same delimiter and only whitespace before them on their rows. A code line, or a change of
delimiter, ends a run; a comment after code on its row neither starts nor continues one.

The comment prefixes are stripped by the comment's kind, never by searching the text, so every
line of a block keeps its source line:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Comment
     - Stripped from each line
   * - ``//``, ``///``, ``//!``, ``--``, ``---``, ``--!``, ``#``
     - the delimiter, then one space if there is one
   * - ``/* … */``, ``/** … */``, ``/*! … */``
     - first, a first row holding only the opener (with any number of stars, as in a ``/*****``
       banner) and a last row holding only the closer (``***/``) are dropped; then the
       delimiters; then a ``*`` leader (``*`` and one space, or a lone ``*``), only when every
       non-blank line between the opener's row and the closer's carries one -- so a plain block's
       ``*emphasis*`` is kept. A separator line of stars only (``*****``) counts as carrying the
       leader and is read as a blank line. Give every line the leader or none: when one line lacks
       it, an open word behind a ``*`` is reported (``multiline_need_header``) and no need is
       produced. So is an RST bullet starting ``* @need`` in a plain block's prose outside any
       need: write such a bullet with ``-``, or give the block leaders
   * - Python string statement
     - the quotes, and the lines' common indentation, as ``inspect.cleandoc`` removes it

Under the :ref:`libclang engine <preprocessor_engine>` what precedes a comment on its row is read
from the row itself; a block in an inactive preprocessor branch is not extracted.

Precedence over one-line needs and references
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The lines of a block belong to it alone: they are never read as one-line needs or ``@need-ids:``
references, whatever they hold. The default one-line start sequence ``@`` is a prefix of ``@need``,
and this rule is what keeps them apart: an open line such as ``@need req: Title, with a comma``, or a
body line such as ``@param a, b``, would otherwise be a one-line need. A refused one-line form
(``@need req: T @endneed``) hides its own line too; an open line without a close hides nothing. A
one-line marker or a reference on a line outside the block -- in the same comment or another -- is
found as before.

With multi-line needs switched on, a one-line need whose title starts with the open word, such as
``// @need to handle overflow, IMPL_3, impl``, is still a one-line need but also draws a
``multiline_need_unterminated`` warning: reword the title, or choose another open word.

Malformed blocks
^^^^^^^^^^^^^^^^

Each problem is an analyser warning at the source file and line; ``codelinks analyse`` prints them
as ``Analyse warning in <file>:<line> - <kind>: <message>``.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Kind
     - When, and what happens
   * - ``multiline_need_oneline_form``
     - The close word ends the open line (after whitespace): skipped, and the line is not read as a
       one-line need either (a one-line need is written with the :ref:`one-line marker <oneline>`).
       ``foo@endneed`` is no close word.
   * - ``multiline_need_unterminated``
     - No close line before the comment run ends: skipped, and the rest of the run is not read for
       blocks.
   * - ``multiline_need_header``
     - The open word starts a line that is not ``<open>[<markup>] <type>: <title>``: skipped, but
       its lines up to the close line are still the block's (not read as one-line needs). The same
       for an open word behind a ``*`` in a block comment whose lines do not all carry the leader:
       its lines up to the first close line, ``@endneed`` or ``* @endneed``, are the block's too;
       without one it is ``multiline_need_unterminated``. In a block where some lines carry the
       leader and others do not, every ``multiline_need_unterminated`` message names the missing
       leader as the likely cause; a plain block's message has no such hint.
   * - ``multiline_need_markup``
     - The markup tag is not in ``markups``: the need is produced with the project's default markup.
   * - ``multiline_need_duplicate_option``
     - An option key given twice, or one naming a key of the record itself (``type``, ``title``,
       ``content``, ``doctype``): the first value stands.
   * - ``multiline_need_nested_open``
     - The open word starts a body line: it stays body text.

.. _multiline_needs_rendering:

Rendering
^^^^^^^^^

The ``src-trace`` directive creates a need from every multi-line need in its files, with the
one-line needs and by the same rules: in one order, a block taking its place by its open line; one
need per id, the earlier line keeping it whatever the kinds (the ``codelinks.duplicate_need``
warning names the kind of the one skipped); the id written, or the one Sphinx-Needs generates from
the type and title.

- **The body is parsed in its declared markup**, whatever the page's: a Markdown body in a
  reStructuredText page renders its roles, references and lists, and so does the reverse. In a
  project written in MyST only, set ``default_markup = "md"`` (:ref:`multiline_needs_config`): a
  block without a tag is otherwise reStructuredText, the default.
- **The need is recorded at the directive**, as a one-line need is: its ``docname`` is the page and
  its ``lineno`` the ``src-trace`` directive's line; its ``doctype`` is the body's markup. Its source
  links (``local-url``, ``remote-url``) and the source page's ``[docs]`` link point at the open line.
- **Its options are a need directive's**: ``id``, ``status``, ``tags``, ``collapse``, ``hide``,
  ``style``, ``layout``, ``template``, ``pre_template``, ``post_template``, ``constraints``,
  ``jinja_content`` and the project's extra and link fields, converted as ``.. req::`` converts them
  -- a key lowercased (``:ID:`` is the id), links and tags split, typed fields coerced,
  ``jinja_content`` a flag. Any other key (``parts``, ``docname``, the directive's own ``delete`` and
  ``title_from_content`` …) is ignored with a warning at its line, the need kept; an empty ``:id:``
  refuses the need, as the directive does (``invalid_option``), and so does a value Sphinx-Needs
  refuses (warned at the open line). The title is the open line's, as a one-line need's is: an empty
  one draws no "title is required" warning, and ``needs_title_from_content`` does not apply.
- **Through a template, the page's markup.** A block rendered through a template -- its own
  ``:template:``, or one the project gives with the ``template`` field's default or a predicate (a
  predicate counts even where it does not match) -- is parsed as the page's markup, template and
  body together: a template is a file of the project, written in that markup. ``needimport`` does
  the same.
- **A markup no parser claims** -- a ``markups`` entry such as ``txt = ".txt"``, or ``md`` in a
  project without myst-parser -- falls back to the page's markup, still anchored at the body's
  source line (unless the page's own parser is neither reStructuredText nor MyST, when the body is
  parsed by that parser and its warnings sit at the page): the need is kept with its declared
  ``doctype``, and the directive warns once per markup, at the directive (not for a hidden block,
  or one without a body).
- **Warnings.** Every warning about a block's own content or options is
  ``codelinks.multiline_need`` -- the malformed blocks above included -- at the source file and line,
  relative to the git root; a skipped duplicate shares ``codelinks.duplicate_need`` with one-line
  needs; the unclaimed-markup warning is at the directive. A warning about the body itself, from
  docutils or Sphinx (an unknown role, an unresolved reference), names the source file by its
  absolute path, at the body's line -- except for a body rendered through a template or with
  ``jinja_content``, whose rendered text Sphinx-Needs anchors at the need (the page, at the
  directive's line), for a fallback body on a page of neither parser (above), and for myst-parser's
  own warnings about a Markdown body, which name the page with the body's line (myst-parser 4: the
  source file with ``.rst`` appended).

What a body should not contain
..............................

A body is parsed as part of the page that traces it, and this version refuses nothing in it (a
later Sphinx-Needs version will, as ubCode already does). So it should not contain:

- directives that read files (``include``, ``literalinclude``, ``csv-table`` with ``:file:``,
  ``raw`` with ``:file:``), and images and other references to files by a relative path:
  ``include``, ``literalinclude`` and images, and everything in a Markdown body, resolve against
  the page -- so a block traced from two pages reads two different files -- while ``csv-table
  :file:`` and ``raw :file:`` in a reStructuredText body resolve against the source file;
- ``raw``, and raw HTML in Markdown;
- need or ``needimport`` directives: the needs they create are recorded against the page, with the
  source file's line;
- labels (``.. _name:``, ``(name)=``): they belong to the page, so a block traced from two pages
  defines each twice;
- anything relying on the page's substitutions or ``rst_prolog``: it works, but the same block reads
  differently on another page.

The record
^^^^^^^^^^

``codelinks analyse`` writes each multi-line need to ``marked_content.json`` as one record of type
``multiline-need``. For the C example above, in a repository on GitHub:

.. code-block:: json

   {
       "filepath": "/home/me/repo/src/auth/login.c",
       "remote_url": "https://github.com/useblocks/demo/blob/4f2a9c1e0b7d3a5f6e8c9b0a1d2e3f4a5b6c7d8e/src/auth/login.c#L4",
       "source_map": {
           "start": { "row": 3, "column": 3 },
           "end": { "row": 10, "column": 11 }
       },
       "tagged_scope": "bool login(const char *user, const char *password) {\n    return false;\n}",
       "need": {
           "type": "req",
           "title": "Login must be rate limited",
           "id": "REQ_LOGIN_1",
           "links": "SPEC_AUTH, SPEC_LOCK",
           "status": "open",
           "content": "After **five** failed attempts the account is locked;\nsee :need:`SPEC_AUTH`.",
           "doctype": ".rst"
       },
       "markup": "rst",
       "source": {
           "project": "src",
           "path": "src/auth/login.c",
           "root": "git",
           "commit": "4f2a9c1e0b7d3a5f6e8c9b0a1d2e3f4a5b6c7d8e",
           "start": { "line": 4, "col": 3 },
           "end": { "line": 11, "col": 11 },
           "content_start": { "line": 9, "col": 3 },
           "option_lines": { "id": 5, "links": 6, "status": 7 },
           "scope": {
               "kind": "function_definition", "start": 13, "end": 15, "language": "c",
               "entity_kind": "function", "qualified_name": "login",
               "semantic": [{ "kind": "function", "name": "login" }], "mechanism": "doc_comment"
           }
       },
       "type": "multiline-need"
   }

- ``need`` -- the type, the title, the options in the order written with their values as written,
  ``content`` (the body, ``\n``-joined) and ``doctype``.
- ``markup`` -- the markup tag as resolved.
- ``source`` -- the codelinks project; the file, relative to the git root (``root: "git"``) or else
  to the project's source directory (``root: "src_dir"``), POSIX; the commit; the open line's start,
  the close line's end and the first body line's start (``null`` without a body), each with a
  1-based ``line`` and a 0-based ``col``; each option's line; and the code entity the block is
  attached to, the ``scope`` object of :ref:`attachment` (``null`` when the block is attached to the file rather than
  to an entity, and always under the libclang engine).
- ``filepath``, ``remote_url``, ``source_map`` and ``tagged_scope`` are the fields every
  ``marked_content.json`` record has; ``source_map`` spans the open line to the close line, 0-based.

``codelinks write rst`` ignores these records. The configuration is
:ref:`get_multiline_needs <get_multiline_needs>` and :ref:`analyse.multiline_needs <multiline_needs_config>`.

One-line Needs
--------------

**One-line Needs** provide a simplified syntax for creating **Sphinx-Needs** items directly in source code comments without requiring full RST syntax.

For comprehensive information about one-line needs configuration and usage, see :ref:`OneLineCommentStyle <oneline>`.

**Basic Example:**

.. code-block:: c

   // @Function Implementation, IMPL_001, impl, [REQ_001, REQ_002]

This single comment line creates a complete **Sphinx-Needs** item equivalent to:

.. code-block:: rst

   .. impl:: Function Implementation
       :id: IMPL_001
       :links: REQ_001, REQ_002

.. _oneline_overlap:

Overlapping scopes
~~~~~~~~~~~~~~~~~~

When ``src-trace`` directives' scopes overlap -- one tracing ``src/`` and another one file in it, or two projects whose source directories nest -- a one-line need they both find is created once, by its first owner: the directive Sphinx reads first (documents in name order, directives in document order). The id is the marker's, or the one Sphinx-Needs generates from the type and title when the one-line style has no ``id`` field. Whichever definition is read first keeps the id -- codelinks never takes an existing id over, and a hand-written or imported need read later is refused by Sphinx-Needs itself (``needs.create_need``, or ``needs.import_need`` for an imported one). Every other directive finding it skips it with one warning at the marker's line, naming both documents -- ``src/impl.cpp:1: WARNING: one-line need 'IMPL_1' is already defined in document 'page1': not created again by the src-trace directive in 'page2' (narrow one directive's scope) [codelinks.duplicate_need]`` -- and its ``codelinks [<project>]`` line adds ``, 1 skipped (already defined)``. A document that skipped a need is read again when the owner's document changes or is removed, so the need moves to it instead of vanishing (an incremental build leaves an existing owner in place until it is read again; two documents read in the same build give the earlier one, as a fresh build does). With ``-j N`` the two directives may be read by different workers, which cannot see each other's needs: Sphinx-Needs then keeps the first merged and warns ``needs.duplicate_id``, and when that directive later stops tracing the line, the other document takes the need over only when it is next read -- until then the need is missing from ``needs.json``, and that page keeps its old card.

.. _preprocessor_engine:

Preprocessor-Aware C/C++ Extraction (libclang)
----------------------------------------------

By default, **Source Analyse** uses a tree-sitter parser that extracts **every** comment,
regardless of the C preprocessor. For C/C++ projects that rely on conditional compilation
(``#ifdef VARIANT_A`` …), this means needs from *all* branches are extracted — even
branches that are never compiled.

The optional **libclang engine** addresses this. When an
:ref:`analyse.preprocessor <preprocessor_config>` table is configured and ``comment_type``
is ``"cpp"``, each file is parsed as a real translation unit and **comments inside inactive
preprocessor branches are dropped**. Active needs keep their original line numbers — no
source transformation is performed.

A branch is inactive when the file's own pass through the preprocessor skips it.
A file its own includes enter again -- a guarded header whose includes include it back, or a
file that includes itself -- passes through the preprocessor a second time, and that pass
finds the guard defined and skips the whole guarded body: its comments are kept all the
same, since the file's own pass compiled them. A source read through the entry that
includes it is one exception: there its first inclusion's pass decides
(:ref:`preprocessor_compile_db`); a header read through the entries that include it is the
other: there each entry's first inclusion of it decides (:ref:`preprocessor_headers`).

.. important:: The libclang engine requires an optional dependency:
   ``pip install 'sphinx-codelinks[libclang]'``. The wheel bundles the native library, so
   no compiler is required on the user's machine.

How files are selected and parsed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

File **discovery** is unchanged — :ref:`SourceDiscover <discover>` still decides which
files are candidates. A ``compile_commands.json`` database only determines *how* each
discovered file is parsed:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - File
     - How it is parsed
   * - Listed in ``compile_commands.json``
     - Parsed with the exact flags the compiler used for that translation unit, in the
       entry's ``directory``, for the target the entry declares (see
       :ref:`preprocessor_target`).
   * - A compiled source (``.c``, ``.cpp``, ``.cc``, ``.cxx``) **not** listed, that a
       listed source ``#include``\ s (a unity build)
     - Read through that entry's parse, with its flags (see
       :ref:`preprocessor_compile_db`).
   * - A compiled source **not** listed, that no listed source includes
     - Skipped, with a ``codelinks.not_in_compile_database`` warning — assumed to be
       excluded from the build (e.g. another platform).
   * - A **header** (``.h``, ``.hpp``, …, any file that is not a compiled source) — never
       listed in a database — that listed sources include
     - Read through **every** entry whose parse includes it, each with its own flags and
       target; a branch is left out only when every one of them leaves it out (see
       :ref:`preprocessor_headers`).
   * - A **header** not listed that no listed source includes
     - Parsed **standalone** using ``defines`` and ``includes`` (see below), for the
       ``target`` setting.
   * - Any file, when **no** database is found
     - Parsed with ``defines`` and ``includes``, for the ``target`` setting.

.. _preprocessor_compile_db:

How the compilation database is applied
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An entry of ``compile_commands.json`` is applied as the build applies it:

- **In its directory.** The entry's ``directory`` is the working directory of its parse,
  so a relative ``-I``, ``-iquote``, ``-isystem``, ``-include`` or ``-imacros`` resolves
  against it, as it did for the compiler, whatever directory the analysis runs in.
  A relative ``directory`` is taken against the directory of the database file.
- **Up to its** ``--``. An entry that ends its options with ``--`` (``-c -- src/a.cpp``)
  is read with the options before it; what follows is its input. A ``--`` that is the
  value of ``-Xlinker``, ``-Xclang`` or another option that hands its argument on, or
  of ``-I``, ``-isystem``, ``-iquote``, ``-idirafter``, ``-isysroot`` or ``-include``,
  ends nothing, and the options after it are read too. Nothing is promised for
  another option whose value is ``--`` (``-x --``, ``-D --``, ``-imacros --``).
- **Through its includes.** A unity (or "jumbo") build compiles one entry whose source
  ``#include``\ s other sources, which then have no entry of their own. Such a source is
  read through its **includer**: an entry whose own source directly includes it.

  - The candidates are found by reading each entry's ``#include "…"`` and
    ``#include <…>`` lines (not those inside a block comment), each name looked up as
    the compiler looks it up: a quoted name next to the including file first, then in
    the entry's ``-iquote`` directories; both forms then in its ``-I`` and then its
    ``-isystem`` directories (joined, ``-Idir``, or separate, ``-I dir``). No other flag
    adds a directory to this search: a source found only through ``-idirafter``,
    ``--include-directory=``, ``-I=`` or ``/I`` has no candidate.
  - The includer is the first candidate, ordered by the path of its source, whose parse
    confirms the inclusion: an ``#include`` in an inactive branch (``#if 0``) does not
    make an includer, nor does one in a header the entry's source includes. An
    ``#include`` the parse cannot find (``<immintrin.h>``, a header not generated yet) is
    passed over. Each entry is parsed once as an includer, and that parse serves every
    source it includes; an entry whose source is traced too is also parsed as its own
    unit.
  - The source's own comments are read from that parse, and a branch is inactive when
    the source's **first** inclusion skips it. So its markers follow the includer's
    ``-D`` flags and whatever its source defines before the ``#include``.

  A compiled source no entry includes is skipped as before, now with one warning naming
  it and the database (``codelinks.not_in_compile_database``, which
  ``suppress_warnings`` can silence). Only direct includes count: a source included by
  a file that is itself included is not read through the entry. Headers are read
  otherwise: through every entry that includes them, at any depth (below).

  The files such a read depends on -- the database, the source of every entry tried as
  its includer and the headers those include (not the system headers) -- are
  dependencies of the ``src-trace`` directive's document, so an edit to a unity file in
  the build directory, outside every traced directory, reads the source again in an
  incremental build; a project no directive traces is analysed again too.

.. _preprocessor_target:

Which target a file is read for
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The target (a clang triple: ``thumbv7em-none-eabihf``, ``x86_64-pc-linux-gnu``) decides
which ``#if`` branches on the architecture, the operating system and the data model a file
compiles (``__arm__``, ``_WIN32``, ``__SIZEOF_LONG__``). libclang does not read a target
from a compile command's compiler: left alone, it reads every file for the machine the
analysis runs on, so an Arm firmware build read on an x86-64 laptop would take its
``#if defined(__x86_64__)`` branches. **Sphinx-CodeLinks** reads the target the build
declares, in this order:

1. The entry's own ``--target=<triple>`` or ``-target <triple>``.
2. The target the entry's compiler's name carries, read as clang's driver reads it:
   ``arm-none-eabi-gcc``, ``aarch64-linux-gnu-g++``, ``riscv64-unknown-elf-gcc-13.2.0`` or
   ``thumbv7em-none-eabihf-clang`` name the target before their last ``-gcc``, ``-g++``,
   ``-cc``, ``-c++``, ``-clang`` or ``-clang++``, with or without a directory, a version or
   ``.exe``, and behind a launcher such as ``ccache``. As in clang's driver, the name
   counts only when its first part is an architecture the loaded libclang has (``arm``,
   ``aarch64``, ``riscv64``, ``powerpc``, ``x86_64``, ...): a wrapper's name such as
   ``my-arm-gcc``, ``musl-gcc`` or ``afl-clang-fast`` names no target. The entry's own
   flags then refine the target as the compiler does (``-mcpu=cortex-m3 -mthumb``).
3. The ``target`` setting of :ref:`analyse.preprocessor <preprocessor_config>`.
4. Otherwise the machine the analysis runs on. A native compiler (``gcc``, ``cc``,
   ``c++``, ``clang``, ``/usr/bin/c++``) names no target, so a native build is read for
   the machine reading it: right when the database was written on a machine of the same
   kind, wrong for a database written for another architecture or operating system at the
   same paths (a Linux build's database read on Windows takes its ``_WIN32`` branches).
   Set ``target`` when that is the case.

A header an entry includes is read for the target of each entry that includes it
(:ref:`preprocessor_headers`). A header no entry includes, and a file no entry applies to,
has no entry to read a target from: it is read for the ``target`` setting, else for the
machine the analysis runs on. A source read through the entry that includes it is read
for that entry's target.

A target the loaded libclang cannot parse for is not used, and a build or a
``codelinks analyse`` run warns at the file's first line
(``codelinks.preprocessor_target_unknown``), naming the target, where it came from, and
how the file is read instead. When no other target is the build's, the file's target is
unknown, and the file is **read as written**: no ``#if`` branch is left out, and every
comment's markers are kept. Nothing is hidden, but it is less precise: a marker in a
branch the build does not compile is extracted too, so a definition written once in each
of two exclusive branches (``#ifdef A`` … ``#else`` …) looks like one, carrying the markers
of both. The warning comes once per such file; to accept it, add
``codelinks.preprocessor_target_unknown`` to Sphinx's ``suppress_warnings``, or set
``target`` to a triple the loaded libclang models, where the file takes the setting and
such a triple fits.

- an entry's own ``--target`` or ``-target`` naming one (``xtensa-esp32-elf``,
  ``tricore-elf``) is left out of the parse, and the file is read as written (the
  ``target`` setting does not override what the entry declares, and is not used);
- a compiler's name whose first part is an architecture libclang does not have, but whose
  rest it reads as a vendor, an operating system or an environment
  (``xtensa-esp32-elf-gcc``, ``tricore-elf-gcc``, ``sh-elf-gcc``: ``elf``), names a target
  it cannot read: the file is read as written (the ``target`` setting does not override
  it either); by the same rule a wrapper whose name's rest is a system word
  (``my-linux-gcc``) names one too, and is read as written;
- a ``target`` setting naming one is not used: a file that would take it is read as
  written;
- a target that clang refuses with the entry's own flags (a CPU or an ABI GCC knows and
  clang 18 does not, such as ``-mcpu=e200z4``, ``-mcpu=cortex-r52plus``,
  ``-mcpu=cortex-x925`` or ``-mabi=lp64`` for ``aarch64-linux-gnu``, or RISC-V's
  ``-march=rv32imac_zicsr`` for the machine the analysis runs on, in a build that names
  no target; xPack's ``riscv-none-elf-gcc`` names one, ``riscv``, an architecture
  libclang does not have without its width, so it is read as written instead) is kept,
  whatever its source, and the file is read
  for it without the entry's ``-mcpu=``, ``-march=``, ``-mtune=`` and ``-mabi=``, that
  is, for the architecture's default CPU;
- a declared target (the entry's own, its compiler's name's or the setting's) that clang
  refuses without those flags too, because of another of the entry's flags (``-mcmse``
  with ``arm-none-eabi``), is dropped for that file, which is read as written; the
  warning says the target was refused with the entry's flags and lists its ``-m`` flags
  (libclang does not say which one it refused), and, when the setting named it, gives as
  the remedy a ``target`` that clang accepts with the entry's flags.

A declared target never leaves a file unread that would be read without it, whatever the
machine the analysis runs on: a refused parse is made again without the entry's
``-mcpu=``, ``-march=``, ``-mtune=`` and ``-mabi=``, then without the target and them,
for the file's comments only (it is read as written). A file whose target is unknown is
never skipped: when clang refuses even that parse, because of another of its flags
(``-mfpmath=vfp``, which clang refuses for every machine the analysis runs on), it is
read as written by the tree-sitter engine, every comment's markers kept, attached to no
entity as under the libclang engine, so with the same findings as a parse read as
written (no ``codelinks.marker_above_conditional``, which only a marker attached by the
tree-sitter engine can get). A source with no entry of its own that such an entry
``#include``\ s is read as written too, through that entry, whatever ``#if`` branch its
``#include`` line is in, unless an entry whose target **Sphinx-CodeLinks** reads
includes it in a branch that entry compiles: that one reads it, for its target.

A file whose target is known is never skipped either. When clang refuses every parse of
it, no parse decides a branch, so it is read as written by the tree-sitter engine, as a
file whose target is unknown is, and a build or a ``codelinks analyse`` run warns at the
file's first line (``codelinks.preprocessor_parse_refused``), once per such file. Two
kinds of refusal are told apart, by what libclang reports:

- a flag of its own that clang does not take for the target it reads (a native build's
  ``-mfpmath=sse`` on an Arm64 machine, or ``-mfpmath=vfp`` on every machine; its
  ``-mcpu``, ``-march``, ``-mtune`` and ``-mabi`` are left out first): the warning names
  the target it was parsed for (the machine the analysis runs on, for a build that names
  none), whose flags they are (its entry's, its includer's entry's, or the
  ``[preprocessor]`` table's), their ``-m`` flags and the ``-mcpu``, ``-march``,
  ``-mtune`` and ``-mabi`` left out (libclang does not say which flag it refused);
- its arguments, whatever the target: an input file besides the file itself (a
  compile-and-link entry, ``gcc main.c util.c -o app``), or an argument clang does not
  take, such as a ``-std`` it does not know (``-std=gnu2y`` from a newer GCC, or a
  ``std`` in the ``[preprocessor]`` table for a header) or a PGO profile that has moved
  (``-fprofile-use=`` naming a file that is not there). The warning names whose
  arguments they are, lists them (at most twelve, the rest counted; not the working
  directory and builtin-header directory **Sphinx-CodeLinks** adds, nor a target it
  inserted), and names the other input files among them. A target the build declares
  (``arm-none-eabi-gcc -std=gnu2y``) is named too: clang refused its command, not the
  target, so such a file gets this warning rather than
  ``codelinks.preprocessor_target_unknown``.

The remedy is to remove or change what clang refused in the compilation database (or in
the ``[preprocessor]`` table, for a file no entry applies to), or to accept the file read
as written by adding ``codelinks.preprocessor_parse_refused`` to Sphinx's
``suppress_warnings``. A source with no entry of its own that such an entry
``#include``\ s is confirmed by that entry's ``#include`` lines and read as written
through it, with the same warning naming that includer, unless an entry whose parse
reads includes it in a branch that entry compiles: that one reads it, for its target.

.. _preprocessor_headers:

Header files
~~~~~~~~~~~~~

A ``compile_commands.json`` only ever lists compiled translation units (``.cpp`` files);
headers are pulled in via ``#include`` and never appear as entries. **Sphinx-CodeLinks**
reads a header the database does not list through **every entry that includes it**: each
entry of the header's database (of every database the project's other files find, when
none is found above the header) whose own parse includes the header, directly, through
other headers, through a macro ``#include`` or a ``-include``, whatever directory the
entry's source is in, and whatever directory finds the header (one of the project's on
an ``-isystem`` or ``-idirafter`` path counts too, though clang calls it a system
header). A file is the project's when its path is under the project's root, as resolved
or as the compiler names it: a project directory that is a symbolic link to elsewhere
counts (though discovery itself lists no file that resolves outside ``src_dir``, so such a
header reaches the analysis only when a caller names it). Each such entry reads the header with its own flags, its own target,
and whatever its source defines before the ``#include``, in the header's **first**
inclusion into it; a file the database compiles twice counts twice.

A branch of the header is left out only when **every** one of those entries leaves it out,
so a header both an Arm and an x86 entry include keeps the branches of both, and a branch
none of them compiles (``#ifdef NEVER_SET``) is still left out. Three kinds of entry read
the header as written, and with one of them no branch of the header is left out:

- one that enters the header again and compiles some of it then (an X-macro header included
  twice, or a whole-file ``#ifndef`` whose macro nothing defines); a guarded header entered
  again, whose second entry skips its whole body, is read in its first inclusion;
- one whose target is unknown (:ref:`preprocessor_target`), and one whose every parse
  clang refuses: no parse decides their branches, so every file their forced includes
  and their ``#include`` and ``#include_next`` lines name, at any depth and whatever
  ``#if`` branch the line is in, counts as included (also through a file outside the
  project, such as an SDK header that includes a project one). The names are looked up
  as the compiler looks them up (see :ref:`below <preprocessor_header_spellings>`), and an
  ``#include_next`` continues after the directory that found its file, each directory
  once (one listed again, or a symbolic link to an earlier one, is passed over, as clang
  passes it over); in a file found on no search directory, it is looked up as an
  ``#include``. The units of one analysis share what they read and look up, so a large
  include path over many headers is walked once per path.

The header's comments are read from one of the entries whose target is known (the one that
includes the most project files, the first by the path of its source among equals),
parsed once more for every header it reads. When none is known, the header is read as
written by the tree-sitter engine, with the warning the first such entry's includer would
get (``codelinks.preprocessor_target_unknown`` or ``codelinks.preprocessor_parse_refused``);
so is a header whose reading entry clang refuses when it is parsed again (a file changed
in between), with that entry's warning.
When an entry is read for its target without the ``-mcpu=``, ``-march=``, ``-mtune=`` or
``-mabi=`` clang refused, and every entry leaves out branches of the header, the header gets
the same ``codelinks.preprocessor_target_unknown`` warning as that entry's source, worded
for its includer: those flags decide branches it leaves out.

A header **no entry includes** is parsed **standalone**, using the ``defines`` and
``includes`` you configure, for the ``target`` setting, and leaves out only the branches
that configuration decides (:ref:`preprocessor_no_includer`). Every file when no database
is found is parsed the same way, every branch its parse skips left out: there the
``defines`` are the build's own configuration. Include guards resolve correctly, and
``#ifdef`` branches are evaluated against your ``defines``.

The files a header's read depends on -- the database, the source of every entry and the
project files each includes -- are dependencies of the ``src-trace`` directive's document,
so an edit to one of them reads the header again in an incremental build. What each entry
contributes is kept in the Sphinx environment between builds, so an entry is parsed again
only when its source or a project file it includes changes (or its flags, the loaded
libclang or the database do).

.. note:: A header no entry includes sees only the global ``defines`` — **not** the
   per-file ``-D`` flags from ``compile_commands.json``. A branch on a macro ``defines``
   does not state is read whatever the build does with it; to leave out what a
   particular variant leaves out, mirror that variant into ``defines``. Treat one
   analysis run as **one variant**: set ``defines`` to the variant you want, and both
   sources and headers evaluate their conditions consistently.

What can still hide code in a header:

- a header no entry includes is read with the ``defines`` and ``target`` you configure:
  a branch on a macro ``defines`` states with another value than the build's, or on the
  target's identity when ``target`` is not the build's effective triple, is left out as
  they decide it, and so is one on a target macro another header ``#undef``\ s;
- an include guard undefined between two inclusions (``#undef FOO_H`` and an
  ``#include`` again) leaves a second entry that compiles the body again; the header is
  read as written then, but a header given both by ``-include`` and ``#include`` is
  entered once;
- a header that a file includes only through a ``#include`` of a computed name, in a
  branch of a target the loaded libclang cannot read, is not seen as included;
- a header another one newly shadows on an include path is seen when an entry is read
  again (its source or a project file it includes changes);
- a source file the database compiles twice, with other flags, is read with its last
  entry (a header it includes is read through both);
- a header that an entry whose target is unknown, or whose every parse is refused,
  finds only through ``-iframework`` (a framework's headers are named
  ``<Name/header.h>`` and live in ``Name.framework/Headers``) is not seen as included.

.. _preprocessor_header_spellings:

The flags an entry whose branches no parse decides is read for, each joined
(``-Iinc``) or separate (``-I inc``), each kind in the order the entry gives it:

- the include path, searched in this order: ``-iquote`` (a quoted name only, after the
  including file's own directory); then ``-I``, clang-cl's ``/I``,
  ``--include-directory`` (``=`` or separate) and ``-iwithprefixbefore``; then
  ``-isystem``, ``-cxx-isystem``, ``-iwithsysroot``, and clang-cl's ``/imsvc``
  (``-imsvc``) and ``/external:I`` (``-external:I``); then ``-idirafter``, ``--include-directory-after`` (``=`` or separate),
  ``-isystem-after`` and ``-iwithprefix``, last. A directory that starts with ``=`` is
  under the sysroot (``-isysroot``, else ``--sysroot``), as is every ``-iwithsysroot``
  one; an ``-iwithprefix`` or ``-iwithprefixbefore`` directory follows the last
  ``-iprefix`` before it (a plain string prefix); any other relative directory is taken
  against the entry's ``directory``. ``-iframework`` is not read;
- the forced includes, ahead of the source's own lines: ``-include``, ``--include``
  (``=`` or separate), ``-imacros`` and clang-cl's ``/FI`` (``-FI``), looked up in the
  entry's ``directory`` first, then on the include path; never ``-include-pch`` or
  another ``-include-*`` or ``--include-*`` flag.

.. _preprocessor_no_includer:

A header no entry includes
~~~~~~~~~~~~~~~~~~~~~~~~~~

Its parse is not the build's: the build may compile it with a ``-D`` the ``defines`` do
not state, or for a target the ``target`` setting does not name. So of the branches its
parse skips, only one whose whole ``#if`` chain the configuration **decides** is left out,
and every other branch is read as written, markers and all. A chain is decided up to its
first condition that is not, and an ``#elif`` or ``#else`` after a branch decided and
taken is decided too. A condition is decided when every name it reads is:

- a macro ``defines`` states (``-D``), whose value is decided in turn: ``"A=B"`` with
  ``B`` unstated leaves ``#if A`` undecided, while ``#ifdef A`` and ``defined(A)`` read only
  that ``A`` is defined;
- with the ``target`` setting stated, a macro of the target's **identity**: its
  architecture, operating system, object format and byte order (``__arm__``,
  ``__x86_64__``, ``__linux__``, ``_WIN32``, ``__ELF__``, ``__BYTE_ORDER__``), which GCC and
  clang set alike for one effective triple whatever the other flags, and the
  **definedness** alone of the data model (``#ifdef __LP64__`` is decided,
  ``#if __SIZEOF_LONG__ == 8`` is not). Without the setting the target is a guess (the
  machine the analysis runs on), and none of them decides;
- a literal (``#if 0``, ``#if (2 + 3) * 4 > 30``), and ``__has_include`` of a header name
  (``<a.h>``, ``"a.h"``): the ``includes`` you configure say what is found. Of a macro
  (``__has_include(CFG_HDR)``), as the macro is.

Never decided: a macro the header itself ``#define``\ s or ``#undef``\ s (``defines``
or not); a macro a build passes (``__ZEPHYR__``, ``_DEBUG``, ``NDEBUG``); the compiler's
identity (``__clang__``, ``__GNUC__``: libclang is clang, the build's compiler may not be,
and clang's own ``__LITTLE_ENDIAN__`` and ``__ILP32__`` with it); what another flag
decides (``__thumb__``, ``__ARM_ARCH``, ``__OPTIMIZE__``); the language
(``__cplusplus``, ``__STDC_VERSION__``); clang's other ``__has_*`` tests; and a condition
the scan cannot read (a string). The directives are read from the header's text, through
line splices, comments, string literals and the ``%:`` digraph.

When such a header has a branch read for a condition the configuration does not decide,
the build (or ``codelinks analyse``) prints one information line per compilation
database, at its first line, naming the headers (at most five, relative to the
database's directory) and counting the branches:

.. code-block:: text

   build/compile_commands.json:1: codelinks: 1 header that no entry of this compilation
   database includes is read with the `[preprocessor]` table, and 2 `#if` arms on a
   condition the table does not decide are read as written rather than left out:
   `../src/orphan.h`. To leave out what the build leaves out, state the macros in
   `[preprocessor] defines` and the target in `target`, or include it from an entry's
   file. [codelinks.preprocessor_no_includer]

It is not a warning: it can over-report, never hide, so a ``-W`` build does not fail on
it, and it needs no ``suppress_warnings``. To read such a header as the build does, state
the macros in ``defines`` and the build's **effective** triple in ``target`` (a ``-m32``,
``-mx32``, ``-mbig-endian``, ``-EB``, ``-EL`` or ``-mabi=`` changes it), or include the
header from a file the database compiles. The rule and its two lists of target macros
are ubCode's (its ``codelinks.preprocessor_no_includer`` finding), so the two read the
same branches.

Example
~~~~~~~

.. code-block:: cpp

   // include/feature.hpp
   #ifndef FEATURE_HPP
   #define FEATURE_HPP

   // @Always available, IMPL_BASE, impl, [REQ_BASE]
   void base();

   #ifdef VARIANT_A
   // @Variant A only, IMPL_VAR_A, impl, [REQ_A]
   void variant_a();
   #endif

   #endif

When no entry includes it, with ``defines = ["VARIANT_A"]`` both ``IMPL_BASE`` and
``IMPL_VAR_A`` are extracted, and with ``defines = []`` both are extracted too: nothing
states ``VARIANT_A``, so its ``#ifdef`` block is read, and the information line names the
header. With no compilation database at all, ``defines = []`` extracts only ``IMPL_BASE``
— the ``#ifdef VARIANT_A`` block is inactive, so its need is dropped. When an entry built
with ``-DVARIANT_A`` includes it, ``IMPL_VAR_A`` is extracted whatever ``defines`` says. The include guard (``#ifndef FEATURE_HPP``) is always
active when the header is parsed on its own, so ``IMPL_BASE`` is never suppressed by it,
even when one of the header's own includes includes it back.

.. _preprocessor_builtin_headers:

Builtin headers
~~~~~~~~~~~~~~~

Some standard headers come with the compiler rather than with the C library:
``stddef.h``, ``stdarg.h``, ``stdbool.h``, ``float.h``, ``stdatomic.h``, the compiler's half
of ``limits.h``, and ``stdint.h`` where no C library is on the search path (a bare-metal
target). The ``libclang`` wheel carries none of them, so **Sphinx-CodeLinks** ships clang
18's 30 portable builtin headers and passes them to every parse as ``-resource-dir``.
Without them an ``#if`` on what they define (``UINT32_MAX``, ``INT_MAX``,
``__has_include(<stdatomic.h>)``, ``bool``) would take the branch the compiler does not
take. Each parse is given the first of:

1. the ``resource_dir`` of :ref:`analyse.preprocessor <preprocessor_config>`, when set;
2. nothing, when its ``compile_commands.json`` entry already chooses, as the clang driver
   reads it (``-resource-dir``, ``-nostdinc`` or ``-nobuiltininc``; also after
   ``-Xarch_host``, or ``-Xarch_<arch>`` for the architecture of an Apple target, but not
   after an option that hands it to another tool, such as ``-Xclang``);
3. the headers that ship with **Sphinx-CodeLinks**, read where the package is installed;
4. nothing, when those are not all on the filesystem (the package was imported from an
   archive, or some of the files were removed); a build, or a ``codelinks analyse`` run,
   then warns once.

Compiler intrinsics (``immintrin.h``, ``arm_neon.h`` …) and clang's other builtin headers
(``cpuid.h``, ``unwind.h``, compiler-rt's ``sanitizer/`` headers …) are not shipped. If a
parse still cannot find a header a full clang install puts in its resource directory,
included in angle brackets (``#include <cpuid.h>``; ``#include "cpuid.h"`` names a header
of the project, and an include written through a macro, ``#include HDR``, is not warned
about), or by the compile command itself (``-include immintrin.h``), **Sphinx-CodeLinks** warns once per file in a build or a
``codelinks analyse`` run, naming the header (``codelinks.builtin_header``, which fails a
``-W`` build), and continues: ``#if`` tests on what that header defines take their
``#else`` branch. When the entry itself leaves clang's headers out (``-nostdinc``,
``-nobuiltininc``), the warning names that flag instead: no ``resource_dir`` brings them
back. Under ``-j N`` Sphinx reads the documents in chunks, each in a process
of its own, and each chunk warns once. To use your own clang's headers, set
``resource_dir`` to the output of ``clang -print-resource-dir``.

The shipped headers are clang's own, under the Apache License v2.0 with LLVM Exceptions;
the licence is installed beside them (``sphinx_codelinks/analyse/preproc/clang_resource/``).

Variant handling is the caller's job
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Which preprocessor branches are active — and therefore which need markers are in
scope — is decided entirely by the ``-D`` macros libclang sees (from
``compile_commands.json`` for a compiled source and the headers its entries include, or
from ``defines`` for headers no entry includes and the standalone path). **Sphinx-CodeLinks** does not model, generate, or
reconcile build variants itself.

For the result to be meaningful, the macros fed to the extractor and the macros
that select the variant in the code must come from the **same source of truth** —
whatever drives your variant management (Kconfig, pure::variants, a home-grown
generator). Generate the ``compile_commands.json`` / ``defines`` for one variant
from that source, run the analysis once, and the extracted markers are exactly
the ones active in that variant. Keeping the inputs consistent is the caller's
responsibility.

Limitations
~~~~~~~~~~~

The command line of a ``compile_commands.json`` entry is parsed for Clang/GCC-style
flags (``-D``, ``-I``, ``-std=`` …). MSVC ``cl.exe`` slash-style flags (``/D``,
``/I``, ``/std:`` …) are **not** recognised, so a database generated for the MSVC
compiler driver yields no defines or include dirs. Generate the database with
``clang`` / ``clang-cl`` (which emit Clang-style flags) for use with this engine.

The target is read exactly as the build declares it (:ref:`preprocessor_target`), but
these still differ from the compiler's read with the right target, so check them by hand
where a marker your build compiles is missing:

- **the compiler's identity**: libclang is clang, and defines ``__clang__`` and
  ``__GNUC__`` as ``4`` on every target, where GCC 13 defines ``__GNUC__`` as ``13`` and
  no ``__clang__``, so an ``#if __GNUC__ >= 7`` or ``#ifdef __clang__`` takes the other
  branch for a GCC build;
- **the sub-architecture defaults**: with no ``-mcpu`` or ``-march`` in the entry, clang's
  ``arm-none-eabi`` is an older Arm architecture than the one a GCC configured
  ``--with-cpu`` or ``--with-arch`` defaults to, so an ``#if __ARM_ARCH < 5`` can take the
  other branch (an entry that passes ``-mcpu``, as Zephyr's do, is exact);
- **a CPU or ABI clang does not know**: a file whose ``-mcpu``, ``-march``, ``-mtune``
  or ``-mabi`` clang refuses with its target (``-mcpu=e200z4``, ``-mcpu=cortex-r52plus``)
  is read for the architecture's default sub-architecture, without them, with a
  ``codelinks.preprocessor_target_unknown`` warning; all four are left out when one is
  refused, so an accepted ``-march`` goes with a refused ``-mabi``
  (``-march=armv8.2-a+crypto -mabi=lp64`` for ``aarch64-linux-gnu`` loses
  ``__ARM_FEATURE_AES``);
- **headers**: a header no entry includes, and a file no entry applies to, is read for the
  ``target`` setting, else the machine the analysis runs on (a header an entry includes is
  read for the target and flags of every entry that includes it,
  :ref:`preprocessor_headers`); of a header no entry includes, a branch on a target macro
  is left out only when ``target`` is set and the macro is one of the target's identity
  (:ref:`preprocessor_no_includer`);
- **response files** (``@args.rsp``): libclang does not read them, so a ``--target``,
  ``-mcpu`` or ``-D`` inside one is not read;
- **the type macros**: clang's ``arm-none-eabi`` makes ``__INT32_TYPE__`` an ``int``,
  newlib GCC targets a ``long int``;
- **the cross toolchain's own system headers**: a GCC cross compiler finds its C library
  implicitly, and the compilation database does not list it, so ``<stdio.h>`` for an
  ``arm-none-eabi`` file is not found (and a newlib or picolibc macro is undefined) unless
  the entry passes ``--sysroot`` or ``-isystem`` (Yocto, Buildroot and Zephyr's do);
- **the machine a native build is read for**: an entry of ``gcc``, ``cc``, ``c++`` or
  ``clang`` names no target, so its file is read for the machine the analysis runs on,
  which is wrong for a database written for another architecture or operating system at
  the same paths (an x86-64 and an Arm64 CI runner sharing ``/home/runner/work``, or a
  Linux build's database read on Windows): set the ``target`` setting then;
- **a cross compiler whose name carries no triple** (HighTec's ``tricore-gcc``, Xilinx's
  ``mb-gcc``, Microchip's ``xc32-gcc`` and ``xc16-gcc``, IAR's ``iccarm``): its file is
  read for the machine the analysis runs on, as a native compiler's is: set the
  ``target`` setting for it.

A file whose target is unknown hides no marker, but loses precision: an entry's own
``--target=xtensa-esp32-elf``, a compiler whose name carries such a target
(``xtensa-esp32-elf-gcc``), a ``target`` setting naming one for a file that takes it, or
a declared target clang refuses with the entry's flags even without its ``-mcpu``,
``-march``, ``-mtune`` and ``-mabi`` (``-mcmse`` with ``arm-none-eabi``) leaves the file
read as written, with a ``codelinks.preprocessor_target_unknown`` warning: the markers
of every branch of every ``#if`` are extracted, those of the ``#ifdef CONFIG_X``
branches the build does not compile among them, and none is lost. So is a file whose
every parse clang refuses, because of a flag of its own (``-mfpmath=vfp``) or because
of its command (a second input file, a ``-std`` clang does not know), and a source such
an entry includes, with a ``codelinks.preprocessor_parse_refused`` warning.
