.. _ubCode: https://ubcode.useblocks.com/
.. _`schema_validation`:

Schema validation
=================

This is the documentation of the schema validation implementation as proposed in
the `Github discussion #1451 <https://github.com/useblocks/sphinx-needs/discussions/1451>`__.

The new schema validation is a versatile, fast, safe and declarative way to enforce constraints
on need items and their relations in Sphinx-Needs. It is supposed to replace the legacy
:ref:`needs_constraints` and :ref:`needs_warnings` configuration options in future.
See :ref:`migration_from_warnings_constraints` for details on how to migrate.

.. important::

   **Strong Typing System**: Sphinx-Needs features a comprehensive strong typing system
   that extends throughout the entire application. This includes:

   - **Early Type Validation**: All need fields are validated against their defined types,
     with support for :ref:`dynamic_functions`, :ref:`variants <needs_variant_support>`,
     :ref:`needextend` and :ref:`global defaults <needs_global_options>`. Needs that do not
     conform to their types are not created and lead to a warning.
   - **JSON Export**: Generated :ref:`needs.json <needs_builder>` files honor the user provided
     types
   - **Multi value extra options**: Array types for extra options are fully supported
   - **Gradual Migration**: Existing projects can migrate step-by-step to the new system,
     with string types as default for untyped fields.
   - **Safety**: The new type system core makes it possible to configure fields individually.
     Users may decide not to disallow variants / dynamic functions / defaults or needextend on
     certain fields. This makes it possible to build a system in which the RST code is the *only*
     source of truth.
     (Look at the constructor of :py:class:`sphinx_needs.needs_schema.FieldSchema`.)

   This represents a major improvement in data integrity and developer experience compared
   to the previous string-typed system.

Type System
-----------

The typing system features the following types for need fields:

- **Primitive types**: ``string``, ``boolean``, ``integer``, ``number``
- **List types**: ``array[string]``, ``array[boolean]``, ``array[integer]``, ``array[number]``

The schema validation implementation is based on JSON schema, therefore
`JSON schema types <https://json-schema.org/understanding-json-schema/reference/type>`__
are used for types and schema description.

Type representation in Python is as follows:

- JSON ``string`` -> Python ``str``
- JSON ``boolean`` -> Python ``bool``
- JSON ``integer`` -> Python ``int``
- JSON ``number`` -> Python ``float``
- JSON ``array`` -> Python ``list``

Schema configuration
--------------------

The schema is configured in multiple places:

- :ref:`needs_extra_options` is the place to add new extra options that are then available
  for all need types. The type information for each field is globally set here, so it is valid
  for all the usages of that field for any need type. This is required for a coherent data
  storage, as it would be expected by a database system. If different data types are needed for the
  same option, it means creating a new extra option with a different name and type.

  Further, the ``schema`` field in ``needs_extra_options`` also supports setting global
  schema constraints for that option, that will be checked for each need type. E.g.
  minimum/maximum for integers, enum for strings, etc.

- :ref:`needs_extra_links` is the place to add new link options that are then available
  for all need types. The type for link fields is pre-set to ``array[string]``,
  as links are always lists of need IDs. The ``schema`` field in ``needs_extra_links``
  supports setting global schema constraints for that link option, that will be checked
  for each need type. E.g. minimum/maximum number of links or need id patterns. The schema
  defined here always runs on unresolved local needs, i.e. links are a list of IDs.
- :ref:`core fields <need>` such as ``type``, ``id``, ``title``, ``status`` or ``tags`` have
  pre-defined types that cannot be changed.
- :ref:`needs_schema_definitions` and :ref:`needs_schema_definitions_from_json` are the places to
  define more complex validations that can act on need types, collection of fields and
  resolved network links. It is based on JSON schema, but adapted and used in a way so it
  fits perfectly in the Sphinx-Needs ecosystem.

