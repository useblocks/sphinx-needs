"""The code a marker is attached to: what counts as an entity, and how one is named.

A marker is attached to a definition node of the syntax tree (a function, a class,
a namespace, ...): its *entity*. This module holds the per-language tables that say
which node kinds are entities, and the one naming function, :func:`describe_entity`,
that turns such a node into its kind, its qualified name *within its file* (no
module or package prefix: that is derived from the file's path, which this module
never reads -- every function here is pure) and that name's components, its
``semantic``. :func:`render_semantic` joins the components back into the name by the
rule of the file's language (:func:`scope_language`), and :func:`name_chain` is what
identifies an entity among them: names, never kinds.

The traversal that picks the node for a comment is ``find_associated_scope`` /
``associate`` in :mod:`sphinx_codelinks.analyse.utils`; this module only answers
questions about a node.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import PurePath
from typing import Literal, NotRequired, TypedDict

from tree_sitter import Node as TreeSitterNode

from sphinx_codelinks.analyse.cpp_macros import MacroScopes
from sphinx_codelinks.source_discover.config import CommentType

EntityKind = Literal[
    "function",
    "method",
    "constructor",
    "destructor",
    "operator",
    "class",
    "struct",
    "union",
    "enum",
    "interface",
    "trait",
    "impl",
    "record",
    "namespace",
    "module",
    "type",
    "macro",
    "property",
    "event",
    "indexer",
    "delegate",
    "key",
    "item",
]
"""The kind of an entity, as the analysis output spells it."""

Mechanism = Literal["doc_comment", "leading", "trailing", "enclosing"]
"""How a marker came to be attached to its entity.

``doc_comment`` is *declared*: a documentation comment (``///``, ``//!``, ``/**``,
``/*!``, a C# ``///``, a JSDoc ``/**``, a Python docstring) attached by its own rule.
The other three are *inferred* from where a plain comment sits: on the lines before the
entity (``leading``), after code on the entity's own line (``trailing``), or inside its
body (``enclosing``).
"""


class SemanticElement(TypedDict):
    """One component of an entity's qualified name: a container, or the entity."""

    kind: str
    """What it is: an :data:`EntityKind`, or ``scope`` for a C++ qualifier the syntax
    cannot classify (the ``ns`` of ``void ns::W::f() {}``). A Rust impl is an
    ``impl``, a Go receiver's type a ``type``."""
    name: str
    """Its name, as the qualified name spells it: ``Box<bool>`` keeps the arguments of
    an explicit specialisation, an expression name (``module.exports.f``) is whole,
    and a Rust impl is its self type (``Widget``, ``dyn Shape``)."""
    trait: NotRequired[str]
    """The trait of a Rust trait impl, on its ``impl`` component."""


@dataclass(frozen=True)
class EntityName:
    """A definition node, named."""

    kind: EntityKind
    """What the node defines."""
    qualified_name: str | None
    """The name within its file, qualified by the containers the file shows
    (``ns::Widget::draw``, ``Shape.area``, ``<Widget as Shape>::area``); ``None`` when
    the entity has no name (an anonymous class, a data-file entry)."""
    semantic: tuple[SemanticElement, ...] | None
    """``qualified_name`` as its components, outermost first and the entity last
    (``namespace ns``, ``class Widget``, ``method draw``); ``None`` exactly when
    ``qualified_name`` is. :func:`render_semantic` spells them back."""
    name_end: int | None = field(default=None, compare=False, repr=False)
    """The byte offset where the node's own name ends in the file (C and C++ only),
    ``None`` when it has no name node: what the names a whole C++ file decides are
    keyed by (:class:`CppNames`). Not part of the analysis output."""


@dataclass(frozen=True)
class Association:
    """The node a comment is attached to, and how."""

    node: TreeSitterNode
    mechanism: Mechanism


class CodeScope(TypedDict):
    """The ``scope`` object of an analysis record: the entity a marker is attached to."""

    kind: str
    """The tree-sitter node kind of the entity (``function_definition``)."""
    start: int
    """The node's first line (1-based)."""
    end: int
    """The node's last line (1-based)."""
    language: str
    """The file's language (:func:`scope_language`): the rule ``semantic`` renders by."""
    entity_kind: str | None
    """The entity's kind (:data:`EntityKind`), ``None`` if it could not be named."""
    qualified_name: str | None
    """The entity's in-file qualified name, ``None`` if it has none."""
    semantic: list[SemanticElement] | None
    """The qualified name's components (:class:`SemanticElement`), outermost first and
    the entity last; ``None`` exactly when ``qualified_name`` is."""
    mechanism: Mechanism
    """How the marker was attached (:data:`Mechanism`)."""


# ---------------------------------------------------------------------------
# What is an entity: the node kinds a marker can be attached to
# ---------------------------------------------------------------------------
#
# YAML and JSONC are intentionally absent. They are data formats, not code, so a
# comment associates with the surrounding data structure (key/value pair, list
# item, or scalar) rather than with an enclosing or following declaration. That
# needs a different algorithm (inline same-row association first, scalar targets,
# grammar-specific traversal), implemented in find_yaml_associated_structure and
# find_jsonc_associated_structure and dispatched from find_associated_scope.
# Those bespoke finders never read this table, so an entry here would be dead.
#
# Deliberately no entities yet: data members and variables, Python assignments
# (a lambda bound to a name included), Rust ``const``/``static``, Go ``var``/``const``,
# TypeScript plain consts, and macro invocations. A marker above one of them is
# attached to the enclosing entity, or to the file.
ENTITY_NODE_TYPES: dict[CommentType, set[str]] = {
    # @Python Scope Node Types, IMPL_PY_2, impl, [FE_PY]
    CommentType.python: {"function_definition", "class_definition"},
    # @C and C++ Scope Node Types, IMPL_C_2, impl, [FE_C_SUPPORT, FE_CPP]
    # A declaration, a field declaration, a class, struct, union or enum is an entity
    # only when its predicate holds: see ENTITY_PREDICATES.
    CommentType.cpp: {
        "function_definition",
        "declaration",
        "field_declaration",
        "class_specifier",
        "struct_specifier",
        "union_specifier",
        "enum_specifier",
        "namespace_definition",
    },
    CommentType.cs: {
        "method_declaration",
        "class_declaration",
        "property_declaration",
        "constructor_declaration",
        "destructor_declaration",
        "struct_declaration",
        "interface_declaration",
        "enum_declaration",
        "record_declaration",
        "operator_declaration",
        "conversion_operator_declaration",
        "indexer_declaration",
        "delegate_declaration",
        "event_declaration",
        "local_function_statement",
        "namespace_declaration",
        "file_scoped_namespace_declaration",
    },
    # @TypeScript Scope Node Types, IMPL_TS_2, impl, [FE_TS]
    # The last five are scopes only when they hold a function or a class: see
    # ENTITY_PREDICATES.
    CommentType.ts: {
        "function_declaration",
        "generator_function_declaration",
        "function_signature",
        "class_declaration",
        "abstract_class_declaration",
        "interface_declaration",
        "type_alias_declaration",
        "enum_declaration",
        "module",
        "internal_module",
        "method_definition",
        "method_signature",
        "abstract_method_signature",
        "lexical_declaration",
        "variable_declaration",
        "public_field_definition",
        "assignment_expression",
        "export_statement",
    },
    # @Rust Scope Node Types, IMPL_RUST_2, impl, [FE_RUST]
    CommentType.rust: {
        "function_item",
        "function_signature_item",
        "struct_item",
        "enum_item",
        "union_item",
        "impl_item",
        "trait_item",
        "mod_item",
        "type_item",
        "macro_definition",
    },
    # @Go Scope Node Types, IMPL_GO_4, impl, [FE_GO]
    CommentType.go: {
        "function_declaration",
        "method_declaration",
        "type_declaration",
        "type_spec",
        "method_elem",
    },
    # @Bash Scope Node Types, IMPL_BASH_2, impl, [FE_BASH]
    CommentType.bash: {"function_definition"},
}
SCOPE_NODE_TYPES = ENTITY_NODE_TYPES
"""The name this table had before entities were named; kept for importers."""

# What a TypeScript declaration's value can be wrapped in without changing what it
# is: ``(() => {}) as Handler``, ``<Handler>(() => {})``, ``f!``, ``x satisfies T``.
TS_VALUE_WRAPPER_TYPES = {
    "parenthesized_expression",
    "as_expression",
    "satisfies_expression",
    "non_null_expression",
    "type_assertion",
}
# The values that make a declaration a scope.
TS_FUNCTION_VALUE_TYPES = {
    "arrow_function",
    "function_expression",
    "generator_function",
    "class",
}


def _unwrap_ts_value(value: TreeSitterNode | None) -> TreeSitterNode | None:
    """``value`` seen through the wrappers of :data:`TS_VALUE_WRAPPER_TYPES`."""
    while value is not None and value.type in TS_VALUE_WRAPPER_TYPES:
        children = value.named_children
        if not children:
            return None
        # ``<T>x`` names its type first, every other wrapper its expression
        value = children[-1] if value.type == "type_assertion" else children[0]
    return value


def _is_function_like(value: TreeSitterNode | None) -> bool:
    """True if ``value``, seen through its wrappers, is a function or a class."""
    value = _unwrap_ts_value(value)
    return value is not None and value.type in TS_FUNCTION_VALUE_TYPES


def _declares_function(node: TreeSitterNode) -> bool:
    """A ``const``/``let``/``var`` declaration one of whose declarators is a function,
    or one declared with ``declare`` (``declare const x: T``), which holds no value and
    is the declared thing itself. Only the ``declare``-prefixed form: a variable inside a
    ``declare namespace``, ``module`` or ``global`` body, or a bare ``export const x: T;``
    in a ``.d.ts``, is no entity."""
    if node.parent is not None and node.parent.type == "ambient_declaration":
        return True
    return any(
        _is_function_like(declarator.child_by_field_name("value"))
        for declarator in node.named_children
        if declarator.type == "variable_declarator"
    )


def _value_is_function(node: TreeSitterNode) -> bool:
    """A class field (``handler = () => {}``) or a default export of a function or class."""
    return _is_function_like(node.child_by_field_name("value"))


def _assigns_function(node: TreeSitterNode) -> bool:
    """An assignment of a function, as ``module.exports = function () {}`` is."""
    return _is_function_like(node.child_by_field_name("right"))


# The declarators a function declarator can be wrapped in: ``int *f();``,
# ``int &f();``, ``int f [[nodiscard]] ();``.
_CPP_DECLARATOR_WRAPPERS = {
    "pointer_declarator",
    "reference_declarator",
    "attributed_declarator",
}


def _cpp_operator_cast(node: TreeSitterNode) -> TreeSitterNode | None:
    """The ``operator_cast`` a conversion operator's declarator is, or ends in
    (``operator bool() const``, ``ns::W::operator bool() const``)."""
    declarator = node.child_by_field_name("declarator")
    while declarator is not None and declarator.type == "qualified_identifier":
        declarator = declarator.child_by_field_name("name")
    return (
        declarator
        if declarator is not None and declarator.type == "operator_cast"
        else None
    )


def _cpp_declares_function(node: TreeSitterNode) -> bool:
    """The declarator chain reaches a function declarator: ``int f(int);``, not the
    variable ``int x;`` nor the function pointer ``int (*fp)(int);``. A conversion
    operator (``operator bool() const;``) declares a function too."""
    if _cpp_operator_cast(node) is not None:
        return True
    declarator = node.child_by_field_name("declarator")
    for _ in range(8):
        if declarator is None:
            return False
        if declarator.type == "function_declarator":
            inner = declarator.child_by_field_name("declarator")
            return inner is not None and inner.type != "parenthesized_declarator"
        if declarator.type not in _CPP_DECLARATOR_WRAPPERS:
            return False
        declarator = declarator.child_by_field_name("declarator") or (
            declarator.named_children[-1] if declarator.named_children else None
        )
    return False


def in_function_body(node: TreeSitterNode) -> bool:
    """Whether the C or C++ ``node`` is inside a function's body (a compound statement,
    a lambda's included)."""
    parent = node.parent
    while parent is not None:
        if parent.type == "compound_statement":
            return True
        parent = parent.parent
    return False


def _cpp_prototype(node: TreeSitterNode) -> bool:
    """A function prototype outside a function body: inside one, ``SDLoc dl(Op);`` is a
    local variable that merely parses like a prototype."""
    return _cpp_declares_function(node) and not in_function_body(node)


def _cpp_has_body(node: TreeSitterNode) -> bool:
    """A class, struct, union or enum with a body: ``struct Foo;`` declares no entity."""
    return node.child_by_field_name("body") is not None


# Entity node types that are an entity only when their predicate holds, per language.
ENTITY_PREDICATES: dict[CommentType, dict[str, Callable[[TreeSitterNode], bool]]] = {
    CommentType.cpp: {
        "declaration": _cpp_prototype,
        "field_declaration": _cpp_declares_function,
        "class_specifier": _cpp_has_body,
        "struct_specifier": _cpp_has_body,
        "union_specifier": _cpp_has_body,
        "enum_specifier": _cpp_has_body,
    },
    # so that a comment does not bind to a declaration that merely precedes the one
    # it documents (``const flag = true;`` before a function)
    CommentType.ts: {
        "lexical_declaration": _declares_function,
        "variable_declaration": _declares_function,
        "public_field_definition": _value_is_function,
        "assignment_expression": _assigns_function,
        "export_statement": _value_is_function,
    },
}
SCOPE_PREDICATES = ENTITY_PREDICATES
"""The name this table had before entities were named; kept for importers."""

COMMENT_TYPES = frozenset({"comment", "line_comment", "block_comment", "html_comment"})
"""The node kinds of a comment, in every grammar."""

# What may stand between a leading marker and its entity, besides comments; a blank
# line has no node, so it is trivia in every language.
TRIVIA_TYPES: dict[CommentType, frozenset[str]] = {
    CommentType.rust: frozenset({"attribute_item", "inner_attribute_item"}),
    CommentType.ts: frozenset({"decorator"}),
    CommentType.cpp: frozenset({"attribute_declaration"}),
}

# The node kinds that open an entity on a row before a comment -- an attribute, a
# decorator, a template header -- so a comment after one on its row is not trailing
# code: the item they belong to follows. An inner attribute (``#![...]``) applies to
# what it is inside, so it heads nothing.
ENTITY_HEAD_TYPES = frozenset(
    {
        "decorator",
        "template_parameter_list",
        "attribute_list",
        "attribute_declaration",
        "attribute_item",
    }
)

# The node kinds an entity can be wrapped in, and where the wrapped node is: a field
# name, or ``None`` for the last named child that is no comment. The entity is the
# wrapped node, so a decorated or templated definition's lines exclude its decorators
# or its template header.
WRAPPER_TYPES: dict[CommentType, dict[str, str | None]] = {
    CommentType.cpp: {"template_declaration": None, "linkage_specification": "body"},
    CommentType.python: {"decorated_definition": "definition"},
    # an ``export_statement`` is an entity itself when it exports a function or class
    # value (``export default () => {}``)
    CommentType.ts: {
        "export_statement": "declaration",
        "ambient_declaration": None,
        "expression_statement": None,
    },
}


def is_entity(node: TreeSitterNode, comment_type: CommentType) -> bool:
    """Whether ``node`` is an entity of its language (kind and predicate)."""
    if node.type not in ENTITY_NODE_TYPES.get(comment_type, ()):
        return False
    predicate = ENTITY_PREDICATES.get(comment_type, {}).get(node.type)
    return predicate is None or predicate(node)


def is_trivia(node: TreeSitterNode, comment_type: CommentType) -> bool:
    """Whether ``node`` may stand between a leading marker and its entity."""
    return node.type in COMMENT_TYPES or node.type in TRIVIA_TYPES.get(comment_type, ())


def is_wrapper(node: TreeSitterNode, comment_type: CommentType) -> bool:
    """Whether ``node`` can wrap an entity (see :data:`WRAPPER_TYPES`)."""
    return node.type in WRAPPER_TYPES.get(comment_type, {})


def unwrap_entity(
    node: TreeSitterNode | None, comment_type: CommentType
) -> TreeSitterNode | None:
    """The entity ``node`` is, or wraps (``@decorator``, ``template <…>``, ``export``)."""
    wrappers = WRAPPER_TYPES.get(comment_type, {})
    for _ in range(4):
        if node is None:
            return None
        if is_entity(node, comment_type):
            return node
        if node.type not in wrappers:
            return None
        field = wrappers[node.type]
        inner = node.child_by_field_name(field) if field is not None else None
        if inner is None:
            named = [c for c in node.named_children if c.type not in COMMENT_TYPES]
            inner = named[-1] if named else None
        node = inner
    return None


# ---------------------------------------------------------------------------
# Documentation comments
# ---------------------------------------------------------------------------

# The openings of a documentation comment, per language. A line opening followed by
# one more ``/`` (``////``) and a block opening followed by ``*`` or ``/`` (``/***``,
# ``/**/``) are plain comments.
_DOC_LINE_OPENINGS: dict[CommentType, tuple[str, ...]] = {
    CommentType.cpp: ("///", "//!"),
    CommentType.cs: ("///",),
    CommentType.rust: ("///", "//!"),
}
_DOC_BLOCK_OPENINGS: dict[CommentType, tuple[str, ...]] = {
    CommentType.cpp: ("/**", "/*!"),
    CommentType.cs: ("/**",),
    CommentType.rust: ("/**", "/*!"),
    CommentType.ts: ("/**",),
}


