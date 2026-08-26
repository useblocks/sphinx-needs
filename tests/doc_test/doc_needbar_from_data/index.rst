TEST DOCUMENT needbar FROM_DATA labels
======================================

.. story:: Story 1
    :id: STORY_1
    :tags: a

.. story:: Story 2
    :id: STORY_2
    :tags: b

.. needbar:: ylabels only
    :ylabels: FROM_DATA

    Tags a, 'a' in tags, 'a' in tags
    Tags b, 'b' in tags, 'b' in tags

.. needbar:: xlabels only
    :xlabels: FROM_DATA

    A          , B
    'a' in tags, 'b' in tags

.. needbar:: both
    :xlabels: FROM_DATA
    :ylabels: FROM_DATA

         , A          , B
    Tags , 'a' in tags, 'b' in tags

.. needbar:: no labels

    'a' in tags, 'b' in tags