.. important::

   JSON schema requires type information in all schemas to actually perform validation.
   For example, validating an
   `integer minimum <https://json-schema.org/understanding-json-schema/reference/numeric#range>`__
   constraint on a string field does not make sense, but, depending on the implementation,
   JSON schema might not complain about this. Therefore, Sphinx-Needs injects the type information
   from ``needs_extra_options`` and ``needs_extra_links`` as well as the core fields
   into the :ref:`needs_schema_definitions`.

The next sections guides through an example and how do use the type and schema system to enforce
constraints on need items and links between them.

Modeling example
----------------

Imagine the following modeling of need items:

.. figure:: 01_basic_setup.drawio.png

There are a few things to note about this setup:

- the extra options ``efforts``, ``approval`` and
  ``asil`` (for **A**\ utomotive **S**\ ecurity **I**\ ntegrity **L**\ evel) are typed
- the assigned extra options differ between need types
- the fields may be optional for a need type, required or even not allowed
- some validation rules are local to the need itself, while others
  require information from other needs (network validation)
- the needs link to each other in a specific way, so a
  safe ``impl`` can only link to a safe ``spec`` which can only
  link to a safe ``feat`` item

The schema validation in Sphinx-Needs allows you to define declarative rules for validating need
items based on their types, properties and relationships.

This includes both local checks (validating properties of a single need) and network checks
(validating relationships between multiple needs). In local checks links to other needs are just
a list of string need IDs while network checks run on the data of the linked need.

The distinction is especially important in an IDE context, where local checks can provide instant
feedback while network requires building the full network index first.

.. TODO enable this once the PR is merged
   .. note::
   
      The
      `full example <https://github.com/useblocks/sphinx-needs/tree/master/tests/doc_test/doc_schema_example>`__
      for below configuration can be found in the tests.
      It can directly be executed with::
   
        tests/doc_test/doc_schema_example $ uv run sphinx-build -b html . _build

Here are the full example files as a reference:

.. dropdown:: conf.py

   .. literalinclude:: ../../tests/doc_test/doc_schema_example/conf.py
      :language: python

.. dropdown:: index.rst

   .. literalinclude:: ../../tests/doc_test/doc_schema_example/index.rst
      :language: rst

.. dropdown:: ubproject.toml

   .. literalinclude:: ../../tests/doc_test/doc_schema_example/ubproject.toml
      :language: toml

.. dropdown:: schemas.json

   .. literalinclude:: ../../tests/doc_test/doc_schema_example/schemas.json
      :language: json

Field Configuration
-------------------

Above modeling can be reached with the following ubproject.toml configuration:

.. literalinclude:: ../../tests/doc_test/doc_schema_example/ubproject.toml
   :language: toml

As can be seen, the ``needs.extra_options`` section defines the extra options used in the modeling
together with their types and possible schema constraints.

The pictured need types and extra links are also defined.

The given types will be injected to the JSON schema models, if not provided there.

Schema Configuration
--------------------

Schemas can be configured in two ways: directly in the ``conf.py`` file or loaded from a separate
JSON file.

**JSON File Configuration (recommended)**

The preferred approach is to define schemas in a separate JSON file and load them using the
:ref:`needs_schema_definitions_from_json` configuration option:

.. code-block:: python

   # conf.py
   needs_schema_definitions_from_json = "schemas.json"

Then create a small ``schemas.json`` file in your project root:

.. code-block:: json

   {
     "$defs": {
       "type-spec": {
         "properties": {
           "type": { "const": "spec" }
         }
       },
     },
     "schemas": [
       {
         "severity": "warning",
         "message": "id must be uppercase",
         "select": {
             "$ref": "#/$defs/type-spec"
         },
         "validate": {
           "local": {
             "properties": {
               "id": { "pattern": "^SPEC_[A-Z0-9_]+$" }
             }
           }
         }
       }
     ]
   }

Above schema already makes use of :ref:`schema_reuse` via ``$defs`` and ``$ref``.

