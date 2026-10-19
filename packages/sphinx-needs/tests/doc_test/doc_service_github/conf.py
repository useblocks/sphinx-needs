version = "1"
extensions = ["sphinx_needs"]
needs_build_json = True
# the built-in services are registered only when configured: index.rst uses all three
needs_services = {
    "github-issues": {},
    "github-prs": {},
    "github-commits": {
        "retry_delay": 0,
    },
}