def is_doc_comment(
    node: TreeSitterNode, comment_type: CommentType, *, text: bytes | None = None
) -> bool:
    """Whether the comment ``node`` is a documentation comment of its language.

    A Python docstring is one too, but it is a string, not a comment: the caller knows
    it by its capture.

    :param text: The comment's text as the file writes it (``SourceComment.text``);
        ``node.text`` when not given.
    """
    written = ((node.text or b"") if text is None else text).decode("utf-8", "replace")
    for opening in _DOC_LINE_OPENINGS.get(comment_type, ()):
        if written.startswith(opening):
            return not (opening == "///" and written.startswith("////"))
    for opening in _DOC_BLOCK_OPENINGS.get(comment_type, ()):
        if written.startswith(opening):
            return opening == "/*!" or not written[len(opening) :].startswith(
                ("*", "/")
            )
    return False


# ---------------------------------------------------------------------------
# Naming: a definition node -> (kind, in-file qualified name, its components)
# ---------------------------------------------------------------------------
#
# Every namer builds the qualified name and its components (``semantic``) side by
# side, from the same walk; ``render_semantic`` spells the components back, and the
# truth test over the extraction fixtures holds the two together.


def _text(node: TreeSitterNode | None) -> str:
    if node is None:
        return ""
    return (node.text or b"").decode("utf-8", "replace")


def _is_ident_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def _squeeze(text: str) -> str:
    """``text`` without whitespace, except one space between two identifier characters.

    ``ns :: Widget`` becomes ``ns::Widget``, ``Box< T >`` becomes ``Box<T>``, and
    ``operator int`` keeps its space.
    """
    out: list[str] = []
    pending_space = False
    for char in text:
        if char.isspace():
            pending_space = True
            continue
        if pending_space and out and _is_ident_char(out[-1]) and _is_ident_char(char):
            out.append(" ")
        pending_space = False
        out.append(char)
    return "".join(out)


def _collapse(text: str) -> str:
    """``text`` with every whitespace run collapsed to one space, and trimmed."""
    return re.sub(r"\s+", " ", text).strip()


def _strip_template_args(text: str) -> str:
    """``text`` without its ``<…>`` argument lists (``operator<`` is kept)."""
    out: list[str] = []
    depth = 0
    for char in text:
        so_far = "".join(out)
        if char == "<" and depth == 0 and so_far.endswith(("operator", "operator<")):
            out.append(char)
        elif char == "<":
            depth += 1
        elif char == ">" and depth:
            depth -= 1
        elif depth == 0:
            out.append(char)
    return "".join(out)


def _join(separator: str, segments: list[str], own: str | None) -> str | None:
    if own is None:
        return None
    return separator.join([*segments, own])


def _element(kind: str, name: str) -> SemanticElement:
    return {"kind": kind, "name": name}


def _named(
    kind: EntityKind,
    qualified_name: str | None,
    semantic: Iterable[SemanticElement],
    name_end: int | None = None,
) -> EntityName:
    """An entity's name and its components; no components when it has no name."""
    if qualified_name is None:
        return EntityName(kind, None, None, name_end)
    return EntityName(kind, qualified_name, tuple(semantic), name_end)


# --- C and C++ ---------------------------------------------------------------

_CPP_CLASS_KINDS: dict[str, EntityKind] = {
    "class_specifier": "class",
    "struct_specifier": "struct",
    "union_specifier": "union",
    "enum_specifier": "enum",
}

# The kinds the namer gives a function only when a class qualifies it.
_CPP_MEMBER_KINDS = frozenset({"method", "constructor", "destructor"})


def _cpp_text(node: TreeSitterNode | None, source: bytes | None) -> str:
    """The text of ``node``, read from ``source`` when given.

    ``source`` is the file as written: a C++ tree may be parsed from a prepared copy of
    it (:mod:`sphinx_codelinks.analyse.cpp_macros`), and every name is read from the
    file, never from that copy. Without it, the tree's own text is read.
    """
    return _cpp_bytes(node, source).decode("utf-8", "replace")


def _cpp_bytes(node: TreeSitterNode | None, source: bytes | None) -> bytes:
    """The bytes of ``node``, read from ``source`` when given (see :func:`_cpp_text`)."""
    if node is None:
        return b""
    if source is None:
        return node.text or b""
    return source[node.start_byte : node.end_byte]


@dataclass(frozen=True)
class _CppNaming:
    """How the names of a C++ tree's entities are made beyond one node."""

    full_chain: bool = False
    """Keep every container, an inline namespace and a friend's classes included, as
    the names were made before they were left out (see :func:`cpp_renames`)."""
    specs: _PartialSpecs | None = None
    """The file's partial specialisations, which an out-of-line qualifier is spelled
    as (:func:`_cpp_name`)."""
    inline: frozenset[str] | None = None
    """The paths of the file's inline namespaces as the full chain spells them
    (``lib::v2``), which a written qualifier leaves out
    (:func:`_cpp_without_inline_parts`)."""
    macros: Callable[[int], str] | None = None
    """The namespaces the file's own macros open around a name ending at a byte, each
    followed by ``::``."""

    def macros_at(self, name_end: int) -> str:
        """The namespaces the file's own macros open around a name ending at
        ``name_end`` (``ns::`` or empty)."""
        return self.macros(name_end) if self.macros is not None else ""

    def specs_at(
        self, node: TreeSitterNode, source: bytes | None, name_end: int, written: str
    ) -> _Lookup | None:
        """Where the templates the name ``written`` at ``node`` (ending at
        ``name_end``) qualifies are looked up among the file's partial specialisations
        (:class:`_Lookup`), when it has any."""
        if self.specs is None:
            return None
        macros = self.macros_at(name_end)
        inline_parts = (
            _cpp_inline_segments(
                self.inline, macros, node, source, _squeeze(written).lstrip(":")
            )
            if self.inline is not None
            else []
        )
        return _Lookup(
            self.specs, _cpp_scope_of(node, source, self, macros), inline_parts
        )


@dataclass(frozen=True)
class _Lookup:
    """Where the templates an out-of-line qualifier names are looked up among the
    file's partial specialisations (:func:`_cpp_name`)."""

    specs: _PartialSpecs
    """The file's partial specialisations."""
    scope: str
    """Where the name is written (:func:`_cpp_scope_of`)."""
    inline_parts: list[int]
    """The parts of the written name that name an inline namespace of the file
    (:func:`_cpp_inline_segments`): left out of the path, as the specialisations' own
    keys leave them out."""


_ALONE = _CppNaming()
_FULL = _CppNaming(full_chain=True)


def _cpp_templated(node: TreeSitterNode) -> bool:
    """Under a ``template`` with parameters (not an explicit specialisation)."""
    parent = node.parent
    while parent is not None and parent.type == "template_declaration":
        params = parent.child_by_field_name("parameters")
        if params is not None and params.named_child_count > 0:
            return True
        parent = parent.parent
    return False


def _cpp_template_headers(
    node: TreeSitterNode, source: bytes | None
) -> list[list[str]]:
    """The parameter names of each ``template <…>`` header around ``node``, outermost
    first (``template <typename T> template <typename U>`` is ``[T]``, ``[U]``;
    ``template <>`` is ``[]``; a pack ``typename... Ts`` is ``Ts``)."""
    headers: list[list[str]] = []
    parent = node.parent
    while parent is not None and parent.type == "template_declaration":
        parameters = parent.child_by_field_name("parameters")
        headers.append(
            [
                _cpp_parameter_name(parameter, source)
                for parameter in parameters.named_children
                if parameter.type != "comment"
            ]
            if parameters is not None
            else []
        )
        parent = parent.parent
    headers.reverse()
    return headers


def _cpp_parameter_name(parameter: TreeSitterNode, source: bytes | None) -> str:
    """The name a template parameter declares (``T`` of ``typename T = int``, ``N`` of
    ``int N``, ``Ts`` of ``typename... Ts``, ``TT`` of
    ``template <class> class TT``); empty for an unnamed one."""
    if parameter.type in (
        "type_parameter_declaration",
        "variadic_type_parameter_declaration",
    ):
        name = next(
            (c for c in parameter.named_children if c.type == "type_identifier"), None
        )
    elif parameter.type == "optional_type_parameter_declaration":
        name = parameter.child_by_field_name("name")
    elif parameter.type == "template_template_parameter_declaration":
        inner = next(
            (
                c
                for c in reversed(parameter.named_children)
                if c.type.endswith("type_parameter_declaration")
            ),
            None,
        )
        return _cpp_parameter_name(inner, source) if inner is not None else ""
    else:
        # a non-type parameter: the identifier its declarator ends in
        declarator = parameter.child_by_field_name("declarator")
        stack = [declarator] if declarator is not None else []
        name = None
        while stack:
            current = stack.pop()
            if current.type == "identifier":
                name = current
                break
            stack.extend(reversed(current.named_children))
    return _squeeze(_cpp_text(name, source))


def _cpp_written_arguments(part: str) -> list[str] | None:
    """The arguments of ``part``'s template argument list (``P<T,4>`` is ``T`` and
    ``4``), split at its top-level commas, a pack expansion with its ``...``
    (``Ts...``). ``None`` when ``part`` has no argument list."""
    open_at = part.find("<")
    if open_at < 0 or not part.endswith(">") or open_at + 1 > len(part) - 1:
        return None
    inner = part[open_at + 1 : -1]
    arguments: list[str] = []
    depth = start = 0
    for index, char in enumerate(inner):
        if char in "<([":
            depth += 1
        elif char in ">)]":
            depth = max(depth - 1, 0)
        elif char == "," and depth == 0:
            arguments.append(inner[start:index])
            start = index + 1
    arguments.append(inner[start:])
    return [argument.strip() for argument in arguments]


def _cpp_template_arguments(part: str) -> list[str] | None:
    """:func:`_cpp_written_arguments`, a pack expansion without its ``...`` (``Ts...``
    is ``Ts``): what a header's parameter names are compared with."""
    written = _cpp_written_arguments(part)
    if written is None:
        return None
    stripped = []
    for argument in written:
        while argument.endswith("..."):
            argument = argument[: -len("...")]
        stripped.append(argument)
    return stripped


def _cpp_words(text: str) -> list[str]:
    """The identifiers of ``text``, in order."""
    words: list[str] = []
    start: int | None = None
    for index, char in enumerate(text):
        if _is_ident_char(char):
            if start is None:
                start = index
        elif start is not None:
            words.append(text[start:index])
            start = None
    if start is not None:
        words.append(text[start:])
    return words


def _cpp_canonical(arguments: list[str], parameters: list[str]) -> list[str]:
    """``arguments`` with every name in ``parameters`` replaced by its place among the
    parameters named so far (``$0``, ``$1``, …): two argument lists that are the same
    but for their own template parameter names (``<T,4>`` under
    ``template <typename T>``, ``<U,4>`` under ``template <typename U>``) give the same
    list."""
    seen: list[str] = []

    def spelled(word: str) -> str:
        if word not in parameters:
            return word
        if word not in seen:
            seen.append(word)
        return f"${seen.index(word)}"

    canonical: list[str] = []
    for argument in arguments:
        out: list[str] = []
        start: int | None = None
        for index, char in enumerate(argument):
            if _is_ident_char(char):
                if start is None:
                    start = index
                continue
            if start is not None:
                out.append(spelled(argument[start:index]))
                start = None
            out.append(char)
        if start is not None:
            out.append(spelled(argument[start:]))
        canonical.append("".join(out))
    return canonical