.. dropdown:: Full version for above example modeling

   .. literalinclude:: ../../tests/doc_test/doc_schema_example/schemas.json

Benefits of JSON File Configuration:

- **Declarative**: Schema definitions are separate from Python configuration
- **Version Control**: Easy to track changes to validation rules
- **IDE Support**: `ubCode`_ can read the JSON file

**Python Configuration (Alternative)**

Alternatively, schemas can be configured directly using the :ref:`needs_schema_definitions`
configuration option in ``conf.py``:

.. code-block:: python

   needs_schema_definitions = {
     "$defs": {
       # reusable schema components
       "type-spec": {
         "properties": {
           "type": { "const": "spec" }
         }
       },
     },
     "schemas": [
       {
         "severity": "warning",
         "message": "id must be uppercase",
         "select": {
             "$ref": "#/$defs/type-spec"
         },
         "validate": {
           "local": {
             "properties": {
               "id": { "pattern": "^SPEC_[A-Z0-9_]+$" }
             }
           }
         }
       }
     ]
   }

.. _`local_validation`:

Local Validation
----------------

Consider the following local checks:

.. figure:: 02_local_check.drawio.png

Local validation checks individual need properties without requiring information from other needs:

- the ``efforts`` field

  - is of type integer
  - is optional for ``spec`` and ``feat`` and disallowed for ``impl``
  - has a minimum value of 0
  - has a maximum value of 20

- the ``approval`` field

  - is of type boolean
  - is optional for ``spec`` and ``feat`` and disallowed for ``impl``
  - is required in case the field ``efforts`` has a value greater than 15;
    if the condition is not satisfied, the violation should be returned as ``violation``
  - must be set to ``True`` in case the field ``efforts`` has a value greater than 15;
    if the condition is not satisfied, the violation should be returned as ``warning``

- the ``asil`` field

  - is of type string
  - has a string subtype of ``enum``
  - can only be set to one of the following values: ``QM | A | B | C | D``

Example local validation schema:

.. literalinclude:: ../../tests/doc_test/doc_schema_example/schemas.json
   :lines: 1-49,57-143,183-
   :language: json

Above conditions can all be checked locally on need level which allows instant user feedback
in IDE extensions such as `ubCode`_.

Network Validation
------------------

On the other hand, network checks require information from other needs:

.. figure:: 03_network_check.drawio.png

After network resolution, the following checks can be performed:

- a 'safe' ``impl`` that has an ``asil`` of ``A | B | C | D`` cannot ``link`` to ``spec`` items
  that have an ``asil`` of ``QM``
- a safe ``impl`` can only link approved ``spec`` items with link type ``links``
- a safe ``spec`` can only link to safe and approved ``feat`` items with link type ``details``
- a safe ``impl`` can link to *one or more* safe ``spec`` items
- a spec can only link to *exactly one* ``feat``
- additional links to non-validating items are not allowed (that is the min/max constraints are
  met but there are failing additional link targets)

Example:

.. literalinclude:: ../../tests/doc_test/doc_schema_example/schemas.json
   :lines: 1-41,48-49,144-
   :language: json

Network validation supports various constraints on linked needs:

**Link Count Constraints**

- ``validate.local.properties.<link>.minItems``: Minimum number of links required
- ``validate.local.properties.<link>.maxItems``: Minimum number of links required
- ``validate.network.<link>.minContains``: Minimum number of valid links required
- ``validate.network.<link>.maxContains``: Maximum number of valid links allowed

``minItems`` and ``maxItems`` are located under local, as a link field is always a list of
need IDs (strings) on local level. That is enough to validate the number of links.

``minContains`` and ``maxContains`` are located under network, as they validate the actual
need objects that are linked.

.. code-block:: json

   {
     "validate": {
       "network": {
         "links": {
           "contains": {
             "local": {
               "properties": {
                  "type": { "const": "spec" },
                  "asil": { "enum": ["A", "B", "C", "D"] }
               },
               "required": ["type", "asil"]
             }
           },
           "minContains": 1, // At least one link validates 'contains'
           "maxContains": 3  // Maximum three links validate 'contains'
         }
       }
     }
   }

