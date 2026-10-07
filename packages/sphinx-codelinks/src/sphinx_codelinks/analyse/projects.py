import json

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.config import CodeLinksConfig, CodeLinksProjectConfigType
from sphinx_codelinks.logger import get_logger

logger = get_logger(__name__)


class AnalyseProjects:
    def __init__(self, codelink_config: CodeLinksConfig) -> None:
        self.projects_configs: dict[str, CodeLinksProjectConfigType] = (
            codelink_config.projects
        )
        self.projects_analyse: dict[str, SourceAnalyse] = {}
        self.outdir = codelink_config.outdir

    def run(self) -> None:
        for project, config in self.projects_configs.items():
            src_analyse = SourceAnalyse(config["analyse_config"], name=project)
            src_analyse.run()
            self.projects_analyse[project] = src_analyse

    def dump_markers(self) -> None:
        output_path = self.outdir / "marked_content.json"
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True)
        to_dump = {
            project: [marker.to_dict() for marker in analyse.all_marked_content]
            for project, analyse in self.projects_analyse.items()
        }
        with output_path.open("w") as f:
            json.dump(to_dump, f)
        logger.debug(f"codelinks: marked content dumped to {output_path}")
