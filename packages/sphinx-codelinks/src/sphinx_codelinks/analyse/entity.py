"""The code a marker is attached to: what counts as an entity, and how one is named.

A marker is attached to a definition node of the syntax tree (a function, a class,
a namespace, ...): its *entity*. This module holds the per-language tables that say
which node kinds are entities, and the one naming function, :func:`describe_entity`,
that turns such a node into its kind and its qualified name *within its file* (no
module or package prefix: that is derived from the file's path, which this module
never reads -- every function here is pure).

The traversal that picks the node for a comment is ``find_associated_scope`` /
``associate`` in :mod:`sphinx_codelinks.analyse.utils`; this module only answers
questions about a node.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypedDict

from tree_sitter import Node as TreeSitterNode

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
"""The kind of an entity, as the analysis output and the need fields spell it."""

Mechanism = Literal["doc_comment", "leading", "trailing", "enclosing"]
"""How a marker came to be attached to its entity.

``doc_comment`` is *declared*: a documentation comment (``///``, ``//!``, ``/**``,
``/*!``, a C# ``///``, a JSDoc ``/**``, a Python docstring) attached by its own rule.
The other three are *inferred* from where a plain comment sits: on the lines before the
entity (``leading``), after code on the entity's own line (``trailing``), or inside its
body (``enclosing``).
"""


@dataclass(frozen=True)
class EntityName:
    """A definition node, named."""

    kind: EntityKind
    """What the node defines."""
    qualified_name: str | None
    """The name within its file, qualified by the containers the file shows
    (``ns::Widget::draw``, ``Shape.area``, ``<Widget as Shape>::area``); ``None`` when
    the entity has no name (an anonymous class, a data-file entry)."""


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
    entity_kind: str | None
    """The entity's kind (:data:`EntityKind`), ``None`` if it could not be named."""
    qualified_name: str | None
    """The entity's in-file qualified name, ``None`` if it has none."""
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


def _cpp_prototype(node: TreeSitterNode) -> bool:
    """A function prototype outside a function body: inside one, ``SDLoc dl(Op);`` is a
    local variable that merely parses like a prototype."""
    if not _cpp_declares_function(node):
        return False
    parent = node.parent
    while parent is not None:
        if parent.type == "compound_statement":
            return False
        parent = parent.parent
    return True


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


def is_doc_comment(node: TreeSitterNode, comment_type: CommentType) -> bool:
    """Whether the comment ``node`` is a documentation comment of its language.

    A Python docstring is one too, but it is a string, not a comment: the caller knows
    it by its capture.
    """
    text = (node.text or b"").decode("utf-8", "replace")
    for opening in _DOC_LINE_OPENINGS.get(comment_type, ()):
        if text.startswith(opening):
            return not (opening == "///" and text.startswith("////"))
    for opening in _DOC_BLOCK_OPENINGS.get(comment_type, ()):
        if text.startswith(opening):
            return opening == "/*!" or not text[len(opening) :].startswith(("*", "/"))
    return False


# ---------------------------------------------------------------------------
# Naming: a definition node -> (kind, in-file qualified name)
# ---------------------------------------------------------------------------


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


# --- C and C++ ---------------------------------------------------------------

_CPP_CLASS_KINDS: dict[str, EntityKind] = {
    "class_specifier": "class",
    "struct_specifier": "struct",
    "union_specifier": "union",
    "enum_specifier": "enum",
}


def _cpp_templated(node: TreeSitterNode) -> bool:
    """Under a ``template`` with parameters (not an explicit specialisation)."""
    parent = node.parent
    while parent is not None and parent.type == "template_declaration":
        params = parent.child_by_field_name("parameters")
        if params is not None and params.named_child_count > 0:
            return True
        parent = parent.parent
    return False


def _cpp_name(text: str, templated: bool) -> str:
    name = _squeeze(text).lstrip(":")
    return _strip_template_args(name) if templated else name


def _cpp_namespace_name(node: TreeSitterNode) -> str:
    name = node.child_by_field_name("name")
    return _squeeze(_text(name)) if name is not None else "(anonymous namespace)"


def _cpp_containers(node: TreeSitterNode) -> list[str]:
    segments: list[str] = []
    parent = node.parent
    while parent is not None:
        if parent.type == "namespace_definition":
            segments.append(_cpp_namespace_name(parent))
        elif parent.type in ("class_specifier", "struct_specifier", "union_specifier"):
            name = parent.child_by_field_name("name")
            if name is not None:
                segments.append(_cpp_name(_text(name), _cpp_templated(parent)))
        parent = parent.parent
    return list(reversed(segments))


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


def _cpp_conversion_target_end(cast: TreeSitterNode) -> int:
    """Where a conversion operator's target type ends: at its own parameter list
    (``operator const char*() const``), past any pointer or reference. The search
    starts at the cast's declarator, so a parameter list inside the target type
    (``operator std::function<void(int)>()``) is not it."""
    declarator = cast.child_by_field_name("declarator")
    stack = [declarator] if declarator is not None else []
    while stack:
        node = stack.pop()
        if node.type == "parameter_list":
            return node.start_byte
        stack.extend(reversed(node.children))
    return cast.end_byte


def _cpp_conversion_name(node: TreeSitterNode, cast: TreeSitterNode) -> str:
    """``ns::W::operator const char*``: the qualifier written before the
    ``operator_cast``, then ``operator`` and its target type as written, up to the
    parameter list."""
    declarator = node.child_by_field_name("declarator")
    head = ""
    if declarator is not None and declarator.text:
        written = declarator.text[: cast.start_byte - declarator.start_byte]
        head = written.decode("utf-8", errors="replace")
    keyword = cast.children[0] if cast.children else cast
    target = (cast.text or b"")[
        keyword.end_byte - cast.start_byte : _cpp_conversion_target_end(cast)
        - cast.start_byte
    ].decode("utf-8", errors="replace")
    return _cpp_name(head, _cpp_templated(node)) + "operator " + _squeeze(target)


def _cpp_describe(node: TreeSitterNode) -> EntityName | None:
    prefix = _cpp_containers(node)
    if node.type in ("function_definition", "declaration", "field_declaration"):
        cast = _cpp_operator_cast(node)
        if cast is not None:
            return EntityName(
                "operator", "::".join([*prefix, _cpp_conversion_name(node, cast)])
            )
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
        own = _cpp_name(_text(inner), _cpp_templated(node))
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
        return EntityName(kind, "::".join([*prefix, own]))
    if node.type in _CPP_CLASS_KINDS:
        name = node.child_by_field_name("name")
        own_name = (
            _cpp_name(_text(name), _cpp_templated(node)) if name is not None else None
        )
        return EntityName(_CPP_CLASS_KINDS[node.type], _join("::", prefix, own_name))
    if node.type == "namespace_definition":
        return EntityName("namespace", "::".join([*prefix, _cpp_namespace_name(node)]))
    return None


# --- Python ------------------------------------------------------------------


def _python_describe(node: TreeSitterNode) -> EntityName | None:
    """CPython's ``__qualname__``: ``Class.method``, ``outer.<locals>.inner``."""
    if node.type not in ("function_definition", "class_definition"):
        return None
    name = node.child_by_field_name("name")
    if name is None:
        return None
    segments: list[str] = []
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
        parent = parent.parent
    qualified = ".".join([*reversed(segments), _text(name)])
    if node.type == "class_definition":
        return EntityName("class", qualified)
    return EntityName(
        "method" if nearest == "class_definition" else "function", qualified
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


def _rust_describe(node: TreeSitterNode) -> EntityName | None:
    if node.type == "impl_item":
        return EntityName("impl", _rust_impl_segment(node))
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
        if parent.type == "impl_item":
            return EntityName(
                "method" if method else kind,
                "::".join([_rust_impl_segment(parent), *reversed(functions), own]),
            )
        if parent.type == "trait_item":
            trait = [*_rust_modules(parent), _text(parent.child_by_field_name("name"))]
            return EntityName(
                "method" if method else kind,
                "::".join([*trait, *reversed(functions), own]),
            )
        if parent.type == "function_item":
            functions.append(_text(parent.child_by_field_name("name")))
        if parent.type == "mod_item":
            break
        parent = parent.parent
    return EntityName(
        kind, "::".join([*_rust_modules(node), *reversed(functions), own])
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


def _csharp_describe(node: TreeSitterNode) -> EntityName | None:
    kind = _CSHARP_KINDS.get(node.type)
    if kind is None:
        return None
    segments: list[str] = []
    parent = node.parent
    root = node
    while parent is not None:
        if parent.type in _CSHARP_CONTAINERS:
            container = _csharp_own_name(parent)
            if container is not None:
                segments.append(container)
        root = parent
        parent = parent.parent
    segments.reverse()
    # a file-scoped namespace (``namespace A.B;``) is a sibling of what it holds
    if node.type != "file_scoped_namespace_declaration":
        for child in root.named_children:
            if child.start_byte >= node.start_byte:
                break
            if child.type == "file_scoped_namespace_declaration":
                segments.insert(0, _csharp_own_name(child) or "")
    return EntityName(kind, _join(".", segments, _csharp_own_name(node)))


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
        return EntityName("function", _text(node.child_by_field_name("name")) or None)
    if node.type == "method_declaration":
        own = _text(node.child_by_field_name("name"))
        receiver = _go_receiver(node)
        return EntityName("method", f"{receiver}.{own}" if receiver else own)
    if node.type == "type_declaration":
        specs = [
            child
            for child in node.named_children
            if child.type in ("type_spec", "type_alias")
        ]
        if len(specs) != 1:
            return EntityName("type", None)
        node = specs[0]
    if node.type in ("type_spec", "type_alias"):
        return EntityName(
            _go_spec_kind(node), _text(node.child_by_field_name("name")) or None
        )
    if node.type == "method_elem":
        own = _text(node.child_by_field_name("name"))
        parent = node.parent
        while parent is not None and parent.type != "type_spec":
            parent = parent.parent
        owner = _text(parent.child_by_field_name("name")) if parent is not None else ""
        return EntityName("method", f"{owner}.{own}" if owner else own)
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


def _ts_containers(node: TreeSitterNode) -> list[str]:
    segments: list[str] = []
    parent = node.parent
    while parent is not None:
        if parent.type in _TS_NAMED_CONTAINERS:
            name = parent.child_by_field_name("name")
            if name is not None:
                segments.append(_collapse(_text(name)))
        elif parent.type == "variable_declarator" and _ts_value_kind(
            parent.child_by_field_name("value")
        ):
            segments.append(_text(parent.child_by_field_name("name")))
        parent = parent.parent
    return list(reversed(segments))


def _ts_describe(node: TreeSitterNode) -> EntityName | None:
    prefix = _ts_containers(node)
    if node.type in ("lexical_declaration", "variable_declaration"):
        declarator, kind = _ts_declarator(node)
        if declarator is None or kind is None:
            return None
        return EntityName(
            kind, _join(".", prefix, _text(declarator.child_by_field_name("name")))
        )
    if node.type == "assignment_expression":
        kind = _ts_value_kind(node.child_by_field_name("right"))
        if kind is None:
            return None
        return EntityName(
            kind, _join(".", prefix, _collapse(_text(node.child_by_field_name("left"))))
        )
    if node.type == "export_statement":
        kind = _ts_value_kind(node.child_by_field_name("value"))
        if kind is None:
            return None
        return EntityName(kind, _join(".", prefix, "default"))
    kind = _TS_KINDS.get(node.type)
    if kind is None:
        return None
    name = node.child_by_field_name("name")
    return EntityName(
        kind, _join(".", prefix, _collapse(_text(name)) if name is not None else None)
    )


# --- Bash, YAML and JSON -----------------------------------------------------


def _bash_describe(node: TreeSitterNode) -> EntityName | None:
    if node.type != "function_definition":
        return None
    return EntityName("function", _text(node.child_by_field_name("name")) or None)


def _data_describe(node: TreeSitterNode) -> EntityName:
    """A YAML or JSON entry: a key/value pair is a ``key``, anything else an ``item``."""
    is_pair = node.type in ("block_mapping_pair", "flow_pair", "pair")
    return EntityName("key" if is_pair else "item", None)


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
    node: TreeSitterNode, comment_type: CommentType
) -> EntityName | None:
    """Name the definition ``node``: its kind and its in-file qualified name.

    Pure: it reads the node and its ancestors (and, for a C# file-scoped namespace, the
    file's top-level siblings), never the file system.

    :param node: A definition node, as association binds it.
    :param comment_type: The language of the file ``node`` was parsed from.
    :return: The name, or ``None`` if ``node`` is no entity this function can name.
    """
    describer = _DESCRIBERS.get(comment_type)
    return describer(node) if describer is not None else None


def code_scope(association: Association, comment_type: CommentType) -> CodeScope:
    """The ``scope`` object of an analysis record, for ``association``."""
    node = association.node
    name = describe_entity(node, comment_type)
    return {
        "kind": node.type,
        "start": node.start_point.row + 1,
        "end": node.end_point.row + 1,
        "entity_kind": name.kind if name is not None else None,
        "qualified_name": name.qualified_name if name is not None else None,
        "mechanism": association.mechanism,
    }
