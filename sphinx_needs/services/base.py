from __future__ import annotations

from typing import Any, ClassVar

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.logging import get_logger


class BaseService:
    options: ClassVar[list[str]]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.log = get_logger(__name__)

    # note the public API originally just had the `request` method that parsed options as the first argument,
    # and so to not break existing subclasses, we keep that method signature,
    # then also introduce `request_from_directive`, which is what is now called by the directive

    def request(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError("Must be implemented by the service!")

    def request_from_directive(
        self, directive: SphinxDirective, /
    ) -> list[dict[str, Any]]:
        return self.request(directive.options)

    def debug(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("Must be implemented by the service!")
