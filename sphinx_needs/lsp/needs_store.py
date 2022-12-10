# --------------------------------------------------------------------------
# Licensed under the MIT license.
# See License.txt in the project root for further license information.
# --------------------------------------------------------------------------

from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from sphinx_needs.lsp.exceptions import NeedlsConfigException


@contextmanager
def set_directory(path: Path) -> Generator[None, None, None]:
    origin = Path().cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(origin)


class NeedsStore:
    """Abstraction of needs database."""

    def __init__(self) -> None:
        self.docs_per_type: dict[str, list[str]] = {}  # key: need type, val: list of doc names (str)
        self.needs_per_doc: dict[str | None, list[dict[str | None, Any]]] = {}  # key: docname; val: list of needs
        self.types: list[str] = []  # list of need types actually defined in needs.json
        self.declared_types: dict[str, str] = {}  # types declared in conf.py: {'need directive': 'need title'}
        self.needs: dict[str | None, dict[str | None, Any]] = {}
        self.needs_initialized: bool = False
        self.conf_py_path: Path = Path()

    def is_setup(self) -> bool:
        """Return True if database is ready for use."""

        return self.needs_initialized

    def set_conf_py(self, conf_py: Path) -> None:
        if not conf_py.exists():
            raise FileNotFoundError(f"Given custom configuration file {conf_py} not found.")
        self.conf_py_path = conf_py

    def set_declared_types(self) -> None:
        module_name = "conf"
        conf_py = self.conf_py_path
        with set_directory(conf_py.parent):
            logging.info(f"Loading need_types from {conf_py.name}...")

            spec = importlib.util.spec_from_file_location(module_name, conf_py)
            if spec is None:
                raise ImportError(f"Created module spec {spec} from {conf_py.name} not exists.")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module

            if spec.loader:
                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    logging.error(f"Failed to exccute module {module} -> {e}")
            else:
                raise ImportError(f"Python ModuleSpec Loader{spec.loader} not found.")

            need_types = getattr(module, "needs_types", [])
            if not need_types:
                raise NeedlsConfigException(f"No 'need_types' defined on {conf_py.name}")

            self.declared_types = {}
            for item in need_types:
                self.declared_types[item["directive"]] = item["title"]

    def load_needs(self, json_file: Path) -> None:

        self.docs_per_type = {}
        self.needs_per_doc = {}
        self.types = []
        self.needs = {}

        with open(json_file, encoding="utf-8") as file:
            needs_json = json.load(file)

        versions = needs_json["versions"]
        # get the latest version
        version = versions[sorted(versions)[-1]]

        self.needs = version["needs"]

        for need in self.needs.values():
            need_type = need["type"]
            docname = need["docname"] + need["doctype"]

            if need_type not in self.docs_per_type:
                self.types.append(need_type)
                self.docs_per_type[need_type] = []

            if docname not in self.docs_per_type[need_type]:
                self.docs_per_type[need_type].append(docname)

            if docname not in self.needs_per_doc:
                self.needs_per_doc[docname] = []
            self.needs_per_doc[docname].append(need)

        self.needs_initialized = True