The ``items`` property can be used to define validation rules that must be satisfied
for *all* linked needs:

.. code-block:: json

   {
     "validate": {
       "network": {
         "links": {
           "items": {
             "local": {
               "properties": {
                 "status": { "const": "approved" }
               }
             }
           }
         }
       }
     }
   }

**Nested Network Validation**

Network validation can be nested to validate multi-hop link chains:

.. code-block:: json

   {
     "id": "safe-impl-chain",
     "select": {
       "$ref": "#/$defs/safe-impl"
     },
     "validate": {
       "network": {
         "links": {
           "contains": {
             "local": {
               "$ref": "#/$defs/safe-spec"
             },
             "network": {
               "links": {
                 "contains": {
                   "local": {
                     "$ref": "#/$defs/safe-feat"
                   }
                 },
                 "minContains": 1
               }
             }
           },
           "minContains": 1
         }
       }
     }
   }

This validates that:

1. A safe implementation links to safe specifications
#. Those specifications in turn link to safe features
#. Both link levels have minimum count requirements

Schema Components
-----------------

Select Criteria
~~~~~~~~~~~~~~~

The ``select`` section defines which needs the schema applies to:

.. code-block:: json

   {
     "select": {
       "allOf": [
         { "$ref": "#/$defs/type-spec" },
         { "$ref": "#/$defs/high-efforts" }
       ]
     }
   }

If no ``select`` is provided, the schema applies to all needs.
``select`` is always a local validation, meaning it only checks properties of the need itself.
``select`` validation also means all link fields are list of need ID strings, not need objects.

Validation Rules
~~~~~~~~~~~~~~~~

The ``validate`` section contains the actual validation rules:

**Local validation** checks individual need properties:

.. code-block:: json

   {
     "validate": {
       "local": {
         "properties": {
           "status": { "enum": ["open", "closed", "in_progress"] }
         },
         "required": ["status"]
       }
     }
   }

``local`` validation also means all link fields are list of need ID strings, not need objects.

**Unevaluated Properties Control**

The ``unevaluatedProperties`` property controls whether properties not explicitly defined in the
schema are allowed:

.. code-block:: json

   {
     "validate": {
       "local": {
         "properties": {
           "status": { "enum": ["open", "closed"] }
         },
         "unevaluatedProperties": false // Only 'status' property allowed
       }
     }
   }

When ``unevaluatedProperties: false`` is set and a need has additional properties,
validation will report:

.. code-block:: text

   Schema message: Unevaluated properties are not allowed ('comment', 'priority' were unexpected)

This is useful for enforcing strict property schemas and catching typos in property names.
To find out which properties are actually set, the validated needs are reduced to field values
that are not on their default value.

**unevaluatedProperties with allOf**

The ``unevaluatedProperties`` validation also works with properties defined in ``allOf`` constructs.
Properties from all schemas in the ``allOf`` array are considered as evaluated:

.. code-block:: json

   {
     "validate": {
       "local": {
         "properties": { "asil": {} },
         "unevaluatedProperties": false,
         "allOf": [
            { "properties": { "comment": {} } }
         ]
       }
     }
   }

In this example, both ``asil`` and ``comment`` properties are considered evaluated, so only these
two properties would be allowed on the need. Empty schemas for a field are allowed to mark
them as evaluated. The behavior is aligned with the JSON Schema specification.

**required vs unevaluatedProperties**

The ``required`` list has no impact on ``unevaluatedProperties`` validation.
Properties listed in ``required`` must still be explicitly defined in ``properties`` or pulled
in via ``allOf`` to be considered evaluated:

.. code-block:: json

   {
     "validate": {
       "local": {
         "properties": { "status": {} },
         "required": ["status", "priority"], // priority not in properties
         "unevaluatedProperties": false
       }
     }
   }

