import json
import os
from typing import Any

from docutils import nodes
from docutils.parsers.rst import Directive, directives

from sphinx_test_reports.directives.test_common import error_node, new_section, warn

#: JSON's names for the types ``json.load`` returns, for a message about the file.
_JSON_KINDS = {
    list: "an array",
    str: "a string",
    int: "a number",
    float: "a number",
    bool: "a boolean",
    type(None): "null",
}


def _json_kind(value: Any) -> str:
    """What ``value`` is, in JSON's words: ``an array``, ``a string``, ``null``, ..."""
    return _JSON_KINDS.get(type(value), type(value).__name__)


def _comma_list(value: str | None) -> list[str] | None:
    """An ``:env:`` / ``:data:`` value as its elements: split on commas, each stripped,
    an element empty after stripping dropped, a repeated element kept once (at its first
    position). ``None`` when the option is not given."""
    if value is None:
        return None
    return list(dict.fromkeys(e.strip() for e in value.split(",") if e.strip()))


class EnvReport(nodes.General, nodes.Element):
    pass


class EnvReportDirective(Directive):
    """
    Directive for showing test results.
    """

    has_content = True
    required_arguments = 1
    optional_arguments = 0
    option_spec = {
        "env": directives.unchanged_required,
        "data": directives.unchanged_required,
        "raw": directives.flag,
    }

    final_argument_whitespace = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #: The environments ``:env:`` names, or ``None``: every environment, in file order.
        #: A value naming none (``:env: ,``) shows none.
        self.req_env_list = _comma_list(self.options.get("env"))
        #: The variables ``:data:`` names, or ``None``: every variable. A value naming none
        #: (``:data: ,``) is the same as no ``:data:``.
        self.data_option_list = _comma_list(self.options.get("data")) or None

        self.header = ("Variable", "Data")
        self.colwidths = (1, 1)

    def run(self):
        env = self.state.document.settings.env

        json_path = self.arguments[0]
        root_path = env.app.config.tr_rootdir
        if not os.path.isabs(json_path):
            json_path = os.path.join(root_path, json_path)

        # Every refusal is a located `test_reports.*` warning; one that leaves nothing to
        # show is an error box in place of the sections too, and the build goes on.
        if not os.path.exists(json_path):
            return self._refuse("report_missing", f"Test file not found: {json_path}")
        try:
            # UTF-8, with or without a byte-order mark, whatever the locale.
            with open(json_path, encoding="utf-8-sig") as fp_json:
                results = json.load(fp_json)
        except UnicodeDecodeError as exc:
            return self._refuse(
                "report_unreadable",
                f"{json_path} is not valid UTF-8 ({exc.reason} at byte {exc.start})",
            )
        except json.JSONDecodeError as exc:
            return self._refuse(
                "report_unreadable",
                f"{json_path} (line {exc.lineno}, column {exc.colno}): {exc.msg}",
            )
        if not isinstance(results, dict):
            return self._refuse(
                "env_shape",
                f"{json_path}: the file is not a JSON object of environments "
                f"(got {_json_kind(results)})",
            )

        # The environments to show: `:env:`'s, in its order, or every one in file order.
        if self.req_env_list is None:
            selected = list(results)
        else:
            selected = []
            for name in self.req_env_list:
                if name in results:
                    selected.append(name)
                else:
                    warn(
                        self,
                        "env_not_present",
                        f"environment '{name}' is not present in JSON file",
                    )

        # An environment that is not an object is skipped, in every branch.
        shown: list[tuple[str, dict[str, Any]]] = []
        for name in selected:
            variables = results[name]
            if isinstance(variables, dict):
                shown.append((name, variables))
            else:
                warn(
                    self,
                    "env_shape",
                    f"environment '{name}' is not a JSON object "
                    f"(got {_json_kind(variables)}); skipped",
                )

        # Construction idea taken from http://agateau.com/2015/docutils-snippets/
        main_section = []
        for name, variables in shown:
            # The variables `:data:` names, in file order; every one without `:data:`.
            if self.data_option_list is not None:
                variables = {
                    key: value
                    for key, value in variables.items()
                    if key in self.data_option_list
                }
            if "raw" in self.options:
                main_section.append(self._raw_section(name, variables))
            else:
                main_section.append(self._table_section(name, variables))

        # One warning per `:data:` key per directive, naming the shown environments that
        # lack it -- unless none holds it.
        if self.data_option_list is not None:
            for key in self.data_option_list:
                lacking = [name for name, variables in shown if key not in variables]
                if not lacking:
                    continue
                if len(lacking) == len(shown):
                    message = f"option '{key}' is not present in JSON file"
                else:
                    message = (
                        f"option '{key}' is not present in "
                        f"'{', '.join(lacking)}' environment file"
                    )
                warn(self, "env_key_not_present", message)

        return main_section

    def _refuse(self, subtype: str, message: str) -> list[nodes.Node]:
        warn(self, subtype, message)
        return [error_node(message)]

    def _raw_section(self, enviro: str, variables: dict[str, Any]) -> nodes.section:
        section = new_section(self.state, enviro)
        results_string = json.dumps(variables, indent=4)
        code_block = nodes.literal_block(results_string, results_string)
        code_block["language"] = "json"
        section += code_block
        return section

    def _table_section(self, enviro: str, variables: dict[str, Any]) -> nodes.section:
        section = new_section(self.state, enviro)

        table = nodes.table()
        section += table

        tgroup = nodes.tgroup(cols=len(self.header))
        table += tgroup
        for colwidth in self.colwidths:
            tgroup += nodes.colspec(colwidth=colwidth)

        thead = nodes.thead()
        tgroup += thead
        thead += self._create_rows(self.header)

        tbody = nodes.tbody()
        tgroup += tbody
        for key, value in variables.items():
            tbody += self._create_rows((key, value))

        return section

    def _create_rows(self, row_cells):
        row = nodes.row()
        for cell in row_cells:
            entry = nodes.entry()
            row += entry
            if isinstance(cell, (list, dict)):
                results_string = json.dumps(cell, indent=4)
                code_block = nodes.literal_block(results_string, results_string)
                code_block["language"] = "json"
                entry += code_block
            else:
                # A string verbatim (an empty one is an empty cell: it IS the file's
                # value); any other scalar spelled as JSON -- `true`, `false`, `null`, `0`
                # -- not as Python (`True`), and never dropped for being falsy.
                text = cell if isinstance(cell, str) else json.dumps(cell)
                entry += nodes.paragraph(text=text)
        return row


class InvalidJsonFile(Exception):
    """Not raised by the directive since 3.0 (an unreadable file is a warning); kept for
    ``except`` clauses."""


class JsonFileNotFound(Exception):
    """Not raised by the directive since 3.0 (a missing file is a warning); kept for
    ``except`` clauses."""


class InvalidEnvRequested(Exception):
    """Never raised by the directive; kept for ``except`` clauses."""
