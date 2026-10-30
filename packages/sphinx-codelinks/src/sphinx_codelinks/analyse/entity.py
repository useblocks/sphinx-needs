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
from dataclasses import dataclass
from pathlib import PurePath
from typing import Literal, NotRequired, TypedDict

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
# Naming: a definition node -> (kind, in-file qualified name, its components)
# ---------------------------------------------------------------------------
#
# Every namer builds the qualified name and its components (``semantic``) side by
# side, from the same walk; ``render_semantic`` spells the components back, and the
# shared fixtures' truth test holds the two together.


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
    kind: EntityKind, qualified_name: str | None, semantic: Iterable[SemanticElement]
) -> EntityName:
    """An entity's name and its components; no components when it has no name."""
    if qualified_name is None:
        return EntityName(kind, None, None)
    return EntityName(kind, qualified_name, tuple(semantic))


# --- C and C++ ---------------------------------------------------------------

_CPP_CLASS_KINDS: dict[str, EntityKind] = {
    "class_specifier": "class",
    "struct_specifier": "struct",
    "union_specifier": "union",
    "enum_specifier": "enum",
}

# The kinds the namer gives a function only when a class qualifies it.
_CPP_MEMBER_KINDS = frozenset({"method", "constructor", "destructor"})


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


def _cpp_containers(node: TreeSitterNode) -> tuple[list[str], list[SemanticElement]]:
    """The namespaces and classes around ``node``, outermost first: their names, and
    their components (``namespace a::b`` is two namespaces)."""
    segments: list[str] = []
    groups: list[list[SemanticElement]] = []
    parent = node.parent
    while parent is not None:
        if parent.type == "namespace_definition":
            namespace = _cpp_namespace_name(parent)
            segments.append(namespace)
            groups.append([_element("namespace", p) for p in _cpp_split(namespace)])
        elif parent.type in ("class_specifier", "struct_specifier", "union_specifier"):
            name = parent.child_by_field_name("name")
            if name is not None:
                container = _cpp_name(_text(name), _cpp_templated(parent))
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
    prefix, outer = _cpp_containers(node)
    if node.type in ("function_definition", "declaration", "field_declaration"):
        cast = _cpp_operator_cast(node)
        if cast is not None:
            conversion = _cpp_conversion_name(node, cast)
            # a conversion operator is always a member: its qualifier is its class
            return _named(
                "operator",
                "::".join([*prefix, conversion]),
                [*outer, *_cpp_qualified(conversion, "operator", member=True)],
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
        return _named(
            kind,
            "::".join([*prefix, own]),
            [*outer, *_cpp_qualified(own, kind, member=kind in _CPP_MEMBER_KINDS)],
        )
    if node.type in _CPP_CLASS_KINDS:
        class_kind = _CPP_CLASS_KINDS[node.type]
        name = node.child_by_field_name("name")
        if name is None:
            return EntityName(class_kind, None, None)
        own_name = _cpp_name(_text(name), _cpp_templated(node))
        return _named(
            class_kind,
            "::".join([*prefix, own_name]),
            [*outer, *_cpp_qualified(own_name, class_kind, member=False)],
        )
    if node.type == "namespace_definition":
        namespace = _cpp_namespace_name(node)
        return _named(
            "namespace",
            "::".join([*prefix, namespace]),
            [*outer, *(_element("namespace", p) for p in _cpp_split(namespace))],
        )
    return None


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
    node: TreeSitterNode, comment_type: CommentType
) -> EntityName | None:
    """Name the definition ``node``: its kind, its in-file qualified name, and the
    components of that name.

    Pure: it reads the node and its ancestors (and, for a C# file-scoped namespace, the
    file's top-level siblings), never the file system.

    :param node: A definition node, as association binds it.
    :param comment_type: The language of the file ``node`` was parsed from.
    :return: The name, or ``None`` if ``node`` is no entity this function can name.
    """
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

    :param semantic: An entity's components (``scope.semantic``).
    :param language: The entity's file's language (``scope.language``).
    :return: One tuple of ``(key, value)`` pairs per component, its keys sorted,
        ``kind`` left out, and a ``<locals>`` link where Python writes one; ``None``
        for no components.
    """
    if semantic is None:
        return None
    chain: list[tuple[tuple[str, str], ...]] = []
    for index, element in enumerate(semantic):
        chain.append(
            tuple(
                sorted(
                    (key, str(value)) for key, value in element.items() if key != "kind"
                )
            )
        )
        if language == "python" and _python_locals_after(semantic, index):
            chain.append((("name", "<locals>"),))
    return tuple(chain)


def scope_language(comment_type: CommentType, path: PurePath) -> str:
    """The language a source file was analysed as, by its name (``scope.language``).

    ``c`` for a ``.c`` file, ``cpp`` for every other C and C++ file (a ``.h`` header
    included: its language is not in its name; and a ``.C`` file, which compilers read
    as C++), otherwise the comment type (``python``, ``rust``, ``cs``, ``ts``, ``go``,
    ``yaml``, ``jsonc``, ``bash``). A ``.c`` file is parsed with the C++ grammar and
    its components render as C++'s.

    :param comment_type: The comment type the file was analysed as.
    :param path: The file's path; only its suffix is read, case included (discovery
        reads it in any case, so a ``.C`` file is traced, as C++).
    """
    if comment_type == CommentType.cpp:
        return "c" if path.suffix == ".c" else "cpp"
    return comment_type.value


def code_scope(
    association: Association, comment_type: CommentType, language: str
) -> CodeScope:
    """The ``scope`` object of an analysis record, for ``association`` in a file of
    ``language`` (:func:`scope_language`)."""
    node = association.node
    name = describe_entity(node, comment_type)
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