@dataclass(frozen=True)
class _PartialSpec:
    """One partial specialisation :class:`_PartialSpecs` holds."""

    spelled: str
    """Its last name part, squeezed (``P<T,4>``)."""
    canonical: list[str]
    """Its arguments up to its own parameter names (:func:`_cpp_canonical`)."""
    defined: bool
    """Whether it has a body: a forward declaration does not."""


class _PartialSpecs:
    """The partial specialisations of class templates a C++ file declares, by the
    template's qualified name (:func:`_cpp_scope_of` and its name: ``ns1::P``, so
    ``ns1::P<T,4>`` and ``ns2::P<U,4>`` never share one): each as it spells its last
    name part (``P<T,4>``), its arguments up to its own parameter names, a pack's
    ``...`` kept (:func:`_cpp_canonical`), and whether it has a body. An out-of-line
    qualifier the same but for its parameter names as exactly one spelling of those
    with a body is spelled as it is (:func:`_cpp_name`), so the members the
    specialisation defines join their in-class declarations; a forward declaration
    never sets the spelling, and where two spellings remain none does."""

    def __init__(self) -> None:
        self.by_template: dict[str, list[_PartialSpec]] = {}

    @classmethod
    def of(
        cls, nodes: list[TreeSitterNode], source: bytes | None, naming: _CppNaming
    ) -> _PartialSpecs:
        """The partial specialisations among ``nodes`` (:meth:`add`)."""
        specs = cls()
        for node in nodes:
            specs.add(node, source, naming)
        return specs

    def add(
        self, node: TreeSitterNode, source: bytes | None, naming: _CppNaming
    ) -> None:
        """``node``, when it is a class, struct or union named with template arguments
        under a header with parameters (a partial specialisation), keyed as ``naming``
        reads where it is (the file's own macros and its inline namespaces,
        :func:`_cpp_scope_of`)."""
        if not _cpp_templated_class(node):
            return
        name = node.child_by_field_name("name")
        if name is None:
            return
        headers = _cpp_template_headers(node, source)
        if not headers or not headers[-1]:
            return
        spelled = _cpp_class_name(name, node, source)
        *qualifiers, part = _cpp_split(spelled)
        arguments = _cpp_written_arguments(part)
        if arguments is None:
            return
        macros = naming.macros_at(name.end_byte)
        inline_parts = (
            _cpp_inline_segments(naming.inline, macros, node, source, spelled)
            if naming.inline is not None
            else []
        )
        template = _cpp_scope_of(node, source, naming, macros)
        template += "".join(
            f"{_strip_template_args(qualifier)}::"
            for index, qualifier in enumerate(qualifiers)
            if index not in inline_parts
        )
        template += part.split("<", 1)[0]
        self.by_template.setdefault(template, []).append(
            _PartialSpec(
                part,
                _cpp_canonical(arguments, headers[-1]),
                node.child_by_field_name("body") is not None,
            )
        )

    def spelling(self, scope: str, part: str, parameters: list[str]) -> str | None:
        """How the partial specialisations of the file spell ``part`` (a qualifier in
        ``scope``, :func:`_cpp_scope_of` and the qualifiers before it, under a header
        of ``parameters``): the one spelling of those with a body that are the same but
        for their parameter names, when there is exactly one."""
        arguments = _cpp_written_arguments(part)
        if arguments is None:
            return None
        wanted = _cpp_canonical(arguments, parameters)
        spellings = {
            spec.spelled
            for spec in self.by_template.get(scope + part.split("<", 1)[0], ())
            if spec.defined and spec.canonical == wanted
        }
        return next(iter(spellings)) if len(spellings) == 1 else None


def _cpp_templated_class(node: TreeSitterNode) -> bool:
    """``node`` is a class, struct or union under a template header: a partial
    specialisation when it is named with arguments under a header with parameters
    (:meth:`_PartialSpecs.add`)."""
    return (
        node.type in ("class_specifier", "struct_specifier", "union_specifier")
        and node.parent is not None
        and node.parent.type == "template_declaration"
    )


def _cpp_scope_of(
    node: TreeSitterNode, source: bytes | None, naming: _CppNaming, macros: str
) -> str:
    """Where the templates a name written at ``node`` qualifies are looked up:
    ``macros`` (the namespaces the file's own macros open around it, ``ns::`` or
    empty), then the namespaces and classes around it as ``naming`` names them with
    every inline namespace left out (:func:`_cpp_containers`), each without its
    arguments and followed by ``::``."""
    around = replace(naming, full_chain=False, specs=None)
    segments, _ = _cpp_containers(node, source, around)
    return macros + "".join(
        f"{_strip_template_args(part)}::"
        for segment in segments
        for part in _cpp_split(segment)
    )


def _cpp_name(
    text: str,
    headers: list[list[str]],
    *,
    strip_last: bool,
    lookup: _Lookup | None,
) -> str:
    """A name as the naming spells it: ``text`` squeezed, without a leading ``::``.

    A qualifier's template argument list that names a parameter of the next
    ``template <…>`` header around the definition (``headers``, outermost first) is
    matched with that header; one that names none of them (an explicit specialisation,
    ``Outer<int>``) is kept and takes no header but an empty ``template <>``
    (``template <> template <class U> void Outer<int>::Inner<U>::n()`` matches
    ``Inner<U>`` with ``<class U>``). A matched list is spelled as a partial
    specialisation of the file spells its arguments when the two are the same but for
    their own parameter names (``lookup``, with the scope the name is written in,
    ``ns::`` or empty: ``template <typename U> void P<U,4>::fill()`` is ``P<T,4>::fill``
    when the file defines ``template <typename T> struct P<T,4> {…}``;
    :class:`_PartialSpecs`, :class:`_Lookup`).
    Otherwise it is the template's own when its arguments are exactly the header's
    parameter names (the primary template's member,
    ``template <typename T> void Box<T>::get()``), named without it (``Box::get``), and
    a specialisation's, kept, when they are not (``template <typename B> void
    W<B,4>::fill()`` is ``W<B,4>::fill``). The last part's list is stripped when
    ``strip_last`` (a function under a header with parameters).
    """
    parts = _cpp_split(_squeeze(text).lstrip(":"))
    last = len(parts) - 1
    remaining = iter(headers)
    upcoming = next(remaining, None)
    # where the template a qualifier names is: the scope, then the qualifiers before
    # it, without their arguments and without those that name an inline namespace of
    # the file
    path = lookup.scope if lookup is not None else ""
    spelled: list[str] = []
    for index, part in enumerate(parts):
        if index == last:
            spelled.append(_strip_template_args(part) if strip_last else part)
            break
        arguments = _cpp_template_arguments(part)
        if arguments is None:
            spelled.append(part)
        elif upcoming is None or not any(
            word in upcoming for argument in arguments for word in _cpp_words(argument)
        ):
            # an explicit specialisation's empty ``template <>`` is its own
            if upcoming == []:
                upcoming = next(remaining, None)
            spelled.append(part)
        else:
            parameters = upcoming
            upcoming = next(remaining, None)
            as_spec = (
                lookup.specs.spelling(path, part, parameters)
                if lookup is not None
                else None
            )
            if as_spec is not None:
                spelled.append(as_spec)
            elif parameters == arguments:
                spelled.append(_strip_template_args(part))
            else:
                spelled.append(part)
        if lookup is None or index not in lookup.inline_parts:
            path += f"{_strip_template_args(part)}::"
    return "::".join(spelled)


def _cpp_text_without_comments(node: TreeSitterNode, source: bytes | None) -> str:
    """The text of ``node`` with every comment inside it left out (``json.hpp`` writes
    ``//`` comments between a specialisation's template arguments)."""
    comments: list[tuple[int, int]] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type == "comment":
            comments.append((current.start_byte, current.end_byte))
        else:
            stack.extend(current.children)
    written = _cpp_bytes(node, source)
    if not comments:
        return written.decode("utf-8", "replace")
    out: list[bytes] = []
    position = node.start_byte
    for start, end in sorted(comments):
        out.append(written[position - node.start_byte : start - node.start_byte])
        out.append(b" ")
        position = end
    out.append(written[position - node.start_byte :])
    return b"".join(out).decode("utf-8", "replace")


def _cpp_class_name(
    name: TreeSitterNode, class_node: TreeSitterNode, source: bytes | None
) -> str:
    """A class's name: a specialisation's arguments kept, squeezed and without comments
    (``P<T,4>``, explicit or partial), as clang names it; a primary template's name has
    none to strip."""
    return _cpp_name(
        _cpp_text_without_comments(name, source),
        _cpp_template_headers(class_node, source),
        strip_last=False,
        lookup=None,
    )


def _cpp_class_name_in(
    name: TreeSitterNode,
    class_node: TreeSitterNode,
    source: bytes | None,
    naming: _CppNaming,
) -> str:
    """:func:`_cpp_class_name`, without the parts of a written qualifier that name an
    inline namespace of the file (``struct lib::v2::X {…}`` is ``lib::X``, so its
    members are named in it), unless ``naming`` keeps every container."""
    own = _cpp_class_name(name, class_node, source)
    if naming.inline is None or naming.full_chain:
        return own
    dropped = _cpp_inline_segments(
        naming.inline, naming.macros_at(name.end_byte), class_node, source, own
    )
    return _cpp_without_parts(own, dropped) if dropped else own


def _cpp_namespace_name(node: TreeSitterNode, source: bytes | None) -> str:
    name = node.child_by_field_name("name")
    if name is None:
        return "(anonymous namespace)"
    return _squeeze(_cpp_text(name, source))


def _cpp_is_inline_namespace(node: TreeSitterNode) -> bool:
    """The namespace ``node`` is declared ``inline`` (``inline namespace v1``)."""
    for child in node.children:
        if child.type == "namespace":
            return False
        if child.type == "inline":
            return True
    return False


def _cpp_inline_namespace_or_part(node: TreeSitterNode) -> bool:
    """The namespace ``node`` is inline, or holds an inline part in its nested name
    (``namespace a::inline b``): an ``inline`` token, as
    :func:`_cpp_is_inline_namespace` reads one (``namespace pipeline`` has none)."""
    if _cpp_is_inline_namespace(node):
        return True
    name = node.child_by_field_name("name")
    return name is not None and _cpp_has_inline_part(name)


def _cpp_has_inline_part(name: TreeSitterNode) -> bool:
    """The nested namespace specifier ``name`` holds an ``inline`` token."""
    if name.type != "nested_namespace_specifier":
        return False
    return any(
        child.type == "inline" or _cpp_has_inline_part(child) for child in name.children
    )


def _cpp_namespaces_around(node: TreeSitterNode, source: bytes | None) -> str:
    """The namespaces around ``node`` with every part kept (an inline one too),
    outermost first, each followed by ``::`` (``lib::v1::``)."""
    groups: list[list[str]] = []
    parent = node.parent
    while parent is not None:
        if parent.type == "namespace_definition":
            groups.append(_cpp_namespace_parts(parent, source, own=False, naming=_FULL))
        parent = parent.parent
    return "".join(f"{part}::" for group in reversed(groups) for part in group)


def _cpp_inline_paths_of(
    node: TreeSitterNode, source: bytes | None, prefix: Callable[[int], str]
) -> list[str]:
    """The paths of the inline parts of the namespace ``node`` (an inline namespace, or
    one with an inline part in its nested name), as the full chain spells them, after
    the namespaces the file's own macros open (``lib::v2``); none for an unnamed one,
    which no qualifier can name."""
    name = node.child_by_field_name("name")
    if name is None:
        return []
    parts = _cpp_split(_cpp_namespace_name(node, source))
    last = len(parts) - 1
    path = prefix(name.end_byte) + _cpp_namespaces_around(node, source)
    paths: list[str] = []
    for index, part in enumerate(parts):
        inline = part.startswith("inline ")
        bare = part.removeprefix("inline ")
        if not inline:
            inline = index == last and _cpp_is_inline_namespace(node)
        path += bare
        if inline:
            paths.append(path)
        path += "::"
    return paths


def _cpp_without_inline_parts(
    naming: _CppNaming,
    node: TreeSitterNode,
    source: bytes | None,
    own: str,
    name_end: int,
    semantic: list[SemanticElement],
) -> tuple[str, list[SemanticElement]]:
    """``own``, the name written at ``node`` (its name ending at ``name_end``), and its
    components ``semantic`` (which end with ``own``'s), without the parts of its
    qualifier that name an inline namespace of the file, as the namespaces around a
    node leave one out (``void lib::v2::g() {}`` is ``lib::g`` when the file declares
    ``inline namespace v2`` in ``lib``); unchanged with every container kept."""
    if naming.inline is None or naming.full_chain:
        return own, semantic
    dropped = _cpp_inline_segments(
        naming.inline, naming.macros_at(name_end), node, source, own
    )
    if not dropped:
        return own, semantic
    first = max(len(semantic) - len(_cpp_split(own)), 0)
    kept_semantic = [
        element
        for position, element in enumerate(semantic)
        if position - first not in dropped
    ]
    return _cpp_without_parts(own, dropped), kept_semantic


def _cpp_inline_segments(
    paths: frozenset[str],
    macros: str,
    node: TreeSitterNode,
    source: bytes | None,
    own: str,
) -> list[int]:
    """The parts of ``own``, the name written at ``node``, that name one of the file's
    inline namespaces (``paths``): indexes into its qualifier's parts, read from
    ``macros`` (the namespaces the file's own macros open around it) and the
    namespaces around ``node`` (``void lib::v2::g() {}`` is ``lib``, ``v2``, ``g``, and
    ``v2`` is one when the file declares ``inline namespace v2`` in ``lib``)."""
    *qualifier, _ = _cpp_split(own)
    path = macros + _cpp_namespaces_around(node, source)
    dropped: list[int] = []
    for index, part in enumerate(qualifier):
        path += part
        if path in paths:
            dropped.append(index)
        path += "::"
    return dropped


