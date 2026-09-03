LIST2NEED OPTIONS
=================


.. list2need::
   :types: story, spec, test
   :presentation: nested
   :delimiter: .

   * (NEED-1)Need example on level 1 ((status="open"))
   * (NEED-2)Need example on level 1 ((status="done", tags="tag1, tag2, tag3"))
   * (NEED-3)Link example ((links="NEED-1, NEED-2"))
   * (NEED-4)New line example.
     With some content in the next line.
     ((status="in progress", links="NEED-3"))



