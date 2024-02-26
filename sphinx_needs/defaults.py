from __future__ import annotations

import os
from typing import Any

from docutils.parsers.rst import directives

DEFAULT_DIAGRAM_TEMPLATE = """
{%- if is_need -%}
<size:12>{{type_name}}</size>\\n**{{title|wordwrap(15, wrapstring='**\\\\n**')}}**\\n<size:10>{{id}}</size>
{%- else -%}
<size:12>{{type_name}} (part)</size>\\n**{{content|wordwrap(15, wrapstring='**\\\\n**')}}**\\n<size:10>{{id_parent}}.**{{id}}**</size>
{%- endif -%}
"""

LAYOUT_COMMON_SIDE = {
    "side": ['<<image("field:image", align="center")>>'],
    "head": ['<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>>'],
    "meta": ["<<meta_all(no_links=True)>>", "<<meta_links_all()>>"],
}

LAYOUTS = {
    "test": {
        "grid": "simple",
        "layout": {
            "head": [
                '<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>>  <<collapse_button("meta", '
                'collapsed="icon:arrow-down-circle", visible="icon:arrow-right-circle", initial=False)>> '
            ],
            "meta": ["<<meta_all(no_links=True)>>", "<<meta_links_all()>>"],
        },
    },
    "clean": {
        "grid": "simple",
        "layout": {
            "head": [
                '<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>>  <<collapse_button("meta", '
                'collapsed="icon:arrow-down-circle", visible="icon:arrow-right-circle", initial=False)>> '
            ],
            "meta": ["<<meta_all(no_links=True)>>", "<<meta_links_all()>>"],
        },
    },
    "clean_l": {"grid": "simple_side_left", "layout": LAYOUT_COMMON_SIDE},
    "clean_lp": {"grid": "simple_side_left_partial", "layout": LAYOUT_COMMON_SIDE},
    "clean_r": {"grid": "simple_side_right", "layout": LAYOUT_COMMON_SIDE},
    "clean_rp": {"grid": "simple_side_right_partial", "layout": LAYOUT_COMMON_SIDE},
    "complete": {
        "grid": "complex",
        "layout": {
            "head_left": [
                "<<meta_id()>>",
            ],
            "head": [
                '<<meta("title")>>',
            ],
            "head_right": ['<<meta("type_name")>>'],
            "meta_left": ['<<meta_all(no_links=True, exclude=["layout","style"])>>'],
            "meta_right": ["<<meta_links_all()>>"],
            "footer_left": [
                'layout: <<meta("layout")>>',
            ],
            "footer": [],
            "footer_right": ['style: <<meta("style")>>'],
        },
    },
    "focus": {"grid": "content", "layout": {}},
    "focus_f": {"grid": "content_footer", "layout": {"footer": ["<<meta_id()>>"]}},
    "focus_l": {"grid": "content_side_left", "layout": {"side": ["<<meta_id()>>"]}},
    "focus_r": {"grid": "content_side_right", "layout": {"side": ["<<meta_id()>>"]}},
    "debug": {
        "grid": "simple",
        "layout": {
            "head": [
                '<<meta_id()>> **<<meta("title")>>**',
                '**<<collapse_button("meta", collapsed="Debug view on", visible="Debug view off", initial=True)>>**',
            ],
            "meta": ["<<meta_all(exclude=[], defaults=False, show_empty=True)>>"],
        },
    },
}

NEEDFLOW_CONFIG_DEFAULTS = {
    "mixing": """
        allowmixing
    """,
    "monochrome": """
        skinparam monochrome true
    """,
    "handwritten": """
        skinparam handwritten true
    """,
    "lefttoright": """
        left to right direction
    """,
    "toptobottom": """
        top to bottom direction
    """,
    "transparent": """
    skinparam backgroundcolor transparent
    """,
    "tne": """
    ' Based on "Tomorrow night eighties" color theme (see https://github.com/chriskempson/tomorrow-theme)
    ' Provided by gabrieljoelc (https://github.com/gabrieljoelc/plantuml-themes)
    !define Background   #2d2d2d
    !define CurrentLine  #393939
    !define Selection    #515151
    !define Foregound    #cccccc
    !define Comment      #999999
    !define Red          #f2777a
    !define Orange       #f99157
    !define Yellow       #ffcc66
    !define Green        #99cc99
    !define Aqua         #66cccc
    !define Blue         #6699cc
    !define Purple       #cc99cc

    skinparam Shadowing false
    skinparam backgroundColor #2d2d2d
    skinparam Arrow {
      Color Foregound
      FontColor Foregound
      FontStyle Bold
    }
    skinparam Default {
      FontName Menlo
      FontColor #fdfdfd
    }
    skinparam package {
      FontColor Purple
      BackgroundColor CurrentLine
      BorderColor Selection
    }
    skinparam node {
      FontColor Yellow
      BackgroundColor CurrentLine
      BorderColor Selection
    }
    skinparam component {
      BackgroundColor Selection
      BorderColor Blue
      FontColor Blue
      Style uml2
    }
    skinparam database {
      BackgroundColor CurrentLine
      BorderColor Selection
      FontColor Orange
    }

    skinparam cloud {
      BackgroundColor CurrentLine
      BorderColor Selection
    }

    skinparam interface {
      BackgroundColor CurrentLine
      BorderColor Selection
      FontColor Green
    }
    """,
    "cplant": """
    ' CPLANT by AOKI (https://github.com/aoki/cplant)
    !define BLACK   #363D5D
    !define RED     #F6363F
    !define PINK    #F6216E
    !define MAGENTA #A54FBD
    !define GREEN   #37A77C
    !define YELLOW  #F97A00
    !define BLUE    #1E98F2
    !define CYAN    #25AFCA
    !define WHITE   #FEF2DC

    ' Base Setting
    skinparam Shadowing false
    skinparam BackgroundColor transparent
    skinparam ComponentStyle uml2
    skinparam Default {
      FontName  'Hiragino Sans'
      FontColor BLACK
      FontSize  10
      FontStyle plain
    }

    skinparam Sequence {
      ArrowThickness 1
      ArrowColor RED
      ActorBorderThickness 1
      LifeLineBorderColor GREEN
      ParticipantBorderThickness 0
    }
    skinparam Participant {
      BackgroundColor BLACK
      BorderColor BLACK
      FontColor #FFFFFF
    }

    skinparam Actor {
      BackgroundColor BLACK
      BorderColor BLACK
    }
    """,
}

TITLE_REGEX = r'([^\s]+) as "([^"]+)"'


NEED_DEFAULT_OPTIONS: dict[str, Any] = {
    "id": directives.unchanged_required,
    "status": directives.unchanged_required,
    "tags": directives.unchanged_required,
    "links": directives.unchanged_required,
    "collapse": directives.unchanged_required,
    "delete": directives.unchanged,
    "jinja_content": directives.unchanged,
    "hide": directives.flag,
    "title_from_content": directives.flag,
    "style": directives.unchanged_required,
    "layout": directives.unchanged_required,
    "template": directives.unchanged_required,
    "pre_template": directives.unchanged_required,
    "post_template": directives.unchanged_required,
    "constraints": directives.unchanged_required,
    "constraints_passed": directives.unchanged_required,
    "constraints_results": directives.unchanged_required,
}

NEEDEXTEND_NOT_ALLOWED_OPTIONS = ["id"]

NEEDS_PROFILING = [x.upper() for x in os.environ.get("NEEDS_PROFILING", "").split(",")]

NEEDS_TABLES_CLASSES = ["rtd-exclude-wy-table", "no-sphinx-material-strip"]