def _cpp_without_parts(name: str, dropped: list[int]) -> str:
    """``name`` without the parts at ``dropped``."""
    return "::".join(
        part for index, part in enumerate(_cpp_split(name)) if index not in dropped
    )


def _cpp_namespace_parts(
    node: TreeSitterNode, source: bytes | None, *, own: bool, naming: _CppNaming
) -> list[str]:
    """The parts of the namespace ``node``'s name (``namespace a::b`` is ``a`` and
    ``b``) that a name qualified by it keeps.

    None for an inline namespace, and none for an inline part of a nested name
    (``a::inline b`` keeps ``a``), as clang prints a name: ``nlohmann::basic_json``,
    not ``nlohmann::json_abi_v3_12_0::basic_json`` (the ABI tag changes with every
    release). As the entity itself (``own``), its own last part is kept, without the
    ``inline`` (``a::inline b`` is ``a`` and ``b``). A part that reopens one of the
    file's inline namespaces without ``inline`` is inline too, as C++ makes it
    (:func:`_cpp_reopened_parts`, when ``naming`` knows them). With
    ``naming.full_chain``, every part is kept, an inline one without its ``inline``.
    """
    reopened = [] if naming.full_chain else _cpp_reopened_parts(node, source, naming)
    parts = _cpp_split(_cpp_namespace_name(node, source))
    last = len(parts) - 1
    kept: list[str] = []
    for index, part in enumerate(parts):
        inline = part.startswith("inline ") or (
            index == last and _cpp_is_inline_namespace(node)
        )
        if (
            not (inline or index in reopened)
            or naming.full_chain
            or (own and index == last)
        ):
            kept.append(part.removeprefix("inline "))
    return kept


def _cpp_reopened_parts(
    node: TreeSitterNode, source: bytes | None, naming: _CppNaming
) -> list[int]:
    """The parts of the namespace ``node``'s name that reopen one of the file's inline
    namespaces without ``inline`` (``namespace lib { namespace v1 {…} }`` after
    ``inline namespace v1`` in ``lib``): their paths, read as the file's inline paths
    are, are among ``naming``'s; none when it has none."""
    name = node.child_by_field_name("name")
    if naming.inline is None or name is None:
        return []
    path = naming.macros_at(name.end_byte) + _cpp_namespaces_around(node, source)
    reopened: list[int] = []
    for index, part in enumerate(_cpp_split(_cpp_namespace_name(node, source))):
        path += part.removeprefix("inline ")
        if path in naming.inline:
            reopened.append(index)
        path += "::"
    return reopened


def _cpp_reopens_inline(
    node: TreeSitterNode,
    source: bytes | None,
    prefix: Callable[[int], str],
    paths: set[str],
) -> bool:
    """The namespace ``node`` reopens one of the file's inline namespaces met so far
    without ``inline`` (a part's path is among ``paths``), which C++ makes inline too:
    the first declaration is the inline one."""
    if not paths:
        return False
    naming = _CppNaming(inline=frozenset(paths), macros=prefix)
    return bool(_cpp_reopened_parts(node, source, naming))


def _cpp_operator_at(text: str, index: int) -> bool:
    """``text`` has the word ``operator`` at ``index``."""
    end = index + len("operator")
    return text.startswith("operator", index) and (
        end == len(text) or not _is_ident_char(text[end])
    )


def _cpp_split(text: str) -> list[str]:
    """The components of a name as written, at its ``::``: none inside ``<…>`` or
    ``(…)``, and none after ``operator`` (``W::operator std::string`` is ``W`` and
    ``operator std::string``; ``Box<std::string>::get`` is ``Box<std::string>`` and
    ``get``)."""
    parts: list[str] = []
    start = depth = index = 0
    while index < len(text) and not (index == start and _cpp_operator_at(text, index)):
        char = text[index]
        if char in "<(":
            depth += 1
        elif char in ">)" and depth:
            depth -= 1
        elif depth == 0 and text.startswith("::", index):
            parts.append(text[start:index])
            index += 2
            start = index
            continue
        index += 1
    parts.append(text[start:])
    return parts


def _cpp_qualified(text: str, kind: str, *, member: bool) -> list[SemanticElement]:
    """The components of a name written qualified (``ns::W::f``), the last one of
    ``kind``. What a qualifier is, the syntax cannot tell: each is a ``scope``, except
    the one right before a ``member`` (a method, constructor, destructor or conversion
    operator), which is its ``class``."""
    *qualifiers, own = _cpp_split(text)
    elements = [_element("scope", qualifier) for qualifier in qualifiers]
    if member and qualifiers:
        elements[-1] = _element("class", qualifiers[-1])
    return [*elements, _element(kind, own)]


def _cpp_is_friend(node: TreeSitterNode) -> bool:
    """``node`` is what a ``friend`` declaration declares or defines
    (``friend bool operator==(const A&, const A&) {…}``, a friend template's too): a
    function of the innermost enclosing namespace, not of the class."""
    return node.parent is not None and node.parent.type == "friend_declaration"


def _cpp_containers(
    node: TreeSitterNode, source: bytes | None, naming: _CppNaming
) -> tuple[list[str], list[SemanticElement]]:
    """The namespaces and classes around ``node``, outermost first: their names, and
    their components (``namespace a::b`` is two namespaces). An inline namespace adds
    nothing (:func:`_cpp_namespace_parts`), and a function a ``friend`` declaration
    declares or defines is named in its innermost enclosing namespace, as clang names
    it: the classes around it add nothing."""
    friend = not naming.full_chain and _cpp_is_friend(node)
    segments: list[str] = []
    groups: list[list[SemanticElement]] = []
    parent = node.parent
    while parent is not None:
        if parent.type == "namespace_definition":
            parts = _cpp_namespace_parts(parent, source, own=False, naming=naming)
            if parts:
                segments.append("::".join(parts))
                groups.append([_element("namespace", part) for part in parts])
        elif not friend and parent.type in (
            "class_specifier",
            "struct_specifier",
            "union_specifier",
        ):
            name = parent.child_by_field_name("name")
            if name is not None:
                container = _cpp_class_name_in(name, parent, source, naming)
                segments.append(container)
                groups.append(
                    _cpp_qualified(
                        container, _CPP_CLASS_KINDS[parent.type], member=False
                    )
                )
        parent = parent.parent
    return (
        list(reversed(segments)),
        [element for group in reversed(groups) for element in group],
    )


def cpp_function_declarator(node: TreeSitterNode) -> TreeSitterNode | None:
    """The ``function_declarator`` of a function definition or declaration."""
    declarator = node.child_by_field_name("declarator")
    for _ in range(8):
        if declarator is None:
            return None
        if declarator.type == "function_declarator":
            return declarator
        declarator = declarator.child_by_field_name("declarator") or (
            declarator.named_children[-1] if declarator.named_children else None
        )
    return None


# What may stand between a class member and its class body: a member template's
# header, a preprocessor conditional.
_CPP_MEMBER_WRAPPERS = frozenset(
    {
        "template_declaration",
        "preproc_if",
        "preproc_ifdef",
        "preproc_elif",
        "preproc_elifdef",
        "preproc_else",
    }
)


def _cpp_in_class(node: TreeSitterNode) -> bool:
    """A direct member of a class body (a member template, or a member inside
    ``#if`` / ``#else``, counts)."""
    parent = node.parent
    while parent is not None and parent.type in _CPP_MEMBER_WRAPPERS:
        parent = parent.parent
    return parent is not None and parent.type == "field_declaration_list"


def _cpp_defined_by_macro(node: TreeSitterNode) -> bool:
    """A function a macro defines (``TEST(Suite, Name) {...}``): a definition with no
    return type, outside a class, whose declarator is a plain identifier. The function
    the compiler sees is the macro's expansion, which the syntax cannot name."""
    if node.type != "function_definition" or node.child_by_field_name("type"):
        return False
    if _cpp_in_class(node):
        return False
    declarator = cpp_function_declarator(node)
    inner = (
        declarator.child_by_field_name("declarator") if declarator is not None else None
    )
    return inner is not None and inner.type == "identifier"


def _cpp_conversion_parameters(cast: TreeSitterNode) -> TreeSitterNode | None:
    """A conversion operator's own parameter list: the first one under the cast's
    declarator, past any pointer or reference. The search starts at the cast's
    declarator, so a parameter list inside the target type
    (``operator std::function<void(int)>()``) is not it."""
    declarator = cast.child_by_field_name("declarator")
    stack = [declarator] if declarator is not None else []
    while stack:
        node = stack.pop()
        if node.type == "parameter_list":
            return node
        stack.extend(reversed(node.children))
    return None


def _cpp_conversion_target_end(cast: TreeSitterNode) -> int:
    """Where a conversion operator's target type ends: at its own parameter list
    (``operator const char*() const``), past any pointer or reference."""
    parameters = _cpp_conversion_parameters(cast)
    return parameters.start_byte if parameters is not None else cast.end_byte


def _cpp_conversion(
    node: TreeSitterNode,
    cast: TreeSitterNode,
    containers: tuple[list[str], list[SemanticElement]],
    source: bytes | None,
    naming: _CppNaming,
) -> EntityName:
    """A conversion operator, named ``ns::W::operator const char*``: the qualifier
    written before the ``operator_cast``, then ``operator`` and its target type as
    written, up to the parameter list. Its name ends where the target type does."""
    prefix, outer = containers
    declarator = node.child_by_field_name("declarator")
    written = _cpp_bytes(declarator, source)
    head = (
        written[: cast.start_byte - declarator.start_byte].decode("utf-8", "replace")
        if declarator is not None
        else ""
    )
    keyword = cast.children[0] if cast.children else cast
    target_end = _cpp_conversion_target_end(cast)
    cast_text = _cpp_bytes(cast, source)
    target = cast_text[
        keyword.end_byte - cast.start_byte : target_end - cast.start_byte
    ].decode("utf-8", "replace")
    qualifier = _cpp_name(
        head,
        _cpp_template_headers(node, source),
        strip_last=_cpp_templated(node),
        lookup=naming.specs_at(node, source, cast.start_byte, head),
    )
    own = f"{qualifier}operator {_squeeze(target)}"
    spelled = cast_text[: target_end - cast.start_byte].decode("utf-8", "replace")
    # a conversion operator is always a member: its qualifier is its class
    own, semantic = _cpp_without_inline_parts(
        naming,
        node,
        source,
        own,
        cast.start_byte,
        [*outer, *_cpp_qualified(own, "operator", member=True)],
    )
    return _named(
        "operator",
        "::".join([*prefix, own]),
        semantic,
        cast.start_byte + len(spelled.rstrip().encode("utf-8")),
    )


def _cpp_describe_in(
    node: TreeSitterNode, source: bytes | None, naming: _CppNaming
) -> EntityName | None:
    """Name the C or C++ entity ``node``, read from ``source`` (see :func:`_cpp_text`),
    its containers kept as ``naming`` says."""
    prefix, outer = _cpp_containers(node, source, naming)
    if node.type in ("function_definition", "declaration", "field_declaration"):
        cast = _cpp_operator_cast(node)
        if cast is not None:
            return _cpp_conversion(node, cast, (prefix, outer), source, naming)
        if _cpp_defined_by_macro(node):
            return None
        declarator = cpp_function_declarator(node)
        inner = (
            declarator.child_by_field_name("declarator")
            if declarator is not None
            else None
        )
        if inner is None:
            return None
        written = _cpp_text_without_comments(inner, source)
        own = _cpp_name(
            written,
            _cpp_template_headers(node, source),
            strip_last=_cpp_templated(node),
            lookup=naming.specs_at(node, source, inner.end_byte, written),
        )
        last = own.rsplit("::", 1)[-1]
        qualifier = own.rsplit("::", 1)[0] if "::" in own else None
        if qualifier is not None:
            container: str | None = _strip_template_args(qualifier.rsplit("::", 1)[-1])
        elif _cpp_in_class(node) and prefix:
            container = _strip_template_args(prefix[-1])
        else:
            container = None
        kind: EntityKind
        if last.startswith("operator"):
            kind = "operator"
        elif container is not None and last == container:
            kind = "constructor"
        elif container is not None and last.startswith("~"):
            kind = "destructor"
        elif container is not None:
            kind = "method"
        else:
            kind = "function"
        own, semantic = _cpp_without_inline_parts(
            naming,
            node,
            source,
            own,
            inner.end_byte,
            [*outer, *_cpp_qualified(own, kind, member=kind in _CPP_MEMBER_KINDS)],
        )
        return _named(kind, "::".join([*prefix, own]), semantic, inner.end_byte)
    if node.type in _CPP_CLASS_KINDS:
        class_kind = _CPP_CLASS_KINDS[node.type]
        name = node.child_by_field_name("name")
        if name is None:
            return EntityName(class_kind, None, None)
        own_name = _cpp_class_name_in(name, node, source, naming)
        return _named(
            class_kind,
            "::".join([*prefix, own_name]),
            [*outer, *_cpp_qualified(own_name, class_kind, member=False)],
            name.end_byte,
        )
    if node.type == "namespace_definition":
        own_parts = _cpp_namespace_parts(node, source, own=True, naming=naming)
        name = node.child_by_field_name("name")
        return _named(
            "namespace",
            "::".join([*prefix, "::".join(own_parts)]),
            [*outer, *(_element("namespace", part) for part in own_parts)],
            name.end_byte if name is not None else None,
        )
    return None


def _cpp_describe(node: TreeSitterNode) -> EntityName | None:
    return _cpp_describe_in(node, None, _ALONE)


# --- C and C++: what tells a function's overloads apart -------------------------
#
# The parameter-type rules follow codebase-memory-mcp's callable signatures
# (``internal/cbm/callable_sig.c``, MIT): ``(void)`` is ``()``, top-level cv-qualifiers
# are dropped, arrays and function types decay to pointers, and ``struct X`` is ``X``.
# They are re-implemented here on the syntax tree; no code is taken. Leaving out
# comments, attributes and the parameter's name wherever they sit is ours.

# What a parameter's type leaves out wherever it sits: a comment, a C++ ``[[...]]``
# attribute, a GNU ``__attribute__((...))``.
_CPP_PARAMETER_NOISE = frozenset(
    {"comment", "attribute_declaration", "attribute_specifier"}
)