In this case, a need with a ``priority`` property would still trigger an unevaluated properties
error, even though ``priority`` is in the ``required`` list.

Severity Levels
~~~~~~~~~~~~~~~

Each schema can specify a severity level:

- ``violation`` (default): Violation message
- ``warning``: Warning message
- ``info``: Informational message

.. code-block:: json

   {
     "severity": "warning",
     "message": "Approval required due to high efforts"
   }

The config :ref:`needs_schema_severity` can be used to define a minimum severity level for a
warning to be reported.

.. _`schema_reuse`:

Schema Definitions ($defs)
~~~~~~~~~~~~~~~~~~~~~~~~~~

Reusable schema components can be defined in the ``$defs`` section:

.. code-block:: json

   {
     "$defs": {
       "type-feat": {
         "properties": {
           "type": { "const": "feat" }
         }
       },
       "safe-need": {
         "properties": {
           "asil": { "enum": ["A", "B", "C", "D"] }
         },
         "required": ["asil"]
       },
       "safe-feat": {
         "allOf": [
           { "$ref": "#/$defs/safe-need" },
           { "$ref": "#/$defs/type-feat" }
         ]
       }
     }
   }

A full example is outlined in the :ref:`local_validation` section.
The key ``$ref`` must appear as the only key in the schema where it is used.

Recursive references are not allowed, i.e. a schemas cannot directly or indirectly
reference itself.

Error Messages
--------------

Validation errors include detailed information:

- **Severity**: The severity level of the violation
- **Field**: The specific field that failed validation
- **Need path**: The ID of the need that failed or the link chain for network validation
- **Schema path**: The JSON path within the schema that was violated
- **User message**: Custom message from the needs_schema.schemas list
- **Schema message**: Detailed technical validation message from the validator

Example error output::

  Need 'SPEC_P01' has validation errors:
    Severity:       violation
    Field:          id
    Need path:      SPEC_P01
    Schema path:    spec[1] > local > properties > id > pattern
    Schema message: 'SPEC_P01' does not match '^REQ[a-zA-Z0-9_-]*$'

For nested network validation, it can be difficult to determine which constraint and need
caused the error in the chain. In such cases, the error will emit details about the failed
need and the specific link that caused the issue::

  WARNING: Need 'IMPL_SAFE' has validation errors:
    Severity:       violation
    Need path:      IMPL_SAFE > links
    Schema path:    safe-impl-[links]->safe-spec-[links]->safe-req[0] > validate > network > links
    User message:   Safe impl links to safe spec links to safe req
    Schema message: Too few valid links of type 'links' (0 < 1) / nok: SPEC_SAFE

      Details for SPEC_SAFE
      Need path:      IMPL_SAFE > links > SPEC_SAFE > links
      Schema path:    safe-impl-[links]->safe-spec-[links]->safe-req[0] > links > validate > network > links
      Schema message: Too few valid links of type 'links' (0 < 1) / nok: REQ_UNSAFE

        Details for REQ_UNSAFE
        Field:          asil
        Need path:      IMPL_SAFE > links > SPEC_SAFE > links > REQ_UNSAFE
        Schema path:    safe-impl-[links]->safe-spec-[links]->safe-req[0] > links > links > local > allOf > 0 > properties > asil > enum
        Schema message: 'QM' is not one of ['A', 'B', 'C', 'D'] [sn_schema.network_contains_too_few]

Schema Violation Report JSON File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Schema violations are also stored in a ``schema_violations.json`` file under the output directory.

