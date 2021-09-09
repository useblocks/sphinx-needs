Need extract
============


.. story:: needextract story 1
   :id: extract_story_001
   :secret_level: top_level

.. story:: needextract story 2
   :id: extract_story_002
   :secret_level: low_level

.. test:: needextract test 2
   :id: extract_test_001

.. needextract::
   :filter: type == "story" and secret_level == current_secret_level
   :layout: clean
   :style: green_border