# The declarators that hold their inner declarator without a ``declarator`` field: it
# is their first named child that is no noise.
_CPP_UNFIELDED_DECLARATORS = frozenset(
    {
        "attributed_declarator",
        "reference_declarator",
        "abstract_reference_declarator",
        "parenthesized_declarator",
        "abstract_parenthesized_declarator",
        "variadic_declarator",
    }
)

# The cv-qualifiers a parameter's top level may carry, which do not make it another
# type (``const int`` is ``int``, ``int* const`` is ``int*``).
_CPP_TOP_LEVEL_QUALIFIERS = frozenset(
    {"const", "volatile", "restrict", "__restrict", "__restrict__"}
)

# One edit of a parameter's text: the byte range it replaces, and its replacement.
_Edit = tuple[int, int, str]


def _cpp_inner_declarator(node: TreeSitterNode) -> TreeSitterNode | None:
    """The declarator ``node`` wraps; ``None`` at the name."""
    if node.type in ("identifier", "field_identifier"):
        return None
    if node.type in _CPP_UNFIELDED_DECLARATORS:
        return next(
            (c for c in node.named_children if c.type not in _CPP_PARAMETER_NOISE),
            None,
        )
    return node.child_by_field_name("declarator")


def _cpp_declarator_chain(parameter: TreeSitterNode) -> list[TreeSitterNode]:
    """A parameter's declarators, from the outermost to its name (or to the innermost
    one of an unnamed parameter)."""
    chain: list[TreeSitterNode] = []
    current = parameter.child_by_field_name("declarator")
    while current is not None and len(chain) < 16:
        chain.append(current)
        current = _cpp_inner_declarator(current)
    return chain


def _cpp_noise_edits(
    node: TreeSitterNode, source: bytes | None, edits: list[_Edit]
) -> None:
    """The edits that clean a parameter's text: every comment and attribute in
    ``node`` dropped, and every nested parameter list (a function pointer's) replaced
    by its normalised form. Walked with a stack, not by recursion, so a type nested
    hundreds deep (``A<A<…<int>…>>``) cannot exhaust Python's recursion limit."""
    stack = [node]
    while stack:
        for child in stack.pop().children:
            if child.type in _CPP_PARAMETER_NOISE:
                edits.append((child.start_byte, child.end_byte, " "))
            elif child.type == "parameter_list":
                types = _cpp_parameter_types(child, source)
                edits.append(
                    (child.start_byte, child.end_byte, f"({', '.join(types)})")
                )
            else:
                stack.append(child)


def _cpp_apply_edits(
    node: TreeSitterNode, source: bytes | None, end: int, edits: list[_Edit]
) -> str:
    """The text of ``node`` up to the byte ``end``, with ``edits`` applied (an edit
    inside an earlier one is dropped: the earlier one rewrote that text already)."""
    written = _cpp_bytes(node, source)
    start = node.start_byte
    kept = sorted(
        (edit for edit in edits if start <= edit[0] and edit[1] <= end),
        # at one position an insertion comes first, then the longest replacement
        key=lambda edit: (edit[0], edit[0] < edit[1], -edit[1]),
    )
    out: list[str] = []
    position = start
    for edit_start, edit_end, text in kept:
        if edit_start < position:
            continue
        out.append(
            written[position - start : edit_start - start].decode("utf-8", "replace")
        )
        out.append(text)
        position = edit_end
    out.append(written[position - start : end - start].decode("utf-8", "replace"))
    return "".join(out)


def _cpp_decay_edits(
    chain: list[TreeSitterNode], holder: int | None, named: bool, edits: list[_Edit]
) -> str:
    """The edits that decay the declarator holding a parameter's name (``holder`` in
    ``chain``) to a pointer when it is an array or a function: ``[...]`` is ``*``, or
    ``(*)`` when another array applies to it from outside (``int[3][4]`` is
    ``int (*)[4]``); an unnamed function type gains ``(*)``. What the name itself
    becomes: ``(*)`` for a named function type, else nothing."""
    if holder is None:
        return ""
    node = chain[holder]
    arrays = ("array_declarator", "abstract_array_declarator")
    if node.type in arrays:
        suffix_outside = any(outer.type in arrays for outer in chain[:holder])
        bracket = next((c for c in node.children if c.type == "["), None)
        start = bracket.start_byte if bracket is not None else node.start_byte
        edits.append((start, node.end_byte, "(*)" if suffix_outside else "*"))
    elif node.type == "function_declarator" and named:
        return "(*)"
    elif node.type == "abstract_function_declarator":
        edits.append((node.start_byte, node.start_byte, "(*)"))
    return ""


def _cpp_cv_edits(
    parameter: TreeSitterNode,
    holder: TreeSitterNode | None,
    source: bytes | None,
    edits: list[_Edit],
) -> bool:
    """The edits that drop the cv-qualifiers of the parameter itself: those of the
    pointer that holds its name (``int* const p``, not the ``const`` of
    ``int* const* p``, which is its pointee's), or its own specifiers' when no
    declarator holds the name (``const int x``); a reference, an array or a function
    there has none of its own. Whether the specifiers' were the ones."""
    if holder is None:
        qualified = parameter
    elif holder.type in ("pointer_declarator", "abstract_pointer_declarator"):
        qualified = holder
    else:
        return False
    for child in qualified.children:
        if (
            child.type == "type_qualifier"
            and _cpp_text(child, source) in _CPP_TOP_LEVEL_QUALIFIERS
        ):
            edits.append((child.start_byte, child.end_byte, ""))
    return holder is None


def _cpp_base_type_edits(
    parameter: TreeSitterNode,
    base: TreeSitterNode,
    *,
    reorder: bool,
    source: bytes | None,
    edits: list[_Edit],
) -> None:
    """The edits on a parameter's base type ``base``: the specifiers' ``const`` and
    ``volatile`` (when ``reorder``: they qualify a pointee, ``int const*``) written
    once, in that order, before the type; an elaborated ``struct S`` as ``S``; an
    integer type as the compiler spells it (``unsigned`` is ``unsigned int``)."""
    if reorder:
        specifiers = list(parameter.named_children)
        if base.type == "sized_type_specifier":
            specifiers.extend(base.named_children)
        present = {"const": False, "volatile": False}
        for qualifier in specifiers:
            if qualifier.type != "type_qualifier":
                continue
            written = _cpp_text(qualifier, source)
            if written not in present:
                continue
            present[written] = True
            edits.append((qualifier.start_byte, qualifier.end_byte, ""))
        prefix = "".join(f"{word} " for word, here in present.items() if here)
        if prefix:
            edits.append((base.start_byte, base.start_byte, prefix))
    if base.type in _CPP_CLASS_KINDS and base.child_by_field_name("body") is None:
        keyword = base.children[0] if base.children else None
        if keyword is not None and keyword.type in ("struct", "class", "union", "enum"):
            edits.append((keyword.start_byte, keyword.end_byte, ""))
    elif base.type == "sized_type_specifier":
        spelled = _cpp_sized_type(base, source)
        if spelled is not None:
            edits.append((base.start_byte, base.end_byte, spelled))


def _cpp_parameter_type(parameter: TreeSitterNode, source: bytes | None) -> str:
    """One parameter's type, normalised on the syntax tree so that every spelling the
    compiler reads as one type is one string: its comments, attributes, name and
    default value left out; its top-level cv-qualifiers dropped (inner ones, as in
    ``const int*``, kept); an array or a function type decayed to a pointer
    (``int[3]`` is ``int*``, ``int (int)`` is ``int (*)(int)``); ``struct X`` as
    ``X``; a function pointer's own parameters normalised alike; whitespace
    collapsed, ``&`` and ``*`` against the type (``const T&``)."""
    default = parameter.child_by_field_name("default_value")
    end = default.start_byte if default is not None else parameter.end_byte
    edits: list[_Edit] = []
    _cpp_noise_edits(parameter, source, edits)

    chain = _cpp_declarator_chain(parameter)
    name = (
        chain[-1]
        if chain and chain[-1].type in ("identifier", "field_identifier")
        else None
    )
    # the declarator that holds the name (or the innermost of an unnamed parameter)
    holder = next(
        (
            index
            for index in range(len(chain) - 1, -1, -1)
            if chain[index] != name
            and chain[index].type
            not in (
                "attributed_declarator",
                "parenthesized_declarator",
                "abstract_parenthesized_declarator",
            )
        ),
        None,
    )
    name_becomes = _cpp_decay_edits(chain, holder, name is not None, edits)
    if name is not None:
        edits.append((name.start_byte, name.end_byte, name_becomes))
    top_level = _cpp_cv_edits(
        parameter, chain[holder] if holder is not None else None, source, edits
    )
    base = parameter.child_by_field_name("type")
    if base is not None:
        _cpp_base_type_edits(
            parameter, base, reorder=not top_level, source=source, edits=edits
        )

    written = _cpp_apply_edits(parameter, source, end, edits).rstrip().rstrip("=")
    return _cpp_spaced_pointer_groups(
        _collapse(written)
        .replace(" &", "&")
        .replace(" *", "*")
        .replace("( ", "(")
        .replace(" )", ")")
    )


def _cpp_sized_type(node: TreeSitterNode, source: bytes | None) -> str | None:
    """A ``sized_type_specifier`` (``unsigned``, ``long int``, ``signed char``) spelled
    as the compiler spells its type: ``unsigned int``, ``long``, ``signed char``,
    ``long double``; ``signed`` and a redundant ``int`` dropped, ``char``'s sign kept
    (``char``, ``signed char`` and ``unsigned char`` are three types). ``None`` for a
    shape this does not know, which is then compared as written."""
    unsigned = short = signed = False
    longs = 0
    base: str | None = None
    for child in node.children:
        if child.type == "unsigned":
            unsigned = True
        elif child.type == "signed":
            signed = True
        elif child.type == "short":
            short = True
        elif child.type == "long":
            longs += 1
        elif child.type == "primitive_type":
            base = _cpp_text(child, source)
        elif child.type not in ("type_qualifier", "comment"):
            return None
    sign = "unsigned " if unsigned else ""
    if base == "char" and not short and longs == 0:
        return "unsigned char" if unsigned else "signed char" if signed else "char"
    if base == "double" and not short and longs == 1 and not unsigned and not signed:
        return "long double"
    if base not in (None, "int"):
        return None
    if short and longs == 0:
        return f"{sign}short"
    if not short and longs in (0, 1, 2):
        return f"{sign}{('int', 'long', 'long long')[longs]}"
    return None


def _cpp_spaced_pointer_groups(written: str) -> str:
    """``written`` with one space before each parenthesised pointer ``(*`` that follows
    a word, as ``int (*)(int)`` is spelled however it was written."""
    out: list[str] = []
    previous: str | None = None
    for index, char in enumerate(written):
        if (
            char == "("
            and written.startswith("*", index + 1)
            and previous is not None
            and previous not in " ("
        ):
            out.append(" ")
        out.append(char)
        previous = char
    return "".join(out)


def _cpp_parameter_types(parameters: TreeSitterNode, source: bytes | None) -> list[str]:
    """The normalised types of a parameter list's parameters (``...`` for C varargs);
    none for ``(void)``."""
    types: list[str] = []
    for parameter in parameters.children:
        if parameter.type in (
            "parameter_declaration",
            "optional_parameter_declaration",
            "variadic_parameter_declaration",
        ):
            types.append(_cpp_parameter_type(parameter, source))
        elif parameter.type in ("variadic_parameter", "..."):
            types.append("...")
    return [] if types == ["void"] else types


def cpp_signature(node: TreeSitterNode, source: bytes | None) -> str | None:
    """What tells a function's overloads apart: its normalised parameter types,
    ``, ``-joined in parentheses, then the cv- and ref-qualifiers of a member function
    as written (``(int) const``, ``() &&``). ``noexcept``, ``override`` and a trailing
    return type are left out: no overload differs by them alone."""
    cast = _cpp_operator_cast(node)
    if cast is not None:
        # a conversion operator's parameters and qualifiers are its cast's
        # (``operator bool() const``), not those of a list inside the target type
        parameters = _cpp_conversion_parameters(cast)
        declarator = parameters.parent if parameters is not None else None
    else:
        declarator = cpp_function_declarator(node)
        parameters = (
            declarator.child_by_field_name("parameters")
            if declarator is not None
            else None
        )
    if declarator is None or parameters is None:
        return None
    signature = f"({', '.join(_cpp_parameter_types(parameters, source))})"
    for child in declarator.children:
        if child.type == "type_qualifier":
            qualifier = _cpp_text(child, source)
            if qualifier not in ("const", "volatile"):
                continue
        elif child.type == "ref_qualifier":
            qualifier = _cpp_text(child, source)
        else:
            continue
        signature += f" {qualifier}"
    return signature


# --- C and C++: the names a whole file decides ---------------------------------


def _cpp_qualified_with_arguments(node: TreeSitterNode, source: bytes | None) -> bool:
    """``node`` may be named otherwise by the file's partial specialisations
    (:class:`_PartialSpecs`): a function whose name is qualified with a template
    argument list."""
    if node.type not in ("function_definition", "declaration", "field_declaration"):
        return False
    cast = _cpp_operator_cast(node)
    if cast is not None:
        declarator = node.child_by_field_name("declarator")
        if declarator is None:
            return False
        head = _cpp_bytes(declarator, source)[: cast.start_byte - declarator.start_byte]
        return b"<" in head
    declarator = cpp_function_declarator(node)
    inner = declarator.child_by_field_name("declarator") if declarator else None
    return (
        inner is not None
        and inner.type == "qualified_identifier"
        and b"<" in _cpp_bytes(inner, source)
    )


def _cpp_has_body_entity(node: TreeSitterNode) -> bool:
    """``node`` is a definition with a body, which a name must tell apart from every
    other: a function, a class, struct, union or enum with its body, a namespace."""
    if node.type in ("function_definition", "namespace_definition"):
        return True
    return node.type in _CPP_CLASS_KINDS and _cpp_has_body(node)


def _cpp_leaf_key(name: str) -> str:
    """What two names that could be the same end in: the last part of ``name`` without
    its argument list, every conversion operator as ``operator `` (it only picks which
    entities :func:`cpp_renames` compares)."""
    last = _cpp_split(name)[-1]
    if _cpp_operator_at(last, 0):
        return "operator " if last[len("operator") :].startswith(" ") else last
    return _strip_template_args(last)


