from tests.test_services.test_service_basics import NoDebugService, ServiceTest

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


needs_services = {
    "testservice": {
        "class": ServiceTest,
        "class_init": {
            "custom_init": True,
        },
        "custom_option": "custom_option_True",
    },
    "no_debug_service": {
        "class": NoDebugService,
        "class_init": {
            "custom_init": True,
        },
    },
}
