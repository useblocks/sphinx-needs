Variant Handling Test
=====================

.. spec:: No ID
   :status: <<['church' in tags]:open, ['extension' in tags]:progress, close>>
   :tags: school, extension, needs

.. spec:: Tags Example
   :id: VA_003
   :status: <<[all(x in build_tags for x in ['tag_a', 'tag_b'])]:tags_implemented, closed>>

.. story:: Test story
   :id: ST_001
   :status: close
   :author: <<change_author:Daniel Woste, Randy>>


.. spec:: Custom Variant
   :id: CV_0002
   :status: <<[value in tags]:open, close>>
   :value: start
   :tags: commence, start, begin
   :relates: <<[value in tags]:SPEC_003, SPEC_004>>

.. spec:: Variant Specification
   :id: SPEC_003
   :status: <<['tag_a' in build_tags]:open, unknown>>

.. spec:: Unknown Variant
   :id: SPEC_004
   :status: <<['tag_c' in build_tags]:open, unknown>>

.. spec:: Disabled variant parsing
   :id: SPEC_005
   :value: <<['tag_a' in build_tags]:open, close>>
   :links: <<['tag_a' in build_tags]:SPEC_003, SPEC_004>>

.. spec:: Bool field with multiple variants
   :id: SPEC_006
   :field_bool: <<['tag_a' in build_tags]:1, 0>>, <<['tag_b' in build_tags]:0, 1>>

.. spec:: Array of integer field with multiple variants
   :id: SPEC_007
   :field_array_int: <<['tag_a' in build_tags]:1, 2>>, <<['tag_b' in build_tags]:3, 4>>

.. needtable::
   :filter: status in ("open", "close", "progress")

.. toctree::
   :maxdepth: 2
   :caption: Contents:
