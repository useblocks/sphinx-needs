extensions = ["sphinx_needs"]

needs_types = [
    {
        "directive": "story",
        "title": "User Story",
        "prefix": "US_",
        "color": "#BFD8D2",
        "style": "node",
    },
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
        "style": "node",
    },
    {
        "directive": "impl",
        "title": "Implementation",
        "prefix": "IM_",
        "color": "#DF744A",
        "style": "node",
    },
    {
        "directive": "test",
        "title": "Test Case",
        "prefix": "TC_",
        "color": "#DCB239",
        "style": "node",
    },
]

needs_extra_options = ["author", "author_image"]

needs_layouts = {
    "example": {
        "grid": "simple_side_right_partial",
        "layout": {
            "head": ['**<<meta("title")>>** for *<<meta("author")>>*'],
            "meta": [
                '**status**: <<meta("status")>>',
                '**author**: <<meta("author")>>',
                '**author_image**: <<meta("author_image")>>',
            ],
            "side": ['<<image("_images/smile.png", align="center")>>'],
        },
    },
    "image_author": {
        "grid": "simple_side_right_partial",
        "layout": {
            "head": ['**<<meta("title")>>**'],
            "meta": [
                '**status**: <<meta("status")>>',
                r'<<meta("author", prefix="\*\*author\*\*: ")>>',
                r'<<meta("author_image", prefix="\*\*author_image\*\*: ")>>',
            ],
            "side": ['<<image("field:author_image", align="center")>>'],
        },
    },
    "optional_author": {
        "grid": "simple",
        "layout": {
            "head": ['**<<meta("title")>>**'],
            "meta": [
                '**status**: <<meta("status")>>',
                r'<<meta("author", prefix="\*\*author\*\*: ")>>',
            ],
        },
    },
    "footer_grid": {
        "grid": "simple_footer",
        "layout": {
            "head": ['**<<meta("title")>>** for *<<meta("author")>>*'],
            "meta": [
                '**status**: <<meta("status")>>',
                '**author**: <<meta("author")>>',
            ],
            "footer": ['**custom footer for <<meta("title")>>**'],
        },
    },
}
