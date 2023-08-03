import os
from typing import Iterable, Optional, Set

from docutils import nodes
from sphinx import version_info
from sphinx.application import Sphinx
from sphinx.builders import Builder

from sphinx_needs.logging import get_logger
from sphinx_needs.needsfile import NeedsList
from sphinx_needs.utils import unwrap

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
