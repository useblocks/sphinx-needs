from __future__ import annotations

from typing import Any, ClassVar

from sphinx_needs.logging import get_logger


class BaseService:
    options: ClassVar[list[str]]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.log = get_logger(__name__)

    def request(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("Must be implemented by the service!")

    def debug(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("Must be implemented by the service!")
