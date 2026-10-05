# The need_id_refs fixture: @need-ids references attached during the build.
# The tests copy it, make it a git repository, and change it per case.
extensions = ["sphinx_needs", "sphinx_codelinks"]
exclude_patterns = ["_build"]
needs_build_json = True
