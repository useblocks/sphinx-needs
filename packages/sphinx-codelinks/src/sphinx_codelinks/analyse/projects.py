import json
import logging
from pathlib import Path
from typing import cast

from sphinx_codelinks.analyse.analyse import (
    AnalyseWarning,
    AnalyseWarningType,
    SourceAnalyse,
)
from sphinx_codelinks.config import CodeLinksConfig, CodeLinksProjectConfigType

# initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# log to the console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)


class AnalyseProjects:
    warning_filepath: Path = Path("warnings") / "codelinks_warnings.json"

    def __init__(self, codelink_config: CodeLinksConfig) -> None:
        self.projects_configs: dict[str, CodeLinksProjectConfigType] = (
            codelink_config.projects
        )
        self.projects_analyse: dict[str, SourceAnalyse] = {}
        self.warnings_path = codelink_config.outdir / AnalyseProjects.warning_filepath
        self.outdir = codelink_config.outdir

    def run(self) -> None:
        for project, config in self.projects_configs.items():
            src_analyse = SourceAnalyse(config["analyse_config"])
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
        logger.info(f"Marked content dumped to {output_path}")

    @classmethod
    def load_warnings(cls, warnings_dir: Path) -> list[AnalyseWarning] | None:
        """Load warnings from the given path.

        It mainly used for other apps or users to load warnings files directly.
        """
        warnings_path = warnings_dir / cls.warning_filepath
        if not warnings_path.exists():
            return None
        with warnings_path.open("r") as f:
            # load the json file and convert to AnalyseWarning]
            warnings = json.load(f)
        loaded_warnings: list[AnalyseWarning] = [
            AnalyseWarning(**warning) for warning in warnings
        ]

        return loaded_warnings

    def update_warnings(self) -> None:
        current_warnings: list[AnalyseWarningType] = [
            cast(AnalyseWarningType, _warning.__dict__)
            for analyse in self.projects_analyse.values()
            for _warning in analyse.oneline_warnings
        ]
        self.dump_warnings(current_warnings)

    def dump_warnings(self, warnings: list[AnalyseWarningType]) -> None:
        if not self.warnings_path.parent.exists():
            self.warnings_path.parent.mkdir(parents=True)
        with self.warnings_path.open("w") as f:
            json.dump(
                warnings,
                f,
            )