.. dropdown:: Example

   .. code-block:: json

      {
        "validation_summary": "Schema validation completed with 2 warning(s) in 0.002 seconds. Validated 1368 needs/s.",
        "validated_needs_per_second": 1368,
        "validated_needs_count": 3,
        "validation_warnings": {
          "FEAT_unsafe": [
            {
              "log_lvl": "warning",
              "type": "sn_schema",
              "subtype": "local_fail",
              "details": {
                "severity": "violation",
                "field": "id",
                "need_path": "FEAT_unsafe",
                "schema_path": "[0] > local > properties > id > pattern",
                "user_msg": "id must be uppercase with numbers and underscores",
                "validation_msg": "'FEAT_unsafe' does not match '^[A-Z0-9_]+$'"
              },
              "children": []
            }
          ],
          "IMPL_SAFE": [
            {
              "log_lvl": "warning",
              "type": "sn_schema",
              "subtype": "network_local_fail",
              "details": {
                "severity": "violation",
                "field": "asil",
                "need_path": "IMPL_SAFE > links > SPEC_UNSAFE",
                "schema_path": "safe-impl-[links]->safe-spec[7] > links > local > allOf > 0 > properties > asil > enum",
                "validation_msg": "'QM' is not one of ['A', 'B', 'C', 'D']"
              },
              "children": []
            }
          ]
        }
      }

.. _supported_data_types:

Supported Data Types
--------------------

Sphinx-Needs supports comprehensive data type validation for need options through JSON Schema.
The following data types are available for need options:

String Type
~~~~~~~~~~~

String fields store textual data with optional format validation:

.. code-block:: json

   {
     "properties": {
       "description": {
         "type": "string",
         "minLength": 10,
         "maxLength": 500
       }
     }
   }

The following schema constraints are supported for ``string`` fields:

- ``minLength`` / ``maxLength``: Minimum and maximum length of the string
- ``pattern``: Regex pattern that the string must match
- ``format``: Predefined string formats (see below)
- ``enum``: Enumerated set of allowed string values
- ``const``: Exact allowed string value

**String Formats**

String fields can be validated against specific formats using the ``format`` property:

**Date and Time Formats (ISO 8601)**

.. code-block:: json

   {
     "properties": {
       "start_date": {"type": "string", "format": "date"},          // 2023-12-25
       "created_at": {"type": "string", "format": "date-time"},     // 2023-12-25T14:30:00Z
       "meeting_time": {"type": "string", "format": "time"},        // 14:30:00
       "project_duration": {"type": "string", "format": "duration"} // P1Y2M10DT2H30M
     }
   }

**Communication formats**

.. code-block:: json

   {
     "properties": {
       "contact_email": {"type": "string", "format": "email"}, // user@example.com (RFC 5322)
       "project_url": {"type": "string", "format": "uri"},     // https://example.com (RFC 3986)
       "tracking_id": {"type": "string", "format": "uuid"}     // 123e4567-e89b-12d3-a456-426614174000 (RFC 4122)
     }
   }

**Enumerated Values**

.. code-block:: json

   {
     "properties": {
       "priority": {
         "type": "string",
         "enum": ["low", "medium", "high", "critical"]
       }
     }
   }

Integer Type
~~~~~~~~~~~~

Integer fields store whole numbers with optional range constraints:

.. code-block:: json

   {
     "properties": {
       "efforts": {
         "type": "integer",
         "minimum": 0,
         "maximum": 100,
         "multipleOf": 5
       }
     }
   }

The following schema constraints are supported for ``integer`` fields:

- ``minimum`` / ``maximum``: Minimum and maximum value of the integer
- ``exclusiveMinimum`` / ``exclusiveMaximum``: Exclusive minimum and maximum value
- ``multipleOf``: Value must be a multiple of this integernumber
- ``enum``: Enumerated set of allowed integer values
- ``const``: Exact allowed integer value

Number Type
~~~~~~~~~~~

Number fields store floating-point values:

.. code-block:: json

   {
     "properties": {
       "cost_estimate": {
         "type": "number",
         "minimum": 0.0,
         "exclusiveMaximum": 1000000.0
       }
     }
   }

The following schema constraints are supported for ``number`` fields:

- ``minimum`` / ``maximum``: Minimum and maximum value of the number
- ``exclusiveMinimum`` / ``exclusiveMaximum``: Exclusive minimum and maximum value
- ``multipleOf``: Value must be a multiple of this number
- ``enum``: Enumerated set of allowed number values
- ``const``: Exact allowed number value

