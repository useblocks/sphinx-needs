import os

extensions = ["sphinx_needs"]

needs_types = [
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "R_",
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
        "directive": "task",
        "title": "Task",
        "prefix": "T_",
        "color": "#DCB239",
        "style": "node",
    },
]

needs_services = {
    "open-needs": {
        "url": "http://127.0.0.1:9595",
        "user": os.environ.get("ONS_USERNAME", ""),
        "password": os.environ.get("ONS_PASSWORD", ""),
        "id_prefix": "ONS_TEST_",
        "mappings": {
            "id": "{{key}}",
            "type": ["type"],
            "title": "{{title}}",
            "status": ["options", "status"],
            "links": ["references", "links"],
        },
        "extra_data": {
            "Priority": ["options", "priority"],
            "Approval": ["options", "approved"],
            "Cost": ["options", "costs"],
        },
    },
}
