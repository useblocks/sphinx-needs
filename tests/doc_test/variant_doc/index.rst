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

.. needtable::
   :filter: status in ("open", "close", "progress")

.. toctree::
   :maxdepth: 2
   :caption: Contents:
