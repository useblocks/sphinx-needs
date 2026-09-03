version = "1"
extensions = ["sphinx_needs"]
needs_build_json = True
needs_services = {
    "github-commits": {
        "retry_delay": 0,
    }
}