def _cpp_written_leaf(node: TreeSitterNode, source: bytes | None) -> str | None:
    """:func:`_cpp_leaf_key` of ``node``'s name, read from its name node without naming
    it."""
    if _cpp_operator_cast(node) is not None:
        return "operator "
    if node.type in ("function_definition", "declaration", "field_declaration"):
        declarator = cpp_function_declarator(node)
        name = (
            declarator.child_by_field_name("declarator")
            if declarator is not None
            else None
        )
    elif node.type == "namespace_definition":
        name = node.child_by_field_name("name")
        if name is None:
            return "(anonymous namespace)"
    else:
        name = node.child_by_field_name("name")
    if name is None:
        return None
    return _cpp_leaf_key(_squeeze(_cpp_text_without_comments(name, source)))


@dataclass(frozen=True)
class _Seen:
    """One entity :func:`cpp_renames` compares."""

    node: TreeSitterNode
    alone: EntityName
    """Its name as the node alone gives it."""
    named: EntityName
    """Its name with what the file adds to one node."""
    full: EntityName | None
    """Its name with every container kept, when one is left out."""


@dataclass
class _Found:
    """What the one walk of :func:`cpp_renames` finds."""

    spec_nodes: list[TreeSitterNode] = field(default_factory=list)
    """The classes that may be partial specialisations (:func:`_cpp_templated_class`),
    read once the inline namespaces are known."""
    inline_paths: set[str] = field(default_factory=set)
    """The paths of its inline namespaces (:func:`_cpp_inline_paths_of`)."""
    inline_names: set[str] = field(default_factory=set)
    """Their own names (``v2``), one of which a qualifier through one holds."""
    left_out: list[TreeSitterNode] = field(default_factory=list)
    """The entities that leave a container out."""
    bodies: list[TreeSitterNode] = field(default_factory=list)
    """The other definitions."""
    qualified: list[TreeSitterNode] = field(default_factory=list)
    """The other functions qualified with arguments."""
    through: list[TreeSitterNode] = field(default_factory=list)
    """The functions named through a written qualifier
    (:func:`_cpp_written_qualifier`)."""


def _cpp_written_qualifier(node: TreeSitterNode, source: bytes | None) -> str | None:
    """The written qualified name of the function ``node`` (``lib::v2::g`` of
    ``void lib::v2::g() {}``, ``lib::v1::W::`` of a conversion operator
    ``lib::v1::W::operator int()``), when it has one."""
    if node.type not in ("function_definition", "declaration", "field_declaration"):
        return None
    cast = _cpp_operator_cast(node)
    if cast is not None:
        declarator = node.child_by_field_name("declarator")
        if declarator is None:
            return None
        head = _cpp_bytes(declarator, source)[: cast.start_byte - declarator.start_byte]
        return head.decode("utf-8", "replace") if b"::" in head else None
    declarator = cpp_function_declarator(node)
    inner = declarator.child_by_field_name("declarator") if declarator else None
    if inner is None or inner.type != "qualified_identifier":
        return None
    return _cpp_text(inner, source)


def _cpp_class_through_inline(
    node: TreeSitterNode, source: bytes | None, inline_names: set[str]
) -> bool:
    """The class ``node``'s head is written through a qualifier that holds the name of
    an inline namespace of the file met so far (``struct lib::v2::X {…}``, one of
    ``inline_names``)."""
    if node.type not in _CPP_CLASS_KINDS:
        return False
    name = node.child_by_field_name("name")
    # tree-sitter-cpp reads a qualified class name as this kind
    return (
        name is not None
        and name.type == "qualified_identifier"
        and any(word in inline_names for word in _cpp_words(_cpp_text(name, source)))
    )


def cpp_renames(
    root: TreeSitterNode, source: bytes | None, prefix: Callable[[int], str]
) -> dict[int, EntityName]:
    """The C++ entities under ``root`` named otherwise than the node alone names them,
    by the end of their name, with that name.

    An out-of-line qualifier the same as a partial specialisation of the file but for
    its parameter names is spelled as that specialisation (:class:`_PartialSpecs`).

    An inline namespace and a friend's classes are left out of a name
    (:func:`_cpp_containers`), and so is an inline namespace of the file a written
    qualifier names (``void lib::v2::g() {}`` is ``lib::g``, its full chain
    ``lib::v2::g``: :func:`_cpp_without_inline_parts`), except where that makes two
    definitions with a body share a name and parameters that the full chain kept
    apart: then every entity of that name and parameters that leaves a container out
    (its declarations too) keeps the full chain, so no marker credits another
    definition, and so does everything a class or namespace that keeps it holds. A
    declaration and one definition do not collide (a friend declared in its class and
    defined in its namespace stays one entity). The name compared is ``prefix`` (the
    namespaces the file's own macros open around a name ending at a byte) and the
    name, and the parameters are the normalised signature (:func:`cpp_signature`).

    Only the entities that leave a container out, and the definitions whose name ends
    as one of theirs does, are named here: a file with neither friends nor inline
    namespaces costs one walk of its tree, which skips every function body.
    """
    # one walk: the partial specialisations, the inline namespaces, what leaves a
    # container out, the other definitions, the functions a specialisation may spell,
    # and those named through a written qualifier
    found = _Found()
    cursor = root.walk()
    # whether an inline namespace is around the cursor's node, per depth
    inside = [False]
    while True:
        node = cursor.node
        if node is None:  # a cursor always stands on a node
            return _cpp_renamed(source, prefix, found)
        in_inline = inside[-1]
        inline_here = node.type == "namespace_definition" and (
            _cpp_inline_namespace_or_part(node)
            or _cpp_reopens_inline(node, source, prefix, found.inline_paths)
        )
        # a class head written through an inline namespace leaves it out, and so does
        # everything the class holds
        through_here = not inline_here and _cpp_class_through_inline(
            node, source, found.inline_names
        )
        if _cpp_templated_class(node):
            found.spec_nodes.append(node)
        if inline_here:
            for path in _cpp_inline_paths_of(node, source, prefix):
                found.inline_names.add(path.rsplit("::", 1)[-1])
                found.inline_paths.add(path)
        if is_entity(node, CommentType.cpp):
            if _cpp_written_qualifier(node, source) is not None:
                found.through.append(node)
            if in_inline or inline_here or through_here or _cpp_is_friend(node):
                found.left_out.append(node)
            else:
                if _cpp_has_body_entity(node):
                    found.bodies.append(node)
                if _cpp_qualified_with_arguments(node, source):
                    found.qualified.append(node)
        # nothing a function's body holds is a friend, an inline namespace or a
        # partial specialisation, or names one
        if node.type != "function_definition" and cursor.goto_first_child():
            inside.append(in_inline or inline_here or through_here)
            continue
        while not cursor.goto_next_sibling():
            if not cursor.goto_parent():
                return _cpp_renamed(source, prefix, found)
            inside.pop()


def _cpp_leave_out_through_inline(
    source: bytes | None, naming: _CppNaming, found: _Found
) -> set[int]:
    """The functions of ``found.through`` whose written qualifier may name an inline
    namespace of the file (one of its inline names is among its words) that ``naming``
    names otherwise than as written and that are not in ``found.left_out``, moved there
    from ``found.bodies``, by node id: they leave a container out, their full chain the
    qualifier as written."""
    if naming.inline is None:
        return set()
    through = [
        node
        for node in found.through
        if (head := _cpp_written_qualifier(node, source)) is not None
        and any(word in found.inline_names for word in _cpp_words(head))
    ]
    left = {node.id for node in found.left_out}
    as_written = replace(naming, inline=None)
    moved: set[int] = set()
    for node in through:
        if node.id in left:
            continue
        named = _cpp_describe_in(node, source, naming)
        written = _cpp_describe_in(node, source, as_written)
        if (named and named.qualified_name) != (written and written.qualified_name):
            moved.add(node.id)
            found.left_out.append(node)
    found.bodies = [node for node in found.bodies if node.id not in moved]
    return moved


def _cpp_renamed(
    source: bytes | None, prefix: Callable[[int], str], found: _Found
) -> dict[int, EntityName]:
    """:func:`cpp_renames`, once its walk has found what it looks for
    (:class:`_Found`)."""
    base = _CppNaming(
        inline=frozenset(found.inline_paths) if found.inline_paths else None,
        macros=prefix,
    )
    specs = _PartialSpecs.of(found.spec_nodes, source, base)
    with_specs = replace(base, specs=specs if specs.by_template else None)
    full_chain = replace(with_specs, full_chain=True)
    moved = _cpp_leave_out_through_inline(source, with_specs, found)

    def named_alone(node: TreeSitterNode) -> tuple[EntityName, EntityName] | None:
        alone = _cpp_describe_in(node, source, _ALONE)
        if alone is None or alone.qualified_name is None or alone.name_end is None:
            return None
        named = alone
        if with_specs.inline is not None or (
            with_specs.specs is not None and _cpp_qualified_with_arguments(node, source)
        ):
            named = _cpp_describe_in(node, source, with_specs) or alone
        return alone, named

    out: dict[int, EntityName] = {}
    for node in found.qualified if with_specs.specs is not None else ():
        if node.id in moved:
            continue
        names = named_alone(node)
        if names is None:
            continue
        alone, named = names
        if named.qualified_name != alone.qualified_name and named.name_end is not None:
            out[named.name_end] = named
    # the entities that leave a container out, named both ways
    seen: list[_Seen] = []
    for node in found.left_out:
        names = named_alone(node)
        if names is None:
            continue
        alone, named = names
        full = _cpp_describe_in(node, source, full_chain)
        if full is not None and full.qualified_name == named.qualified_name:
            full = None
        if (
            full is None
            and named.qualified_name != alone.qualified_name
            and named.name_end is not None
        ):
            out[named.name_end] = named
        seen.append(_Seen(node, alone, named, full))
    leaves = {
        _cpp_leaf_key(entity.named.qualified_name)
        for entity in seen
        if entity.full is not None and entity.named.qualified_name is not None
    }
    if not leaves:
        return out
    # the other definitions that could share a name with one of them
    for node in found.bodies:
        if _cpp_written_leaf(node, source) in leaves:
            names = named_alone(node)
            if names is not None:
                seen.append(_Seen(node, *names, None))
    _cpp_keep_full_chains_where_names_collide(seen, source, prefix, out)
    return out


def _cpp_chain_of(name: EntityName, prefix: Callable[[int], str]) -> str:
    """``name`` after the namespaces the file's macros open around it: what two full
    chains are compared by."""
    at = prefix(name.name_end) if name.name_end is not None else ""
    return at + (name.qualified_name or "")


def _cpp_held_by(chain: str, containers: set[str]) -> bool:
    """The chain ``chain`` is inside one of ``containers`` (one of them is a leading
    part of it, ``lib::v1::Widget`` of ``lib::v1::Widget::draw``)."""
    parts = _cpp_split(chain)
    return any(
        "::".join(parts[: count + 1]) in containers for count in range(len(parts) - 1)
    )


def _cpp_keep_full_chains_where_names_collide(
    seen: list[_Seen],
    source: bytes | None,
    prefix: Callable[[int], str],
    out: dict[int, EntityName],
) -> None:
    """The names of ``seen`` into ``out`` where they differ from the names alone: each
    one that leaves a container out keeps its full chain where its name and
    parameters are those of two definitions whose full chains differ, and so does
    everything a class or namespace that keeps its full chain holds (its members are
    named in it), but a friend, which is named in its namespace."""
    keys = [
        (_cpp_chain_of(entity.named, prefix), cpp_signature(entity.node, source))
        for entity in seen
    ]
    chains: dict[tuple[str, str | None], set[str]] = {}
    for entity, key in zip(seen, keys, strict=True):
        if _cpp_has_body_entity(entity.node):
            full = entity.full or entity.named
            chains.setdefault(key, set()).add(_cpp_chain_of(full, prefix))
    collides = [
        entity.full is not None and len(chains.get(key, ())) > 1
        for entity, key in zip(seen, keys, strict=True)
    ]
    # the classes and namespaces that keep their full chain
    kept = {
        _cpp_chain_of(entity.full, prefix)
        for entity, collide in zip(seen, collides, strict=True)
        if collide
        and entity.full is not None
        and _cpp_has_body_entity(entity.node)
        and entity.node.type != "function_definition"
    }
    for entity, collide in zip(seen, collides, strict=True):
        if entity.full is None:
            continue
        # a friend is named in its namespace, never in its class
        keeps = collide or (
            bool(kept)
            and not _cpp_is_friend(entity.node)
            and _cpp_held_by(_cpp_chain_of(entity.full, prefix), kept)
        )
        name = entity.full if keeps else entity.named
        if (
            name.qualified_name != entity.alone.qualified_name
            and name.name_end is not None
        ):
            out[name.name_end] = name


class CppNames:
    """What the names of a C++ file's entities take from the whole file, beyond what
    one node shows: the namespaces the file's own macros open
    (:class:`~sphinx_codelinks.analyse.cpp_macros.MacroScopes`), and the entities named
    otherwise than one node names them (:func:`cpp_renames`: a name spelled as the
    file's partial specialisation spells it; an inline namespace or a friend's classes
    kept where leaving them out would give two definitions one name).

    Made once per parse, by :func:`sphinx_codelinks.analyse.utils.parse_source`; the
    renames are worked out when a marker of the file first asks for a name, so a file
    without markers costs nothing.
    """

    def __init__(
        self, source: bytes, root: TreeSitterNode, macros: MacroScopes | None = None
    ) -> None:
        self.source = source
        """The file as written: what every name is read from."""
        self.macros = macros if macros is not None else MacroScopes()
        """The namespaces the file's own macros open."""
        self._root = root
        self._renamed: dict[int, EntityName] | None = None

    @property
    def renamed(self) -> dict[int, EntityName]:
        """The entities named otherwise, by the end of their name: the name and its
        parts, before the macros' namespaces."""
        if self._renamed is None:
            self._renamed = cpp_renames(self._root, self.source, self._prefix)
        return self._renamed

    def _prefix(self, name_end: int) -> str:
        """The namespaces the file's macros open around a name ending at ``name_end``,
        each followed by ``::``."""
        return "".join(f"{n}::" for n in self.macros.namespaces_at(name_end))

    def qualify(self, name: EntityName, start_line: int) -> EntityName:
        """``name``, an entity's name as its node alone gives it, as the whole file
        names it: renamed where the file decides so, then prefixed with the namespaces
        the file's macros open around the name's end, or, for an entity with no name
        node (an anonymous namespace), around ``start_line``, its 1-based first
        line."""
        qualified_name, semantic = name.qualified_name, name.semantic
        if name.name_end is not None:
            renamed = self.renamed.get(name.name_end)
            if renamed is not None:
                qualified_name, semantic = renamed.qualified_name, renamed.semantic
            namespaces = self.macros.namespaces_at(name.name_end)
        else:
            namespaces = self.macros.namespaces_at_line(start_line)
        if namespaces:
            if qualified_name is not None:
                qualified_name = "::".join([*namespaces, qualified_name])
            if semantic is not None:
                semantic = (
                    *(_element("namespace", namespace) for namespace in namespaces),
                    *semantic,
                )
        return replace(name, qualified_name=qualified_name, semantic=semantic)


