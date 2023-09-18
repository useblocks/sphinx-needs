import os
from typing import Iterable, List, Optional, Set

from docutils import nodes
from sphinx import version_info
from sphinx.application import Sphinx
from sphinx.builders import Builder

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsInfoType, SphinxNeedsData
from sphinx_needs.logging import get_logger
from sphinx_needs.needsfile import NeedsList

log = get_logger(__name__)


class NeedsBuilder(Builder):
    name = "needs"
    format = "needs"
    file_suffix = ".txt"
    links_suffix = None

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        pass

    def finish(self) -> None:
        env = self.env
        data = SphinxNeedsData(env)
        filters = data.get_or_create_filters()
        version = getattr(env.config, "version", "unset")
        needs_list = NeedsList(env.config, self.outdir, self.srcdir)
        needs_config = NeedsSphinxConfig(env.config)

        if needs_config.file:
            needs_file = needs_config.file
            needs_list.load_json(needs_file)
        else:
            # check if needs.json file exists in conf.py directory
            needs_json = os.path.join(self.srcdir, "needs.json")
            if os.path.exists(needs_json):
                log.info("needs.json found, but will not be used because needs_file not configured.")

        # Clean needs_list from already stored needs of the current version.
        # This is needed as needs could have been removed from documentation and if this is the case,
        # removed needs would stay in needs_list, if list gets not cleaned.
        needs_list.wipe_version(version)
        #
        from sphinx_needs.filter_common import filter_needs

        filter_string = needs_config.builder_filter
        filtered_needs: List[NeedsInfoType] = filter_needs(self.app, data.get_or_create_needs().values(), filter_string)

        for need in filtered_needs:
            needs_list.add_need(version, need)

        for need_filter in filters.values():
            if need_filter["export_id"]:
                needs_list.add_filter(version, need_filter)

        try:
            needs_list.write_json()
        except Exception as e:
            log.error(f"Error during writing json file: {e}")
        else:
            log.info("Needs successfully exported")

    def get_outdated_docs(self) -> Iterable[str]:
        return []

    def prepare_writing(self, _docnames: Set[str]) -> None:
        pass

    def write_doc_serialized(self, _docname: str, _doctree: nodes.document) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def get_target_uri(self, _docname: str, _typ: Optional[str] = None) -> str:
        return ""


def build_needs_json(app: Sphinx, _exception: Exception) -> None:
    env = app.env

    if not NeedsSphinxConfig(env.config).build_json:
        return

    # Do not create an additional needs.json, if builder is already "needs".
    if isinstance(app.builder, NeedsBuilder):
        return

    try:
        needs_builder = NeedsBuilder(app, env)
    except TypeError:
        needs_builder = NeedsBuilder(app)
        needs_builder.set_environment(env)

    needs_builder.finish()


class NeedumlsBuilder(Builder):
    name = "needumls"

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        pass

    def finish(self) -> None:
        env = self.env
        needumls = SphinxNeedsData(env).get_or_create_umls().values()

        for needuml in needumls:
            if needuml["save"]:
                puml_content = needuml["content_calculated"]
                # check if given save path dir exists
                save_path = os.path.join(self.outdir, needuml["save"])
                save_dir = os.path.dirname(save_path)
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir, exist_ok=True)

                log.info(f"Storing needuml data to file {save_path}.")
                with open(save_path, "w") as f:
                    f.write(puml_content)

    def get_outdated_docs(self) -> Iterable[str]:
        return []

    def prepare_writing(self, _docnames: Set[str]) -> None:
        pass

    def write_doc_serialized(self, _docname: str, _doctree: nodes.document) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def get_target_uri(self, _docname: str, _typ: Optional[str] = None) -> str:
        return ""


def build_needumls_pumls(app: Sphinx, _exception: Exception) -> None:
    env = app.env
    config = NeedsSphinxConfig(env.config)

    if not config.build_needumls:
        return

    # Do not create additional files for saved plantuml content, if builder is already "needumls".
    if isinstance(app.builder, NeedumlsBuilder):
        return

    # if other builder like html used together with config: needs_build_needumls
    if version_info[0] >= 5:
        needs_builder = NeedumlsBuilder(app, env)
        needs_builder.outdir = os.path.join(needs_builder.outdir, config.build_needumls)
    else:
        needs_builder = NeedumlsBuilder(app)
        needs_builder.outdir = os.path.join(needs_builder.outdir, config.build_needumls)
        needs_builder.set_environment(env)

    needs_builder.finish()


