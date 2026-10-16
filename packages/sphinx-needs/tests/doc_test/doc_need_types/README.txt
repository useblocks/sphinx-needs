The docs include these files with literalinclude, cut at the marker comments
(`# [name]` / `# [/name]` in ubproject.toml, `.. name-start` / `.. name-end` in index.rst).
Keep the markers when editing, and keep tests/test_need_types_docs.py in step: it pins the warnings the docs quote.
