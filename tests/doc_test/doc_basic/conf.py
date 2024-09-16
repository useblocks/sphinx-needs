project = "needs"
version = "0.1.0"
copyright = "2024"

extensions = ["sphinx_needs"]

suppress_warnings = ["epub.unknown_project_files"]

needs_id_regex = "^[A-Za-z0-9_]"

needs_types = [
    {
        "directive": "story",
        "title": "User Story",
        "prefix": "US_",
        "color": "#BFD8D2",
    },
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "SP_",
        "color": "#FEDCD2",
    },
    {
        "directive": "impl",
        "title": "Implementation",
        "prefix": "IM_",
        "color": "#DF744A",
    },
    {
        "directive": "test",
        "title": "Test Case",
        "prefix": "TC_",
        "color": "#DCB239",
    },
]