# --- Python ------------------------------------------------------------------


def _python_semantic(definitions: list[tuple[str, str]]) -> list[SemanticElement]:
    """The components of a ``__qualname__``, from its definitions (node type, name),
    outermost first: a class, or a function -- a ``method`` directly in a class.
    CPython's ``<locals>`` is not one: :func:`render_semantic` writes it."""
    elements: list[SemanticElement] = []
    container: str | None = None
    for node_type, name in definitions:
        if node_type == "class_definition":
            kind = "class"
        else:
            kind = "method" if container == "class_definition" else "function"
        elements.append(_element(kind, name))
        container = node_type
    return elements


def _python_describe(node: TreeSitterNode) -> EntityName | None:
    """CPython's ``__qualname__``: ``Class.method``, ``outer.<locals>.inner``."""
    if node.type not in ("function_definition", "class_definition"):
        return None
    name = node.child_by_field_name("name")
    if name is None:
        return None
    segments: list[str] = []
    definitions = [(node.type, _text(name))]
    nearest: str | None = None
    parent = node.parent
    while parent is not None:
        if parent.type in ("class_definition", "function_definition"):
            nearest = nearest or parent.type
            parent_name = _text(parent.child_by_field_name("name"))
            segments.append(
                parent_name
                if parent.type == "class_definition"
                else f"{parent_name}.<locals>"
            )
            definitions.append((parent.type, parent_name))
        parent = parent.parent
    qualified = ".".join([*reversed(segments), _text(name)])
    semantic = _python_semantic(definitions[::-1])
    if node.type == "class_definition":
        return _named("class", qualified, semantic)
    return _named(
        "method" if nearest == "class_definition" else "function", qualified, semantic
    )


# --- Rust --------------------------------------------------------------------

_RUST_KINDS: dict[str, EntityKind] = {
    "function_item": "function",
    "function_signature_item": "function",
    "struct_item": "struct",
    "enum_item": "enum",
    "union_item": "union",
    "trait_item": "trait",
    "mod_item": "module",
    "type_item": "type",
    "macro_definition": "macro",
}


def _rust_modules(node: TreeSitterNode) -> list[str]:
    segments: list[str] = []
    parent = node.parent
    while parent is not None:
        if parent.type == "mod_item":
            segments.append(_text(parent.child_by_field_name("name")))
        parent = parent.parent
    return list(reversed(segments))


def _rust_type(node: TreeSitterNode | None, modules: list[str]) -> str:
    """A type or trait as written: whitespace collapsed, a leading ``crate::`` dropped,
    and a bare name prefixed with the in-file module path."""
    text = _collapse(_text(node)).removeprefix("crate::")
    bare = node is not None and node.type in ("type_identifier", "generic_type")
    if bare and "::" not in text and modules:
        return "::".join([*modules, text])
    return text


# The self types rustc prints without brackets in an inherent impl's path: a path
# (``Widget``, ``a::Widget``, ``Widget<T>``) or a primitive.
_RUST_PATH_TYPES = frozenset(
    {"type_identifier", "generic_type", "scoped_type_identifier", "primitive_type"}
)


def _rust_impl_segment(impl: TreeSitterNode) -> str:
    """``Widget`` for an inherent impl, ``<dyn Shape>`` for an inherent impl of a type
    that is no path, ``<Widget as Shape>`` for a trait impl."""
    modules = _rust_modules(impl)
    self_node = impl.child_by_field_name("type")
    self_type = _rust_type(self_node, modules)
    trait = impl.child_by_field_name("trait")
    if trait is None:
        if self_node is not None and self_node.type not in _RUST_PATH_TYPES:
            return f"<{self_type}>"
        return self_type
    return f"<{self_type} as {_rust_type(trait, modules)}>"


def _rust_impl_parts(impl: TreeSitterNode) -> list[SemanticElement]:
    """An impl as components: the in-file modules it is written in, each a ``module``
    component of its own, then the impl, named after its self type as written and,
    for a trait impl, carrying the trait as the qualified name spells it.

    The self type is written without the modules (``G`` in ``mod m``): rendering
    prefixes them again where the qualified name does (:func:`_rust_render`). A path
    from the crate root keeps its ``crate::`` where dropping it would leave a name the
    rendering prefixes (``crate::G`` in ``mod k`` is ``Q``, not ``k::Q``)."""
    modules = _rust_modules(impl)
    self_node = impl.child_by_field_name("type")
    written = _collapse(_text(self_node))
    name = written.removeprefix("crate::")
    prefixed = (
        bool(modules)
        and self_node is not None
        and self_node.type in ("type_identifier", "generic_type")
        and "::" not in name
    )
    if not prefixed and modules and written != name and _rust_resolves_in_module(name):
        name = written
    element = _element("impl", name)
    trait = impl.child_by_field_name("trait")
    if trait is not None:
        element["trait"] = _rust_type(trait, modules)
    return [*(_element("module", module) for module in modules), element]


def _rust_functions(functions: list[str], *, in_item: bool) -> list[SemanticElement]:
    """The functions between an item and its impl, trait or module, outermost first:
    the one directly in an impl or a trait (``in_item``) is a method."""
    return [
        _element("method" if in_item and index == 0 else "function", name)
        for index, name in enumerate(functions)
    ]


def _rust_describe(node: TreeSitterNode) -> EntityName | None:
    if node.type == "impl_item":
        return _named("impl", _rust_impl_segment(node), _rust_impl_parts(node))
    kind = _RUST_KINDS.get(node.type)
    name = node.child_by_field_name("name")
    if kind is None or name is None:
        return None
    own = _text(name)
    is_fn = node.type in ("function_item", "function_signature_item")
    functions: list[str] = []
    parent = node.parent
    while parent is not None:
        # a function directly in an impl or a trait is a method; one nested in a
        # method is a function
        method = is_fn and not functions
        own_kind: EntityKind = "method" if method else kind
        if parent.type == "impl_item":
            outer = list(reversed(functions))
            return _named(
                own_kind,
                "::".join([_rust_impl_segment(parent), *outer, own]),
                [
                    *_rust_impl_parts(parent),
                    *_rust_functions(outer, in_item=True),
                    _element(own_kind, own),
                ],
            )
        if parent.type == "trait_item":
            modules = _rust_modules(parent)
            trait_name = _text(parent.child_by_field_name("name"))
            outer = list(reversed(functions))
            return _named(
                own_kind,
                "::".join([*modules, trait_name, *outer, own]),
                [
                    *(_element("module", module) for module in modules),
                    _element("trait", trait_name),
                    *_rust_functions(outer, in_item=True),
                    _element(own_kind, own),
                ],
            )
        if parent.type == "function_item":
            functions.append(_text(parent.child_by_field_name("name")))
        if parent.type == "mod_item":
            break
        parent = parent.parent
    modules = _rust_modules(node)
    outer = list(reversed(functions))
    return _named(
        kind,
        "::".join([*modules, *outer, own]),
        [
            *(_element("module", module) for module in modules),
            *_rust_functions(outer, in_item=False),
            _element(kind, own),
        ],
    )


# --- C# ----------------------------------------------------------------------

_CSHARP_KINDS: dict[str, EntityKind] = {
    "class_declaration": "class",
    "struct_declaration": "struct",
    "interface_declaration": "interface",
    "record_declaration": "record",
    "enum_declaration": "enum",
    "namespace_declaration": "namespace",
    "file_scoped_namespace_declaration": "namespace",
    "method_declaration": "method",
    "constructor_declaration": "constructor",
    "destructor_declaration": "destructor",
    "property_declaration": "property",
    "indexer_declaration": "indexer",
    "operator_declaration": "operator",
    "conversion_operator_declaration": "operator",
    "event_declaration": "event",
    "delegate_declaration": "delegate",
    "local_function_statement": "function",
}
_CSHARP_CONTAINERS = {
    "class_declaration",
    "struct_declaration",
    "interface_declaration",
    "record_declaration",
    "enum_declaration",
    "namespace_declaration",
    "method_declaration",
    "constructor_declaration",
    "local_function_statement",
}


def _csharp_own_name(node: TreeSitterNode) -> str | None:
    if node.type == "indexer_declaration":
        return "this[]"
    if node.type == "operator_declaration":
        symbol = next(
            (
                node.children[index + 1]
                for index, child in enumerate(node.children[:-1])
                if child.type == "operator"
            ),
            None,
        )
        return f"operator {_text(symbol)}" if symbol is not None else None
    if node.type == "conversion_operator_declaration":
        return f"operator {_squeeze(_text(node.child_by_field_name('type')))}"
    name = node.child_by_field_name("name")
    if name is None:
        return None
    own = _squeeze(_text(name))
    return f"~{own}" if node.type == "destructor_declaration" else own


def _csharp_elements(node: TreeSitterNode, own: str) -> list[SemanticElement]:
    """``node``, named ``own``, as components: a namespace's dotted name
    (``Acme.Gfx``) is a namespace per part."""
    kind = _CSHARP_KINDS[node.type]
    if kind == "namespace":
        return [_element(kind, part) for part in own.split(".")]
    return [_element(kind, own)]


def _csharp_describe(node: TreeSitterNode) -> EntityName | None:
    kind = _CSHARP_KINDS.get(node.type)
    if kind is None:
        return None
    segments: list[str] = []
    groups: list[list[SemanticElement]] = []
    parent = node.parent
    root = node
    while parent is not None:
        if parent.type in _CSHARP_CONTAINERS:
            container = _csharp_own_name(parent)
            if container is not None:
                segments.append(container)
                groups.append(_csharp_elements(parent, container))
        root = parent
        parent = parent.parent
    segments.reverse()
    groups.reverse()
    # a file-scoped namespace (``namespace A.B;``) is a sibling of what it holds
    if node.type != "file_scoped_namespace_declaration":
        for child in root.named_children:
            if child.start_byte >= node.start_byte:
                break
            if child.type == "file_scoped_namespace_declaration":
                namespace = _csharp_own_name(child) or ""
                segments.insert(0, namespace)
                groups.insert(0, _csharp_elements(child, namespace))
    own = _csharp_own_name(node)
    return _named(
        kind,
        _join(".", segments, own),
        [
            *(element for group in groups for element in group),
            *_csharp_elements(node, own or ""),
        ],
    )


# --- Go ----------------------------------------------------------------------


def _go_spec_kind(spec: TreeSitterNode) -> EntityKind:
    value = spec.child_by_field_name("type")
    if spec.type == "type_spec" and value is not None:
        if value.type == "struct_type":
            return "struct"
        if value.type == "interface_type":
            return "interface"
    return "type"


def _go_receiver(node: TreeSitterNode) -> str | None:
    """The receiver's type name, as ``go doc`` writes it (no ``*``, no type arguments)."""
    receiver = node.child_by_field_name("receiver")
    if receiver is None:
        return None
    for parameter in receiver.named_children:
        value = parameter.child_by_field_name("type")
        while value is not None and value.type in ("pointer_type", "generic_type"):
            value = (
                value.named_children[0]
                if value.type == "pointer_type" and value.named_children
                else value.child_by_field_name("type")
            )
        if value is not None:
            return _text(value)
    return None


def _go_describe(node: TreeSitterNode) -> EntityName | None:
    if node.type == "function_declaration":
        own = _text(node.child_by_field_name("name")) or None
        return _named("function", own, [_element("function", own or "")])
    if node.type == "method_declaration":
        own = _text(node.child_by_field_name("name"))
        # the receiver's type: what it is, its declaration (maybe in another file) says
        receiver = _go_receiver(node)
        if receiver:
            return _named(
                "method",
                f"{receiver}.{own}",
                [_element("type", receiver), _element("method", own)],
            )
        return _named("method", own, [_element("method", own)])
    if node.type == "type_declaration":
        specs = [
            child
            for child in node.named_children
            if child.type in ("type_spec", "type_alias")
        ]
        if len(specs) != 1:
            return EntityName("type", None, None)
        node = specs[0]
    if node.type in ("type_spec", "type_alias"):
        spec_kind = _go_spec_kind(node)
        spec_name = _text(node.child_by_field_name("name")) or None
        return _named(spec_kind, spec_name, [_element(spec_kind, spec_name or "")])
    if node.type == "method_elem":
        own = _text(node.child_by_field_name("name"))
        parent = node.parent
        while parent is not None and parent.type != "type_spec":
            parent = parent.parent
        owner = _text(parent.child_by_field_name("name")) if parent is not None else ""
        if parent is not None and owner:
            return _named(
                "method",
                f"{owner}.{own}",
                [_element(_go_spec_kind(parent), owner), _element("method", own)],
            )
        return _named("method", own, [_element("method", own)])
    return None


# --- TypeScript and JavaScript ----------------------------------------------

_TS_KINDS: dict[str, EntityKind] = {
    "function_declaration": "function",
    "generator_function_declaration": "function",
    "function_signature": "function",
    "class_declaration": "class",
    "abstract_class_declaration": "class",
    "class": "class",
    "interface_declaration": "interface",
    "type_alias_declaration": "type",
    "enum_declaration": "enum",
    "module": "namespace",
    "internal_module": "namespace",
    "method_definition": "method",
    "method_signature": "method",
    "abstract_method_signature": "method",
    "public_field_definition": "method",
}
_TS_NAMED_CONTAINERS = {
    "class_declaration",
    "abstract_class_declaration",
    "class",
    "interface_declaration",
    "module",
    "internal_module",
    "function_declaration",
    "generator_function_declaration",
    "method_definition",
}