Boolean Type
~~~~~~~~~~~~

Boolean fields store true/false values with flexible input handling:

.. code-block:: json

   {
     "properties": {
       "approval": {"type": "boolean"},
       "is_critical": {"type": "boolean", "const": true}
     }
   }

**Accepted Boolean Values**:

- **Truthy**: ``true``, ``yes``, ``y``, ``on``, ``1``, ``True``, ``Yes``, ``On``
- **Falsy**: ``false``, ``no``, ``n``, ``off``, ``0``, ``False``, ``No``, ``Off``

The ``enum`` keyword cannot be used for booleans as ``const`` is functionally equivalent and
more expressive.

Array Type
~~~~~~~~~~

Array fields store lists of homogeneous typed values:

.. code-block:: json

   {
     "properties": {
       "tags": {
         "type": "array",
         "items": {"type": "string"},
         "minItems": 1,
         "maxItems": 10
       },
       "priorities": {
         "type": "array",
         "items": {"type": "integer"},
         "minItems": 1
       },
       "approvals": {
         "type": "array",
         "items": {"type": "boolean"}
       }
     }
   }

**Array Properties**:

- ``items``: Schema for all array elements (required).
  The dictionary can contain any of the basic type schemas outlined above.
  The ``items.type`` field is required.
- ``minItems`` / ``maxItems``: Array size constraints
- ``contains`` Schema for some elements in the array.
  The dictionary can contain any of the basic type schemas outlined above.
- ``minContains`` / ``maxContains``: Constraints on number of elements matching ``contains``;

  - If ``minContains`` is not given, it defaults to 1 when ``contains`` is present.
  - If ``maxContains`` is not given, there is no upper limit.

Regex Pattern Restrictions
--------------------------

When using ``pattern`` for string types in schemas, the regex patterns must be compatible
across multiple language engines such as Python, Rust, and SQLite to consume the patterns
also in the bigger Sphinx-Needs ecosystem.
The following constructs are **not allowed**:

**Prohibited Constructs:**

- **Lookaheads/Lookbehinds**: ``(?=pattern)``, ``(?!pattern)``, ``(?<=pattern)``, ``(?<!pattern)``
- **Backreferences**: ``\1``, ``\2``, etc.
- **Nested Quantifiers**: ``(a+)+``, ``(a*)*`` (can cause catastrophic backtracking)
- **Possessive Quantifiers**: ``a++``, ``a*+`` (not supported in all engines)
- **Atomic Groups**: ``(?>pattern)`` (not supported in all engines)
- **Recursive Patterns**: ``(?R)`` (not supported in all engines)

**Safe Patterns:**

.. code-block:: json

   {
     "properties": {
       "id": { "pattern": "^[A-Z0-9_]+$" },           // ✓ Safe
       "version": { "pattern": "^v[0-9]+\\.[0-9]+$" }, // ✓ Safe
       "status": { "pattern": "^(open|closed)$" }      // ✓ Safe
     }
   }

**Unsafe Patterns:**

.. code-block:: json

   {
     "properties": {
       "id": { "pattern": "^(?=.*[A-Z]).*$" },      // ✗ Lookahead
       "ref": { "pattern": "^(\\w+)_\\1$" },        // ✗ Backreference
       "complex": { "pattern": "^(a+)+$" }          // ✗ Nested quantifiers
     }
   }

The validation will reject schemas containing unsafe patterns and provide
clear error messages indicating the specific issue. Some constructs might be
restricted in future versions of Sphinx-Needs if they cannot be safely evaluated
in all relevant engines.

Best Practices
--------------

