# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "test_parse"
copyright = "2025, useblocks"
author = "team useblocks"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
# html_static_path = ["_static"]

extensions = ["sphinx_needs", "sphinx_codelinks"]

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
        "directive": "implement",
        "title": "Implementation",
        "prefix": "IM_",
        "color": "#DF744A",
        "style": "node",
    },
    {
        "directive": "impl",
        "title": "Impl",
        "prefix": "IMPL_",
        "color": "#DFd44A",
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

needs_extra_options = ["priority"]

src_trace_config_from_toml = "src_trace.toml"

# # TODO implement me
# src_trace_set_local_url = True
# src_trace_local_url_field = "local-url"
# src_trace_set_remote_url = True
# src_trace_remote_url_field = "remote-url"

# src_trace_projects = {
#     # TODO use the key (add it to the src-trace need)
#     "dcdc": {
#         "type": "cpp",
#         "src_dir": "../../dcdc",  # relative to confdir
#         "remote_url_pattern": "https://github.com/useblocks/sphinx-codelinks/blob/{commit}/{path}#L{line}",  # optional
#         "exclude": ["dcdc/src/ubt/ubt.cpp"],
#         "include": ["**/*.cpp", "**/*.hpp"],  # has default for each type
#         "gitignore": True,  # default is True
#         # Proposal for the one-line comment style:
#         # a need object defined in a one-line comment with the customized style.
#         # The example is the following:
#         # [[directive: implement, title: charge, id:impl_charge, link: req_charge]]]]
#         # The equivalent need object in rst is:
#         # .. implement:: implement charge
#         #    :id: impl_charge
#         #    :link: req_charge
#         "oneline_comment_style": {
#             "start": "[[",
#             "end": "]]",
#             "option_separator": ",",
#             "key_value_separator": ":",
#             ## What's the point if the comment has no readability?
#             # "default-need-type": "implements",
#             # "structure": [
#             #     "id",
#             #     "link-type",
#             #     "link-id",
#             #     "title",
#             # ],
#         },
#         "multiline_comment_style": {
#             "line-start-char": "*",
#             "start": "[[[",
#             "end": "]]]",
#         },
#     }
# }
