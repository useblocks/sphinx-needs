"""The ``test-reports build needs`` CLI's output, inside Sphinx (TR-A).

This is the half that needs Sphinx: the converter's output checked against sphinx-needs'
schema and imported into a build. The converter's own tests are ub-test-reports',
``packages/ub-test-reports/tests/test_cli_convert.py``.
"""

import json
from pathlib import Path

import pytest

UTILS = Path(__file__).parent / "doc_test" / "utils"
GTEST_XML = UTILS / "gtest_data.xml"


def _convert(tmp_path, *args, xml=GTEST_XML):
    """Run the converter and return (exit_code, parsed output or None)."""
    from ub_test_reports.cli import main

    output = tmp_path / "needs.json"
    code = main(["build", "needs", str(xml), "--output", str(output), *args])
    data = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    return code, data


def _needs(data):
    version = data["current_version"]
    return data["versions"][version]["needs"]


def _field_type(declaration):
    """The declared type, with the nullability the schema spells separately."""
    kind = declaration["type"]
    if isinstance(kind, str):
        return kind
    return next(iter(set(kind) - {"null"}))


class TestEnvelope:
    def test_output_passes_the_sphinx_needs_schema(self, tmp_path):
        """The output must validate against sphinx-needs' own needs.json schema."""
        from sphinx_needs import needsfile

        code, data = _convert(tmp_path)

        assert code == 0
        assert needsfile.check_needs_data(data).schema == []


class TestImportIntoABuild:
    """The documented consumption path: ``needimport`` of the produced file.

    The converter writes needs shaped like the build's own test-case needs, so
    a build with the extension has to import them without dropping fields.
    """

    def test_converted_needs_import_without_loss(self, tmp_path):
        from io import StringIO
        from shutil import copytree

        from sphinx.application import Sphinx

        docs = tmp_path / "docs"
        copytree(Path(__file__).parent / "doc_test" / "basic_doc", docs)
        (tmp_path / ".git").mkdir(exist_ok=True)  # bounds the upward search
        with (docs / "conf.py").open("a", encoding="utf-8") as handle:
            # The IDs are lowercase; sphinx-needs' default regex is not.
            handle.write('\nneeds_id_regex = "^[A-Za-z0-9_]{5,}"\n')
        (docs / "index.rst").write_text(
            "Imported\n========\n\n.. needimport:: needs.json\n", encoding="utf-8"
        )
        # One declarative file for both consumers: the build registers these
        # properties as need options, the converter exports exactly these.
        config = docs / "ubproject.toml"
        config.write_text(
            '[test_reports]\nextra_options = ["TestType", "Requirement", "PartiallyVerifies"]\n',
            encoding="utf-8",
        )
        code, data = _convert(docs, "--config", str(config), xml=GTEST_XML)
        assert code == 0

        warnings = StringIO()
        app = Sphinx(
            srcdir=docs,
            confdir=docs,
            outdir=docs / "_build" / "html",
            doctreedir=docs / "_build" / "doctrees",
            buildername="html",
            freshenv=True,
            status=None,
            warning=warnings,
        )
        app.build()
        text = warnings.getvalue()
        assert "Unknown keys" not in text, text
        assert "could not be imported" not in text, text
        html = (docs / "_build" / "html" / "index.html").read_text(encoding="utf-8")
        for need_id in _needs(data):
            assert need_id in html

    def test_the_declared_types_match_the_extension_s(self, tmp_path):
        """What the file declares is what the build registers.

        The extension declares its fields to sphinx-needs, the converter
        declares them into the file, and an import brings the two together --
        so a field the two type differently is an import-time type error
        waiting to happen. Only the type is compared: the wording of a core
        field's description belongs to sphinx-needs and moves with its
        version.
        """
        from shutil import copytree

        from sphinx.application import Sphinx

        docs = tmp_path / "docs"
        copytree(Path(__file__).parent / "doc_test" / "basic_doc", docs)
        (tmp_path / ".git").mkdir(exist_ok=True)  # bounds the upward search
        with (docs / "conf.py").open("a", encoding="utf-8") as handle:
            # The build has to write a needs.json of its own to compare with.
            handle.write("\nneeds_build_json = True\n")
            handle.write('needs_id_regex = "^[A-Za-z0-9_]{5,}"\n')
        (docs / "index.rst").write_text(
            "Imported\n========\n\n.. needimport:: needs.json\n", encoding="utf-8"
        )
        config = docs / "ubproject.toml"
        config.write_text(
            '[test_reports]\nextra_options = ["TestType"]\n', encoding="utf-8"
        )
        code, data = _convert(docs, "--config", str(config), xml=GTEST_XML)
        assert code == 0

        app = Sphinx(
            srcdir=docs,
            confdir=docs,
            outdir=docs / "_build" / "html",
            doctreedir=docs / "_build" / "doctrees",
            buildername="html",
            freshenv=True,
            status=None,
            warning=None,
        )
        app.build()
        built = json.loads(
            (docs / "_build" / "html" / "needs.json").read_text(encoding="utf-8")
        )
        registered = built["versions"][built["current_version"]].get("needs_schema")
        if registered is None:
            pytest.skip("this sphinx-needs does not declare its fields in needs.json")

        declared = data["versions"][data["current_version"]]["needs_schema"]
        shared = set(declared["properties"]) & set(registered["properties"])
        # Guard against a vacuous comparison: these are the fields the
        # converter writes beyond the core ones.
        assert {
            "case",
            "case_file",
            "case_line",
            "case_name",
            "case_parameter",
            "classname",
            "file",
            "remote_url",
            "result",
            "result_text",
            "suite",
            "time",
            "TestType",
        } <= shared

        assert {name: _field_type(declared["properties"][name]) for name in shared} == {
            name: _field_type(registered["properties"][name]) for name in shared
        }
