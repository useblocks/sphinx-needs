from __future__ import annotations

EXTRA_DATA_OPTIONS = ["params", "prefix"]
EXTRA_LINK_OPTIONS = ["url", "url_postfix"]
CONFIG_OPTIONS = ["query", "max_content_lines", "id_prefix"]
DEFAULT_CONTENT = """
{% set desc_list = data.description.split('\n') %}
.. raw:: html
   {% for line in desc_list %}
   {{line}}
   {%- endfor %}
"""
MAPPINGS_REPLACES_DEFAULT = {
    r"^Requirement$": "req",
    r"^Specification$": "spec",
    r"\\\\\\\\\\r\\n": "\n\n",
}
