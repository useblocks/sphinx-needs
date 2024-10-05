LIST2NEED GLOBAL TAGS
=====================


.. list2need::
   :types: story, spec, test
   :presentation: nested
   :delimiter: .
   :tags: global_tag1, global_tag2, global_tag3

   * (NEED-W)Need example on level 1 ((status="open"))
   * (NEED-X)Need example on level 1 ((status="done", tags="tag1, tag2, tag3"))
   * (NEED-Y)Link example ((links="NEED-W, NEED-Y"))
   * (NEED-Z)New line example.
     With some content in the next line.
     ((status="in progress", links="NEED-3"))