class NeedsIdBuilder(Builder):
    """Json builder for needs, which creates separate json-files per need"""

    name = "needs_id"
    format = "needs"
    file_suffix = ".txt"
    links_suffix = None

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        pass

    def finish(self) -> None:
        env = self.env
        data = SphinxNeedsData(env)
        needs = data.get_or_create_needs().values()  # We need a list of needs for later filter checks
        version = getattr(env.config, "version", "unset")
        needs_config = NeedsSphinxConfig(env.config)
        filter_string = needs_config.builder_filter
        from sphinx_needs.filter_common import filter_needs

        filtered_needs = filter_needs(self.app, needs, filter_string)
        needs_build_json_per_id_path = needs_config.build_json_per_id_path
        needs_dir = os.path.join(self.outdir, needs_build_json_per_id_path)
        if not os.path.exists(needs_dir):
            os.makedirs(needs_dir, exist_ok=True)
        for need in filtered_needs:
            needs_list = NeedsList(env.config, self.outdir, self.srcdir)
            needs_list.wipe_version(version)
            needs_list.add_need(version, need)
            id = need["id"]
            try:
                file_name = f"{id}.json"
                needs_list.write_json(file_name, needs_dir)
            except Exception as e:
                log.error(f"Needs-ID Builder {id} error: {e}")
        log.info("Needs_id successfully exported")

    def get_outdated_docs(self) -> Iterable[str]:
        return []

    def prepare_writing(self, _docnames: Set[str]) -> None:
        pass

    def write_doc_serialized(self, _docname: str, _doctree: nodes.document) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def get_target_uri(self, _docname: str, _typ: Optional[str] = None) -> str:
        return ""


def build_needs_id_json(app: Sphinx, _exception: Exception) -> None:
    env = app.env

    if not NeedsSphinxConfig(env.config).build_json_per_id:
        return

    # Do not create an additional needs_json for every needs_id, if builder is already "needs_id".
    if isinstance(app.builder, NeedsIdBuilder):
        return
    try:
        needs_id_builder = NeedsIdBuilder(app, env)
    except TypeError:
        needs_id_builder = NeedsIdBuilder(app)
        needs_id_builder.set_environment(env)

    needs_id_builder.finish()


class NeedsLookUpTableBuilder(Builder):
    """
    JSON builder for needs, which creates a simple JSON file including only all keys is need' id and the value is doc name or external_url
    """

    name = "needs_lut"
    format = "needs"
    file_suffix = ".txt"
    links_suffix = None

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        pass

    def finish(self) -> None:
        env = self.env
        data = SphinxNeedsData(env)
        needs_dict = {}
        needs_config = NeedsSphinxConfig(env.config)
        filter_string = needs_config.builder_filter
        from sphinx_needs.filter_common import filter_needs

        version = getattr(env.config, "version", "unset")
        needs_list = NeedsList(env.config, self.outdir, self.srcdir)
        needs_list.wipe_version(version)
        filtered_needs: List[NeedsInfoType] = filter_needs(self.app, data.get_or_create_needs().values(), filter_string)
        for need in filtered_needs:
            if need["is_external"]:
                needs_dict = {"id": need["id"], "docname": need["external_url"], "content": need["content"]}

            else:
                needs_dict = {"id": need["id"], "docname": need["docname"], "content": need["content"]}
                need["docname"] = need["external_url"]

            needs_list.add_need(version, needs_dict)
        try:
            needs_list.write_json("needs_lut.json")
        except Exception as e:
            log.error(f"Error during writing json file: {e}")
        else:
            log.info("Needs lookup table json successfully created")

    def get_outdated_docs(self) -> Iterable[str]:
        return []

    def prepare_writing(self, _docnames: Set[str]) -> None:
        pass

    def write_doc_serialized(self, _docname: str, _doctree: nodes.document) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def get_target_uri(self, _docname: str, _typ: Optional[str] = None) -> str:
        return ""


def build_needs_look_up_json(app: Sphinx, _exception: Exception) -> None:
    env = app.env

    if not NeedsSphinxConfig(env.config).build_lut_json:
        return

    # Do not create an additional look up table json, if builder is already in use.
    if isinstance(app.builder, NeedsLookUpTableBuilder):
        return

    try:
        needs_lut_builder = NeedsLookUpTableBuilder(app, env)
    except TypeError:
        needs_lut_builder = NeedsLookUpTableBuilder(app)
        needs_lut_builder.set_environment(env)

    needs_lut_builder.finish()
