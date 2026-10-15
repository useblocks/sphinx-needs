"""A need type's declaration of a field is a narrowing of the field: ``narrowing_problems``.

A need of the type is usable wherever a need of any type is: the declaration keeps the
field's kind, type and derivation, its schema admits no value the field's does not,
it does not open what the field closes, and a link type is drawn the same on every
need type. ``narrowing_problems`` lists every way a declaration is not one;
``add_type_overlay`` and ``replace_field`` refuse what it lists, and ``inherit_schema``
reads its schema rules.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest

from sphinx_needs.derive import DeriveRule
from sphinx_needs.need_item import NeedLink
from sphinx_needs.needs_schema import (
    FieldLiteralValue,
    FieldSchema,
    FieldsSchema,
    LinkDisplayConfig,
    LinkSchema,
    LinksLiteralValue,
    inherit_schema,
    narrowing_problems,
    schema_narrowing_problems,
)


def _link(name: str = "blocks", **kwargs: Any) -> LinkSchema:
    return LinkSchema(
        name=name,
        schema=kwargs.pop("schema", {"type": "array", "items": {"type": "string"}}),
        display=kwargs.pop(
            "display", LinkDisplayConfig(incoming=f"{name} in", outgoing=f"{name} out")
        ),
        **kwargs,
    )


#: a field that opens everything a declaration may close
OPEN = FieldSchema(
    name="asil",
    schema={"type": "string", "enum": ["A", "B", "QM"], "minLength": 1},
    nullable=True,
    directive_option=True,
    allow_extend=True,
    allow_defaults=True,
    parse_variants=True,
    parse_dynamic_functions=True,
    default=FieldLiteralValue("QM"),
)

#: a field that closes everything a declaration may open
CLOSED = FieldSchema(name="asil", schema={"type": "string"})


@pytest.mark.parametrize(
    "base,overlay",
    [
        pytest.param(OPEN, OPEN, id="the-same-declaration"),
        pytest.param(OPEN, replace(OPEN, description="spec"), id="a-description"),
        pytest.param(
            OPEN,
            replace(
                OPEN,
                schema={"type": "string", "enum": ["A", "QM"], "minLength": 1},
                nullable=False,
                directive_option=False,
                allow_extend=False,
                allow_defaults=True,
            ),
            id="everything-closed",
        ),
        pytest.param(
            OPEN,
            replace(
                OPEN,
                schema={
                    "type": "string",
                    "enum": ["A", "B", "QM"],
                    "minLength": 2,
                    "maxLength": 3,
                },
            ),
            id="a-longer-minimum-and-a-new-maximum",
        ),
        pytest.param(CLOSED, CLOSED, id="nothing-open"),
        pytest.param(_link(), _link(description="spec"), id="a-link-type"),
        pytest.param(
            _link(allow_extend=True, directive_option=True),
            _link(schema={"type": "array", "items": {"type": "string"}, "maxItems": 2}),
            id="a-link-type-closed",
        ),
    ],
)
def test_a_narrowing(
    base: FieldSchema | LinkSchema, overlay: FieldSchema | LinkSchema
) -> None:
    assert narrowing_problems(base, overlay) == []


@pytest.mark.parametrize(
    "base,overlay,problems",
    [
        # rule 1: the same kind
        pytest.param(
            CLOSED, _link("asil"), ["it is a field."], id="1-a-link-type-for-a-field"
        ),
        pytest.param(
            _link("asil"), CLOSED, ["it is a link type."], id="1-a-field-for-a-link"
        ),
        # rule 2: the same type and item type
        pytest.param(
            CLOSED,
            FieldSchema(name="asil", schema={"type": "integer"}),
            [
                "with type 'integer' (items None): its type is 'string' (items None) "
                "on every need type."
            ],
            id="2-another-type",
        ),
        pytest.param(
            FieldSchema(
                name="asil", schema={"type": "array", "items": {"type": "string"}}
            ),
            FieldSchema(
                name="asil", schema={"type": "array", "items": {"type": "integer"}}
            ),
            [
                "with type 'array' (items 'integer'): its type is 'array' (items "
                "'string') on every need type."
            ],
            id="2-another-item-type",
        ),
        # rule 3: the same derivation
        pytest.param(
            CLOSED,
            replace(CLOSED, derive=DeriveRule(kind="copy", field="title")),
            [
                "with another derivation: a field is derived per need type by its "
                "derive_by_type."
            ],
            id="3-a-derive",
        ),
        pytest.param(
            replace(
                CLOSED, derive_by_type={"req": DeriveRule(kind="copy", field="title")}
            ),
            replace(
                CLOSED, derive_by_type={"spec": DeriveRule(kind="copy", field="title")}
            ),
            [
                "with another derivation: a field is derived per need type by its "
                "derive_by_type."
            ],
            id="3-another-derive-by-type",
        ),
        # rule 4: the schema keywords
        pytest.param(
            OPEN,
            replace(
                OPEN,
                schema={"type": "string", "enum": ["A", "X"], "minLength": 1},
                default=None,
            ),
            [
                "Child 'enum' values ['A', 'X'] are not a subset of parent 'enum' "
                "values ['A', 'B', 'QM']."
            ],
            id="4-a-wider-enum",
        ),
        pytest.param(
            FieldSchema(name="effort", schema={"type": "integer", "minimum": 1}),
            FieldSchema(name="effort", schema={"type": "integer", "minimum": 0}),
            ["Child 'minimum' 0 is less than parent 'minimum' 1."],
            id="4-a-lower-minimum",
        ),
        pytest.param(
            FieldSchema(
                name="tags",
                schema={"type": "array", "items": {"type": "string", "maxLength": 5}},
            ),
            FieldSchema(
                name="tags",
                schema={"type": "array", "items": {"type": "string", "maxLength": 9}},
            ),
            [
                "'items' inheritance: Child 'maxLength' 9 is greater than parent "
                "'maxLength' 5."
            ],
            id="4-a-longer-item",
        ),
        # rule 5: a constraint dropped
        pytest.param(
            FieldSchema(name="asil", schema={"type": "string", "minLength": 1}),
            CLOSED,
            ["Child schema drops parent constraint 'minLength'."],
            id="5-a-dropped-minimum",
        ),
        pytest.param(
            FieldSchema(
                name="tags",
                schema={"type": "array", "items": {"type": "string", "minLength": 1}},
            ),
            FieldSchema(
                name="tags", schema={"type": "array", "items": {"type": "string"}}
            ),
            ["'items' inheritance: Child schema drops parent constraint 'minLength'."],
            id="5-a-dropped-item-minimum",
        ),
        # rule 6: nullable
        pytest.param(
            CLOSED,
            replace(CLOSED, nullable=True),
            ["Cannot change 'nullable' from False to True in child."],
            id="6-nullable",
        ),
        # rule 7: what a need, a needextend or a default may set
        pytest.param(
            CLOSED,
            replace(CLOSED, allow_extend=True),
            ["Cannot change 'allow_extend' from False to True in child."],
            id="7-allow-extend",
        ),
        pytest.param(
            CLOSED,
            replace(CLOSED, allow_defaults=True),
            ["Cannot change 'allow_defaults' from False to True in child."],
            id="7-allow-defaults",
        ),
        pytest.param(
            CLOSED,
            replace(CLOSED, directive_option=True),
            ["Cannot change 'directive_option' from False to True in child."],
            id="7-directive-option",
        ),
        # rule 8: what is parsed, the same on every need type (a needextend converts
        # its value once, for the needs of every type)
        pytest.param(
            CLOSED,
            replace(CLOSED, parse_variants=True),
            ["Field 'asil' declares 'parse_variants' for every need type."],
            id="8-parse-variants",
        ),
        pytest.param(
            CLOSED,
            replace(CLOSED, parse_dynamic_functions=True),
            ["Field 'asil' declares 'parse_dynamic_functions' for every need type."],
            id="8-parse-dynamic-functions",
        ),
        pytest.param(
            OPEN,
            replace(OPEN, parse_dynamic_functions=False),
            ["Field 'asil' declares 'parse_dynamic_functions' for every need type."],
            id="8-parse-dynamic-functions-closed",
        ),
        # rule 9: a literal default the narrowed schema admits
        pytest.param(
            OPEN,
            replace(
                OPEN, schema={"type": "string", "enum": ["A", "B"], "minLength": 1}
            ),
            [
                "Default 'QM' is not valid against the narrowed schema: \"QM\" is not "
                'one of "A" or "B".'
            ],
            id="9-the-default-outside-the-narrowed-enum",
        ),
        pytest.param(
            OPEN,
            replace(
                OPEN,
                schema={"type": "string", "enum": ["A", "QM"], "minLength": 1},
                predicate_defaults=(
                    ('status == "open"', FieldLiteralValue("B")),
                    ('status == "done"', FieldLiteralValue("A")),
                ),
            ),
            [
                "Default 'B' of the predicate 'status == \"open\"' is not valid against "
                'the narrowed schema: "B" is not one of "A" or "QM".'
            ],
            id="9-a-predicate-default",
        ),
        pytest.param(
            _link(allow_defaults=True),
            _link(
                allow_defaults=True,
                schema={"type": "array", "items": {"type": "string"}, "maxItems": 1},
                default=LinksLiteralValue([NeedLink(id="A"), NeedLink(id="B")]),
            ),
            [
                "Default ['A', 'B'] is not valid against the narrowed schema: "
                '["A","B"] has more than 1 item.'
            ],
            id="9-a-link-default",
        ),
        pytest.param(
            _link(allow_defaults=True),
            _link(
                allow_defaults=True,
                schema={
                    "type": "array",
                    "items": {"type": "string", "pattern": "^[A-Z]+_[0-9]+$"},
                },
                default=LinksLiteralValue([NeedLink(id="REQ_1", part="p")]),
            ),
            [
                "Default ['REQ_1.p'] is not valid against the narrowed schema: "
                '"REQ_1.p" does not match "^[A-Z]+_[0-9]+$".'
            ],
            id="9-a-link-default-as-validated",
        ),
        # rule 10: a link type is drawn and resolved the same on every need type
        pytest.param(
            _link(),
            _link(display=LinkDisplayConfig(incoming="in", outgoing="out")),
            ["Link type 'blocks' declares 'display' for every need type."],
            id="10-display",
        ),
        pytest.param(
            _link(),
            _link(copy=True),
            ["Link type 'blocks' declares 'copy' for every need type."],
            id="10-copy",
        ),
        pytest.param(
            _link(),
            _link(allow_dead_links=True),
            ["Link type 'blocks' declares 'allow_dead_links' for every need type."],
            id="10-allow-dead-links",
        ),
        pytest.param(
            _link(),
            _link(parse_conditions=False),
            ["Link type 'blocks' declares 'parse_conditions' for every need type."],
            id="10-parse-conditions",
        ),
    ],
)
def test_one_problem(
    base: FieldSchema | LinkSchema,
    overlay: FieldSchema | LinkSchema,
    problems: list[str],
) -> None:
    assert narrowing_problems(base, overlay) == problems


def test_every_problem_is_listed() -> None:
    """Each rule a declaration breaks is listed, in the order of the rules."""
    overlay = replace(
        OPEN,
        schema={"type": "string", "enum": ["A", "X"]},
        nullable=True,
        default=FieldLiteralValue("A"),
    )
    base = replace(OPEN, nullable=False, allow_extend=False)
    assert narrowing_problems(base, replace(overlay, allow_extend=True)) == [
        "Child 'enum' values ['A', 'X'] are not a subset of parent 'enum' values "
        "['A', 'B', 'QM'].",
        "Child schema drops parent constraint 'minLength'.",
        "Cannot change 'nullable' from False to True in child.",
        "Cannot change 'allow_extend' from False to True in child.",
    ]


def test_every_keyword_is_listed() -> None:
    """Every schema keyword a declaration widens is listed, not the first one."""
    base = FieldSchema(
        name="asil",
        schema={"type": "string", "enum": ["A", "B"], "minLength": 2, "maxLength": 4},
    )
    overlay = FieldSchema(
        name="asil",
        schema={"type": "string", "enum": ["A", "C"], "minLength": 1, "maxLength": 4},
    )
    assert narrowing_problems(base, overlay) == [
        "Child 'enum' values ['A', 'C'] are not a subset of parent 'enum' values "
        "['A', 'B'].",
        "Child 'minLength' 1 is less than parent 'minLength' 2.",
    ]


def test_the_predicate_is_pure() -> None:
    base = FieldSchema(name="asil", schema={"type": "string", "minLength": 1})
    overlay = CLOSED
    before = (deepcopy(base.schema), deepcopy(overlay.schema))
    assert narrowing_problems(base, overlay) == [
        "Child schema drops parent constraint 'minLength'."
    ]
    assert (base.schema, overlay.schema) == before


# -- the schema rules, which inherit_schema reads too -------------------------------


def test_a_dropped_keyword_is_inherited_by_a_dict() -> None:
    """A declaration through a configuration dict names what it changes: the
    keywords it leaves out are the parent's. A full declaration that leaves one out
    has dropped it."""
    parent = {"type": "string", "minLength": 1}
    assert (
        schema_narrowing_problems(parent, {"type": "string"}, dropped_is_widening=False)
        == []
    )
    assert schema_narrowing_problems(
        parent, {"type": "string"}, dropped_is_widening=True
    ) == ["Child schema drops parent constraint 'minLength'."]
    child: dict[str, Any] = {"type": "string"}
    inherit_schema(parent, child)
    assert child == {"type": "string", "minLength": 1}


def test_an_equal_keyword_is_a_narrowing() -> None:
    parent = {"type": "string", "minLength": 3}
    for dropped_is_widening in (False, True):
        assert (
            schema_narrowing_problems(
                parent,
                {"type": "string", "minLength": 3},
                dropped_is_widening=dropped_is_widening,
            )
            == []
        )


def test_inherit_schema_reports_the_first_problem() -> None:
    """``inherit_schema`` refuses with the first of the problems, as it always has."""
    parent = {"type": "string", "enum": ["A", "B"], "minLength": 2}
    child = {"type": "string", "enum": ["A", "X"], "minLength": 1}
    assert schema_narrowing_problems(
        parent, deepcopy(child), dropped_is_widening=False
    ) == [
        "Child 'enum' values ['A', 'X'] are not a subset of parent 'enum' values "
        "['A', 'B'].",
        "Child 'minLength' 1 is less than parent 'minLength' 2.",
    ]
    with pytest.raises(ValueError) as exc_info:
        inherit_schema(parent, child)
    assert str(exc_info.value) == (
        "Child 'enum' values ['A', 'X'] are not a subset of parent 'enum' values "
        "['A', 'B']."
    )


# -- the doors: add_type_overlay and replace_field ----------------------------------


def _schema(*fields: FieldSchema | LinkSchema) -> FieldsSchema:
    schema = FieldsSchema()
    for field in fields:
        if isinstance(field, LinkSchema):
            schema.add_link_field(field)
        else:
            schema.add_extra_field(field)
    return schema


@pytest.mark.parametrize(
    "base,overlay,message",
    [
        pytest.param(
            CLOSED,
            replace(CLOSED, nullable=True),
            "Cannot declare field 'asil' for need type 'spec': Cannot change "
            "'nullable' from False to True in child.",
            id="nullable",
        ),
        pytest.param(
            OPEN,
            replace(OPEN, schema={"type": "string", "enum": ["A", "X"]}, default=None),
            "Cannot declare field 'asil' for need type 'spec': Child 'enum' values "
            "['A', 'X'] are not a subset of parent 'enum' values ['A', 'B', 'QM'].; "
            "Child schema drops parent constraint 'minLength'.",
            id="two-problems",
        ),
        pytest.param(
            OPEN,
            replace(
                OPEN, schema={"type": "string", "enum": ["A", "B"], "minLength": 1}
            ),
            "Cannot declare field 'asil' for need type 'spec': Default 'QM' is not "
            'valid against the narrowed schema: "QM" is not one of "A" or "B".',
            id="the-inherited-default",
        ),
        pytest.param(
            _link(),
            _link(copy=True),
            "Cannot declare field 'blocks' for need type 'spec': Link type 'blocks' "
            "declares 'copy' for every need type.",
            id="a-link-copy",
        ),
        pytest.param(
            CLOSED,
            replace(
                CLOSED,
                derive=DeriveRule(kind="copy", field="title"),
                nullable=True,
            ),
            "Cannot declare field 'asil' for need type 'spec' with another "
            "derivation: a field is derived per need type by its derive_by_type.; "
            "Cannot change 'nullable' from False to True in child.",
            id="a-derivation-and-nullable",
        ),
    ],
)
def test_a_declaration_that_widens_is_refused(
    base: FieldSchema | LinkSchema, overlay: FieldSchema | LinkSchema, message: str
) -> None:
    schema = _schema(base)
    with pytest.raises(ValueError) as exc_info:
        schema.add_type_overlay("spec", overlay)
    assert str(exc_info.value) == message
    assert schema.type_declarations(base.name) == {}


def test_a_narrowing_is_declared() -> None:
    schema = _schema(OPEN)
    overlay = replace(OPEN, nullable=False, allow_extend=False)
    schema.add_type_overlay("spec", overlay)
    assert schema.type_declarations("asil") == {"spec": overlay}


def test_a_replacement_keeps_every_declaration_a_narrowing() -> None:
    """A field replaced while need types declare it anew: each declaration must stay
    a narrowing of the replacement, on every need type."""
    schema = _schema(OPEN)
    schema.add_type_overlay(
        "req",
        replace(
            OPEN, schema={"type": "string", "enum": ["A", "B", "QM"], "minLength": 1}
        ),
    )
    schema.add_type_overlay(
        "spec",
        replace(
            OPEN,
            schema={"type": "string", "enum": ["A", "B"], "minLength": 1},
            default=FieldLiteralValue("A"),
        ),
    )
    # still a narrowing of both
    wider = replace(
        OPEN, schema={"type": "string", "enum": ["A", "B", "QM", "X"], "minLength": 1}
    )
    schema.replace_field(wider)
    assert schema.global_declaration("asil") is wider
    # the replacement leaves 'B' out, which spec's declaration admits
    narrower = replace(
        OPEN,
        schema={"type": "string", "enum": ["A", "QM"], "minLength": 1},
        nullable=False,
    )
    with pytest.raises(ValueError) as exc_info:
        schema.replace_field(narrower)
    assert str(exc_info.value) == (
        "Cannot replace field 'asil' with type 'string' (items None): need type "
        "'req' declares it, and not as a narrowing of it: Child 'enum' values "
        "['A', 'B', 'QM'] are not a subset of parent 'enum' values ['A', 'QM'].; "
        "Cannot change 'nullable' from False to True in child."
    )
    assert schema.global_declaration("asil") is wider


def test_a_replacement_checks_the_declarations_of_every_type() -> None:
    """The declarations of a later need type are checked, not those of the first."""
    schema = _schema(OPEN)
    schema.add_type_overlay("req", replace(OPEN, allow_extend=False))
    schema.add_type_overlay("spec", replace(OPEN, description="spec"))
    with pytest.raises(ValueError) as exc_info:
        schema.replace_field(replace(OPEN, allow_extend=False))
    assert str(exc_info.value) == (
        "Cannot replace field 'asil' with type 'string' (items None): need type "
        "'spec' declares it, and not as a narrowing of it: Cannot change "
        "'allow_extend' from False to True in child."
    )


# -- rule 9 reports what the narrowing makes invalid --------------------------------

#: a field whose own default is outside its own enum: validation reports it per need
INVALID_DEFAULT = FieldSchema(
    name="asil",
    schema={"type": "string", "enum": ["A", "B"]},
    allow_defaults=True,
    default=FieldLiteralValue("Z"),
)


def test_the_fields_own_invalid_default_is_not_a_narrowing_problem() -> None:
    assert (
        narrowing_problems(
            INVALID_DEFAULT, replace(INVALID_DEFAULT, description="spec")
        )
        == []
    )


def test_a_new_default_inside_the_narrowed_enum() -> None:
    overlay = replace(
        INVALID_DEFAULT,
        schema={"type": "string", "enum": ["A"]},
        default=FieldLiteralValue("A"),
    )
    assert narrowing_problems(INVALID_DEFAULT, overlay) == []


def test_a_repeated_link_default_is_one_link() -> None:
    """A link default is validated as a need's links are: each target once."""
    base = _link(allow_defaults=True)
    narrowed = {"type": "array", "items": {"type": "string"}, "maxItems": 1}
    twice = _link(
        allow_defaults=True,
        schema=narrowed,
        default=LinksLiteralValue([NeedLink(id="A"), NeedLink(id="A")]),
    )
    assert narrowing_problems(base, twice) == []
    two = _link(
        allow_defaults=True,
        schema=narrowed,
        default=LinksLiteralValue([NeedLink(id="A"), NeedLink(id="B")]),
    )
    assert narrowing_problems(base, two) == [
        "Default ['A', 'B'] is not valid against the narrowed schema: "
        '["A","B"] has more than 1 item.'
    ]


def test_a_new_default_is_valid_against_the_narrowed_schema() -> None:
    """A default the declaration introduces is checked, also when the field's own
    schema refuses it too: only a default it takes from the field is the field's."""
    base = FieldSchema(
        name="asil",
        schema={"type": "string", "enum": ["A", "B"]},
        allow_defaults=True,
        default=FieldLiteralValue("A"),
    )
    narrowed = {"type": "string", "enum": ["A"]}
    assert narrowing_problems(
        base, replace(base, schema=narrowed, default=FieldLiteralValue("C"))
    ) == [
        'Default \'C\' is not valid against the narrowed schema: "C" is not one of "A".'
    ]
    assert narrowing_problems(
        base,
        replace(
            base,
            schema=narrowed,
            predicate_defaults=(('status == "open"', FieldLiteralValue("C")),),
        ),
    ) == [
        "Default 'C' of the predicate 'status == \"open\"' is not valid against the "
        'narrowed schema: "C" is not one of "A".'
    ]
