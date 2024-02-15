from __future__ import annotations

EXTRA_DATA_OPTIONS = ["user", "created_at", "updated_at", "closed_at", "service"]
EXTRA_LINK_OPTIONS = ["url"]
EXTRA_IMAGE_OPTIONS = ["avatar"]
CONFIG_OPTIONS = [
    "type",
    "query",
    "specific",
    "max_amount",
    "max_content_lines",
    "id_prefix",
]
GITHUB_DATA = (
    ["status", "tags"] + EXTRA_DATA_OPTIONS + EXTRA_LINK_OPTIONS + EXTRA_IMAGE_OPTIONS
)
GITHUB_DATA_STR = (
    '"'
    + '","'.join(EXTRA_DATA_OPTIONS + EXTRA_LINK_OPTIONS + EXTRA_IMAGE_OPTIONS)
    + '"'
)
CONFIG_DATA_STR = '"' + '","'.join(CONFIG_OPTIONS) + '"'
GITHUB_LAYOUT = {
    "grid": "complex",
    "layout": {
        "head_left": [
            "<<meta_id()>>",
            '<<collapse_button("meta,footer", collapsed="icon:arrow-down-circle", '
            'visible="icon:arrow-right-circle", initial=True)>>',
        ],
        "head": [
            '**<<meta("title")>>** ('
            + ", ".join(
                [
                    f'<<link("{x}", text="{x}", is_dynamic=True)>>'
                    for x in EXTRA_LINK_OPTIONS
                ]
            )
            + ")"
        ],
        "head_right": [
            '<<image("field:avatar", width="40px", align="middle")>>',
            '<<meta("user")>>',
        ],
        "meta_left": [f'<<meta("{x}", prefix="{x}: ")>>' for x in EXTRA_DATA_OPTIONS]
        + [
            f'<<link("{x}", text="Link", prefix="{x}: ", is_dynamic=True)>>'
            for x in EXTRA_LINK_OPTIONS
        ],
        "meta_right": [
            '<<meta("type_name", prefix="type: ")>>',
            f'<<meta_all(no_links=True, exclude=["layout","style",{GITHUB_DATA_STR}, {CONFIG_DATA_STR}])>>',
            "<<meta_links_all()>>",
        ],
        "footer_left": [
            'layout: <<meta("layout")>>',
        ],
        "footer": [
            'service:  <<meta("service")>>',
        ],
        "footer_right": ['style: <<meta("style")>>'],
    },
}
