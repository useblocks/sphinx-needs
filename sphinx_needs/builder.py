import os
from typing import Iterable, Optional, Set

from docutils import nodes
from sphinx import version_info
from sphinx.application import Sphinx
from sphinx.builders import Builder

from sphinx_needs.logging import get_logger
from sphinx_needs.needsfile import NeedsList
from sphinx_needs.utils import unwrap
import json

log = get_logger(__name__)


class NeedsBuilder(Builder):
    name = "needs"
    format = "json"
    file_suffix = ".txt"
    links_suffix = None

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        pass

    def finish(self) -> None:
        env = unwrap(self.env)
        needs = env.needs_all_needs.values()  # We need a list of needs for later filter checks
        filters = env.needs_all_filters
        config = env.config
        version = getattr(config, "version", "unset")
        needs_list = NeedsList(config, self.outdir, self.srcdir)

        if config.needs_file:
            needs_file = config.needs_file
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

        filter_string = self.app.config.needs_builder_filter
        filtered_needs = filter_needs(self.app, needs, filter_string)

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

    env = unwrap(app.env)

    if not env.config.needs_build_json:
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
        env = unwrap(self.env)
        needumls = env.needs_all_needumls.values()

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
    env = unwrap(app.env)

    if not env.config.needs_build_needumls:
        return

    # Do not create additional files for saved plantuml content, if builder is already "needumls".
    if isinstance(app.builder, NeedumlsBuilder):
        return

    # if other builder like html used together with config: needs_build_needumls
    if version_info[0] >= 5:
        needs_builder = NeedumlsBuilder(app, env)
        needs_builder.outdir = os.path.join(needs_builder.outdir, env.config.needs_build_needumls)
    else:
        needs_builder = NeedumlsBuilder(app)
        needs_builder.outdir = os.path.join(needs_builder.outdir, env.config.needs_build_needumls)
        needs_builder.set_environment(env)

    needs_builder.finish()

    
class NeedsPerPageBuilder(Builder):
    name = "needs_per_page"
    format = "json"
    file_suffix = ".txt"
    links_suffix = None
    LIST_KEY_EXCLUSIONS_NEEDS = ["content_node"]
    
    # LIST_KEY_DOCS_NAME = ["directives", "layout_styles", "dynamic_functions", "index", "services"]
    
    """
        1. Check Docs_name: is_has_slash
        2. If is_has_slash : split slash to (1) and (2) -> (1) create sub directorie -> (2) create file json and collect all needs the same docs name
        3. If not is_has_slash: collect date all needs has same docs mame -> create json file has name is docs name
    """
    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        pass

    def finish(self) -> None:
        env = unwrap(self.env)
        needs = env.needs_all_needs.values()
        config = env.config
        log.info("Nanmnn2")
        from sphinx_needs.filter_common import filter_needs

        filter_string = self.app.config.needs_builder_filter
        filtered_needs = filter_needs(self.app, needs, filter_string)
        needs_per_page_dir = os.path.join(self.outdir, "need_per_page")
        if not os.path.exists(needs_per_page_dir): 
            os.mkdir(needs_per_page_dir)
        for need in filtered_needs:
            needs_id_dict = {}
            id = need['id']
            needs_id_dict[id] = {key: need[key] for key in need if key not in self.LIST_KEY_EXCLUSIONS_NEEDS}
            docs_name = need.get("docname")
            # if "/" in docs_name:
            #     docs_name = docs_name.split("/")
            #     docs_sub = docs_name[0]
            #     log.info(f"needs_per_page_dir:{docs_sub}")
            #     docs_name_file_sub_dir = os.path.join(needs_per_page_dir, docs_sub)
            #     if not os.path.exists(docs_name_file_sub_dir):
            #         os.mkdir(docs_name_file_sub_dir)
            #     docs_name_file = f"{docs_name[1]}.json"
            #     log.info(f"docs_name_file:{docs_name_file}")
            #     docs_name_file_dir = os.path.join(docs_name_file_sub_dir, docs_name_file)
            # else:
            #     docs_name_file = f"{docs_name}.json"
            #     docs_name_file_dir = os.path.join(needs_per_page_dir, docs_name_file)
            
            docs_name = f"{docs_name}.json"
            docs_name_file = os.path.join(needs_per_page_dir, docs_name)
            docs_name_file_dir = os.path.dirname(docs_name_file)
            if not os.path.exists(docs_name_file_dir):
                os.mkdir(docs_name_file_dir)
            try:
                if not os.path.exists(docs_name_file):
                    with open(docs_name_file, 'w') as f:
                        data = {"needs": [needs_id_dict]}
                        json.dump(data, f)
                else:
                    with open(docs_name_file, 'r+') as f:
                        data = json.load(f)
                        data["needs"].append(needs_id_dict)
                        f.seek(0)
                        json.dump(data, f)
            except Exception as e:
                log.error(f"Error during writing json file: {e}_{id}")   
        
        log.info("Needs_Per_Page successfully exported")
        
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


def build_needs_per_page_json(app: Sphinx, _exception: Exception) -> None:
    env = unwrap(app.env)
    if not env.config.needs_per_page:
        return

    # Do not create an additional needs_json for every needs_id, if builder is already "needs_id".
    if isinstance(app.builder, NeedsPerPageBuilder):
        return
    
    try:
        needs_per_page_builder = NeedsPerPageBuilder(app, env)
    except TypeError:
        needs_per_page_builder = NeedsPerPageBuilder(app)
        needs_per_page_builder.set_environment(env)                            
    needs_per_page_builder.finish()