def _ts_value_kind(value: TreeSitterNode | None) -> EntityKind | None:
    value = _unwrap_ts_value(value)
    if value is None:
        return None
    if value.type == "class":
        return "class"
    if value.type in TS_FUNCTION_VALUE_TYPES:
        return "function"
    return None


def _ts_declarator(
    node: TreeSitterNode,
) -> tuple[TreeSitterNode | None, EntityKind | None]:
    """The declarator a ``const``/``let``/``var`` is named after, and its kind."""
    declarators = [c for c in node.named_children if c.type == "variable_declarator"]
    for declarator in declarators:
        kind = _ts_value_kind(declarator.child_by_field_name("value"))
        if kind is not None:
            return declarator, kind
    for declarator in declarators:
        annotation = declarator.child_by_field_name("type")
        if annotation is not None and any(
            child.type == "function_type" for child in annotation.named_children
        ):
            return declarator, "function"
    return (declarators[0] if declarators else None), None


def _ts_elements(kind: str, name: TreeSitterNode) -> list[SemanticElement]:
    """A declaration's name as components: a dotted namespace name (``namespace
    A.B``) is a namespace per part; any other name, a string one included, is one."""
    text = _collapse(_text(name))
    if name.type == "nested_identifier":
        return [_element(kind, part) for part in text.split(".")]
    return [_element(kind, text)]


def _ts_containers(node: TreeSitterNode) -> tuple[list[str], list[SemanticElement]]:
    segments: list[str] = []
    groups: list[list[SemanticElement]] = []
    parent = node.parent
    while parent is not None:
        if parent.type in _TS_NAMED_CONTAINERS:
            name = parent.child_by_field_name("name")
            if name is not None:
                segments.append(_collapse(_text(name)))
                groups.append(_ts_elements(_TS_KINDS[parent.type], name))
        elif parent.type == "variable_declarator":
            value_kind = _ts_value_kind(parent.child_by_field_name("value"))
            if value_kind is not None:
                declared = _text(parent.child_by_field_name("name"))
                segments.append(declared)
                groups.append([_element(value_kind, declared)])
        parent = parent.parent
    return (
        list(reversed(segments)),
        [element for group in reversed(groups) for element in group],
    )


def _ts_describe(node: TreeSitterNode) -> EntityName | None:
    prefix, outer = _ts_containers(node)
    if node.type in ("lexical_declaration", "variable_declaration"):
        declarator, kind = _ts_declarator(node)
        if declarator is None or kind is None:
            return None
        declared = _text(declarator.child_by_field_name("name"))
        return _named(
            kind, _join(".", prefix, declared), [*outer, _element(kind, declared)]
        )
    if node.type == "assignment_expression":
        kind = _ts_value_kind(node.child_by_field_name("right"))
        if kind is None:
            return None
        # the left-hand side is an expression, not a chain of containers: one component
        left = _collapse(_text(node.child_by_field_name("left")))
        return _named(kind, _join(".", prefix, left), [*outer, _element(kind, left)])
    if node.type == "export_statement":
        kind = _ts_value_kind(node.child_by_field_name("value"))
        if kind is None:
            return None
        return _named(
            kind, _join(".", prefix, "default"), [*outer, _element(kind, "default")]
        )
    kind = _TS_KINDS.get(node.type)
    if kind is None:
        return None
    name = node.child_by_field_name("name")
    if name is None:
        return EntityName(kind, None, None)
    return _named(
        kind,
        _join(".", prefix, _collapse(_text(name))),
        [*outer, *_ts_elements(kind, name)],
    )


# --- Bash, YAML and JSON -----------------------------------------------------


def _bash_describe(node: TreeSitterNode) -> EntityName | None:
    if node.type != "function_definition":
        return None
    own = _text(node.child_by_field_name("name")) or None
    return _named("function", own, [_element("function", own or "")])


def _data_describe(node: TreeSitterNode) -> EntityName:
    """A YAML or JSON entry: a key/value pair is a ``key``, anything else an ``item``."""
    is_pair = node.type in ("block_mapping_pair", "flow_pair", "pair")
    return EntityName("key" if is_pair else "item", None, None)


_DESCRIBERS: dict[CommentType, Callable[[TreeSitterNode], EntityName | None]] = {
    CommentType.cpp: _cpp_describe,
    CommentType.python: _python_describe,
    CommentType.rust: _rust_describe,
    CommentType.cs: _csharp_describe,
    CommentType.go: _go_describe,
    CommentType.ts: _ts_describe,
    CommentType.bash: _bash_describe,
    CommentType.yaml: _data_describe,
    CommentType.jsonc: _data_describe,
}


def describe_entity(
    node: TreeSitterNode, comment_type: CommentType, *, source: bytes | None = None
) -> EntityName | None:
    """Name the definition ``node``: its kind, its in-file qualified name, and the
    components of that name.

    Pure: it reads the node and its ancestors (and, for a C# file-scoped namespace, the
    file's top-level siblings), never the file system.

    :param node: A definition node, as association binds it.
    :param comment_type: The language of the file ``node`` was parsed from.
    :param source: The file as written, which a C or C++ name is read from when given
        (its tree may be parsed from a prepared copy); else the tree's own text.
    :return: The name, or ``None`` if ``node`` is no entity this function can name.
    """
    if comment_type == CommentType.cpp:
        return _cpp_describe_in(node, source, _ALONE)
    describer = _DESCRIBERS.get(comment_type)
    return describer(node) if describer is not None else None


# --- Rendering the components ------------------------------------------------


def _rust_is_path(text: str) -> bool:
    """``text`` is a type rustc writes without brackets in a path: a name, a path or a
    primitive, with any generic arguments (``Widget``, ``a::Widget<dyn Fn() -> u8>``,
    ``u32``) -- not ``dyn Shape``, ``&T``, ``[T]``, a tuple or a function type."""
    if text and not (_is_ident_char(text[0]) or text[0] == ":"):
        return False
    depth = 0
    previous = ""
    for char in text:
        if char in "<([":
            depth += 1
        elif depth and (char in ")]" or (char == ">" and previous != "-")):
            depth -= 1
        elif depth == 0 and not (_is_ident_char(char) or char == ":"):
            return False
        previous = char
    return True


# The types tree-sitter-rust reads as ``primitive_type``: never prefixed with a module.
_RUST_PRIMITIVES = frozenset(
    {
        "bool",
        "char",
        "str",
        "u8",
        "i8",
        "u16",
        "i16",
        "u32",
        "i32",
        "u64",
        "i64",
        "u128",
        "i128",
        "usize",
        "isize",
        "f32",
        "f64",
    }
)


def _rust_resolves_in_module(name: str) -> bool:
    """``name`` is a type written bare, which the qualified name reads as one of the
    modules it is written in: a name, with any generic arguments (``G``,
    ``Vec<T>``), not a path, a primitive or a type that is no path."""
    if not name or not (name[0].isalpha() or name[0] == "_") or "::" in name:
        return False
    return _rust_is_path(name) and name.split("<", 1)[0] not in _RUST_PRIMITIVES


def _rust_render(semantic: Sequence[SemanticElement]) -> str:
    """Rust's qualified name: the components joined with ``::``, an impl written as
    ``<Widget as Shape>`` for a trait impl and ``<dyn Shape>`` for a self type that is
    no path, and the modules before an impl folded into its self type when it is
    written bare (``m::G``) -- dropped otherwise, as the qualified name has no place
    for them (``x::P``, a path from the crate root without its ``crate::``)."""
    impl_at = next(
        (index for index, element in enumerate(semantic) if element["kind"] == "impl"),
        None,
    )
    if impl_at is None:
        return "::".join(element["name"] for element in semantic)
    modules = [element["name"] for element in semantic[:impl_at]]
    impl = semantic[impl_at]
    self_type = impl["name"]
    if modules and _rust_resolves_in_module(self_type):
        self_type = "::".join([*modules, self_type])
    else:
        self_type = self_type.removeprefix("crate::")
    if "trait" in impl:
        segment = f"<{self_type} as {impl['trait']}>"
    elif _rust_is_path(self_type):
        segment = self_type
    else:
        segment = f"<{self_type}>"
    return "::".join(
        [segment, *(element["name"] for element in semantic[impl_at + 1 :])]
    )


def _python_locals_after(semantic: Sequence[SemanticElement], index: int) -> bool:
    """CPython writes ``<locals>`` after the component at ``index``: a function or a
    method that another component follows."""
    return (
        semantic[index]["kind"] in ("function", "method") and index < len(semantic) - 1
    )


def render_semantic(
    semantic: Sequence[SemanticElement] | None, language: str
) -> str | None:
    """Spell ``semantic`` as its language writes a qualified name: the entity's
    ``qualified_name``.

    C and C++ join the components with ``::``. Rust does too, writes an ``impl`` as
    ``<Widget as Shape>`` for a trait impl and ``<dyn Shape>`` for a self type that is
    no path, and folds the modules before an impl into a self type written bare
    (``m::G``). Python joins them with ``.``, with ``<locals>`` after a function or a
    method another component follows (CPython's ``__qualname__``). C#, Go,
    TypeScript, JavaScript and Bash join them with ``.``.

    :param semantic: An entity's components, as :func:`describe_entity` gives them.
    :param language: The language of the entity's file, as ``scope.language``
        records it (:func:`scope_language`).
    :return: The qualified name; ``None`` for no components.
    """
    if semantic is None:
        return None
    if language in ("c", "cpp"):
        return "::".join(element["name"] for element in semantic)
    if language == "rust":
        return _rust_render(semantic)
    if language == "python":
        parts: list[str] = []
        for index, element in enumerate(semantic):
            parts.append(element["name"])
            if _python_locals_after(semantic, index):
                parts.append("<locals>")
        return ".".join(parts)
    return ".".join(element["name"] for element in semantic)


def name_chain(
    semantic: Sequence[SemanticElement] | None, language: str
) -> tuple[tuple[tuple[str, str], ...], ...] | None:
    """What identifies an entity in its file: the identity-bearing part of its
    rendering -- its components' names and other keys (a Rust impl's ``trait``), and
    in Python the ``<locals>`` boundaries -- without their kinds.

    Kinds describe, names identify. A kind is a best-effort classification, for
    filtering and rendering, and one entity's kinds depend on how it is written: a
    method defined in its class is ``namespace ns``, ``class W``, ``method f``, the
    same method defined out of line ``scope ns``, ``class W``, ``method f``. So two
    entities are the same, or one is inside the other, by their name chains, never
    by their kinds. Where a kind does show in the name, so does the chain: CPython's
    ``<locals>`` after a function or a method (``A.f.<locals>.g`` is not ``A.f.g``) is
    a link of its own, ``(("name", "<locals>"),)``, which no Python name can be.

    A ``qualified_name`` key is left out too: a component rebuilt from a code hop's
    semantic entry carries one on the entity, the rendering of this very chain, which
    adds no identity and would break containment (a class's chain is a prefix of its
    method's only without it).

    :param semantic: An entity's components (``scope.semantic``).
    :param language: The entity's file's language (``scope.language``).
    :return: One tuple of ``(key, value)`` pairs per component, its keys sorted,
        ``kind`` and ``qualified_name`` left out, and a ``<locals>`` link where Python
        writes one; ``None`` for no components.
    """
    if semantic is None:
        return None
    chain: list[tuple[tuple[str, str], ...]] = []
    for index, element in enumerate(semantic):
        chain.append(
            tuple(
                sorted(
                    (key, str(value))
                    for key, value in element.items()
                    if key not in ("kind", "qualified_name")
                )
            )
        )
        if language == "python" and _python_locals_after(semantic, index):
            chain.append((("name", "<locals>"),))
    return tuple(chain)


# The suffixes of the ``ts`` comment type that are JavaScript, in lower case.
_JAVASCRIPT_SUFFIXES = frozenset({".js", ".jsx", ".mjs", ".cjs"})


def scope_language(comment_type: CommentType, path: PurePath) -> str:
    """A source file's language, by its name (``scope.language``), spelled as editors'
    language identifiers spell it.

    The comment type gives the language family and the grammar; the suffix then picks
    ``c`` among C and C++ and ``javascript`` among the ``ts`` type's files, and the
    comment type alone names a file of any other suffix (a ``.py`` file in a C++
    project is ``cpp``). So: ``c`` for a ``.c`` file and ``cpp`` for every other C and
    C++ file (a ``.h`` header included: its name does not say whether it is C or C++,
    and it is analysed as C++; and a ``.C`` file, which compilers read as C++);
    ``csharp``; ``javascript`` for a ``.js``, ``.jsx``, ``.mjs`` or ``.cjs`` file, in
    any case, and ``typescript`` for every other file of the ``ts`` comment type,
    ``.tsx`` included; otherwise the comment type (``python``, ``rust``, ``go``,
    ``yaml``, ``jsonc``, ``bash``). A ``.c`` file is parsed with the C++ grammar too,
    and its components render as C++'s.

    :param comment_type: The project's comment type.
    :param path: The file's path; only its suffix is read, case included for C (discovery
        reads it in any case, so a ``.C`` file is traced, as C++).
    """
    if comment_type == CommentType.cpp:
        return "c" if path.suffix == ".c" else "cpp"
    if comment_type == CommentType.cs:
        return "csharp"
    if comment_type == CommentType.ts:
        if path.suffix.lower() in _JAVASCRIPT_SUFFIXES:
            return "javascript"
        return "typescript"
    return comment_type.value


def code_scope(
    association: Association,
    comment_type: CommentType,
    language: str,
    names: CppNames | None = None,
) -> CodeScope:
    """The ``scope`` object of an analysis record, for ``association`` in a file of
    ``language`` (:func:`scope_language`).

    ``names`` is what the whole C++ file decides about its names (:class:`CppNames`),
    for a C++ file the analysis parsed; the entity is named as the file names it.
    """
    node = association.node
    if names is None:
        name = describe_entity(node, comment_type)
    else:
        name = describe_entity(node, comment_type, source=names.source)
        if name is not None:
            name = names.qualify(name, node.start_point.row + 1)
    return {
        "kind": node.type,
        "start": node.start_point.row + 1,
        "end": node.end_point.row + 1,
        "language": language,
        "entity_kind": name.kind if name is not None else None,
        "qualified_name": name.qualified_name if name is not None else None,
        "semantic": (
            list(name.semantic)
            if name is not None and name.semantic is not None
            else None
        ),
        "mechanism": association.mechanism,
    }
