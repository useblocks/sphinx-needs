# --------------------------------------------------------------------------
# Licensed under the MIT license.
# See License.txt in the project root for further license information.
# --------------------------------------------------------------------------

import importlib.util
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from sphinx_needs.lsp.exceptions import NeedlsConfigException


class NeedsStore:
    """Abstraction of needs database."""

    def __init__(self) -> None:
        self.docs_per_type: Dict[str, List[str]] = {}  # key: need type, val: list of doc names (str)
        self.needs_per_doc: Dict[Optional[str], List[Dict[Optional[str], Any]]] = {}  # key: docname; val: list of needs
        self.types: List[str] = []  # list of need types actually defined in needs.json
        self.declared_types: Dict[str, str] = {}  # types declared in conf.py: {'need directive': 'need title'}
        self.needs: Dict[Optional[str], Dict[Optional[str], Any]] = {}
        self.needs_initialized: bool = False
        self.conf_py_path: str = ""

    def is_setup(self) -> bool:
        """Return True if database is ready for use."""

        if not self.needs_initialized:
            return False

        return True

    def set_conf_py(self, conf_py_path: str) -> None:
        if not os.path.exists(conf_py_path):
            raise FileNotFoundError(f"Given custom configuration file {conf_py_path} not found.")
        self.conf_py_path = conf_py_path

    def set_declared_types(self) -> None:
        module_name = "conf"
        work_dir = os.getcwd()
        conf_py_path = self.conf_py_path
        conf_py_dir = os.path.dirname(conf_py_path)
        conf_py_name = os.path.basename(conf_py_path)
        os.chdir(conf_py_dir)

        logging.info(f"Loading need_types from {conf_py_name}...")

        spec = importlib.util.spec_from_file_location(module_name, conf_py_path)
        if spec is None:
            raise ImportError(f"Created module spec {spec} from {conf_py_name} not exists.")

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
            raise NeedlsConfigException(f"No 'need_types' defined on {conf_py_name}")

        self.declared_types = {}
        for item in need_types:
            self.declared_types[item["directive"]] = item["title"]
        os.chdir(work_dir)

    def load_needs(self, json_file: str) -> None:

        self.docs_per_type = {}
        self.needs_per_doc = {}
        self.types = []
        self.needs = {}

        if not os.path.exists(json_file):
            raise FileNotFoundError(f"JSON file not found: {json_file}")

        with open(json_file, encoding="utf-8") as file:
            needs_json = json.load(file)

        versions = needs_json["versions"]
        # get the latest version
        version = versions[sorted(versions)[-1]]

        self.needs = version["needs"]

        for need in self.needs.values():
            need_type = need["type"]
            docname = need["docname"] + ".rst"

            if need_type not in self.docs_per_type:
                self.types.append(need_type)
                self.docs_per_type[need_type] = []

            if docname not in self.docs_per_type[need_type]:
                self.docs_per_type[need_type].append(docname)

            if docname not in self.needs_per_doc:
                self.needs_per_doc[docname] = []
            self.needs_per_doc[docname].append(need)

        self.needs_initialized = True