1. **Use descriptive IDs**: Give your schemas meaningful IDs for easier debugging
#. **Leverage $defs**: Define reusable schema components to avoid duplication
#. **Start with warnings**: Use ``warning`` severity during development, then upgrade to ``violation``
#. **Provide clear messages**: Include helpful ``message`` fields to guide users
#. **Test incrementally**: Add schemas gradually to avoid overwhelming validation errors
#. **Use select wisely**: Only apply schemas to relevant need types using ``select``

.. _`migration_from_warnings_constraints`:

Migration from Legacy Validation
--------------------------------

The schema validation system is designed to replace the older :ref:`needs_constraints` and
:ref:`needs_warnings` configuration options, offering significant advantages:

- **Declarative**: JSON-based configuration instead of Python code
- **Powerful**: Supports selection, local, and network validation
- **Performance**: Schema validation is faster than custom validations written in Python
- **IDE Support**: Full IntelliSense and validation in supported editors like `ubCode`_
- **Type Safety**: Strong typing with comprehensive data type support
- **Network Validation**: Multi-hop link validation capabilities
- **Maintainability**: Easier to read, write, and version control

**Migration Examples**

**From needs_constraints:**

.. code-block:: python

   # Old approach - needs_constraints
   needs_constraints = {
       "security": {
           "check_0": "'security' in tags",
           "severity": "CRITICAL"
       },
       "critical": {
           "check_0": "'critical' in tags",
           "severity": "CRITICAL",
           "error_message": "need {{id}} does not fulfill CRITICAL constraint"
       }
   }

.. code-block:: json

   {
     "schemas": [
       {
         "id": "security-constraint",
         "severity": "violation",
         "message": "Security needs must have security tag",
         "select": {
           "properties": {
             "tags": {
               "type": "array",
               "contains": {"const": "security"}
             }
           }
         },
         "validate": {
           "local": {
             "properties": {
               "tags": {
                 "type": "array",
                 "contains": {"const": "security"}
               }
             }
           }
         }
       }
     ]
   }

**From needs_warnings:**

.. code-block:: python

   needs_warnings = {
       "invalid_status": "status not in ['open', 'closed', 'done']",
   }

.. code-block:: json

   {
     "schemas": [
       {
         "id": "valid-status",
         "severity": "warning",
         "message": "Status must be one of the allowed values",
         "validate": {
           "local": {
             "properties": {
               "status": {
                 "enum": ["open", "closed", "done"]
               }
             },
             "required": ["status"]
           }
         }
       }
     ]
   }

**Network Validation Benefits**

The schema system provides capabilities not available in the legacy system:

.. code-block:: json

   {
     "schemas": [
       {
         "id": "safe-implementation-links",
         "message": "Safe implementations must link to approved specifications",
         "select": {
           "allOf": [
             {"$ref": "#/$defs/type-impl"},
             {"$ref": "#/$defs/safety-critical"}
           ]
         },
         "validate": {
           "network": {
             "links": {
               "contains": {
                 "local": {
                   "allOf": [
                     {"$ref": "#/$defs/type-spec"},
                     {"properties": {"approval": {"const": true}}}
                   ]
                 }
               },
               "minContains": 1
             }
           }
         }
       }
     ]
   }

This type of multi-need relationship validation was not possible with the legacy constraint
and warning systems.

**Recommended Migration Path**

1. **Audit existing constraints and warnings**: Review your current validation rules
2. **Start with local validations**: Convert simple property checks first
3. **Leverage network validation**: Replace complex Python logic with declarative schemas
4. **Test incrementally**: Validate schemas work as expected before removing legacy rules
5. **Update documentation**: Ensure team members understand the new validation approach

Tests
-----

A multitude of test cases exist, that can also be used as a reference for how to use the
type system and schema validation. Whithin the
`YAML based fixtures <https://github.com/useblocks/sphinx-needs/tree/master/tests/schema/fixtures>`__
you will always find full project examples.

The tests use snapshot testing, and the expected validation results can be found
`here <https://github.com/useblocks/sphinx-needs/blob/master/tests/schema/__snapshots__/test_schema.ambr>`__
.

