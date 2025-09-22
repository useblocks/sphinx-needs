"""
Stores defaults configurations
"""

DEFAULT_OPTIONS = [
    "name",
    "classname",
    "file",
    "line",
    "time",
    "result",
    "type",
    "text",
    "message",
    "system-out",
]

try:
    from sphinx_needs.api.configuration import needs_duration_option, needs_completion_option
except ImportError:
    needs_duration_option = 'duration'
    needs_completion_option = 'completion'
    
testreports_file_option = "file"