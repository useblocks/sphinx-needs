from typing import Any, Callable, Dict


class Config:
    """
    Stores sphinx-needs specific configuration values.

    This is used to avoid the usage of the sphinx internal config option, as these can be reset or cleaned in
    unspecific order during different events.

    So this Config class somehow collects possible configurations and stores it in a save way.
    """

    def __init__(self) -> None:
        self.configs: Dict[str, Any] = {}

    def add(
        self, name: str, value: Any, option_type: type = str, append: bool = False, overwrite: bool = False
    ) -> None:
        if name not in self.configs:
            self.configs[name] = option_type()
        elif not isinstance(self.configs[name], option_type):
            raise Exception(
                f"Type of needs config option {name} is {type(self.configs[name])}," f"but {option_type} is given"
            )

        if not append:
            self.configs[name] = value
        else:
            if isinstance(self.configs[name], dict):
                self.configs[name] = {**self.configs[name], **value}
            else:
                self.configs[name] += value

    def create(self, name: str, option_type: Callable[[], Any] = str, overwrite: bool = False) -> None:
        if name in self.configs and not overwrite:
            raise Exception(f"option {name} exists.")
        self.configs[name] = option_type()

    def create_or_get(self, name: str, option_type: Callable[[], Any] = str) -> Any:
        if name not in self.configs:
            self.configs[name] = option_type()
        return self.configs[name]

    def get(self, name: str) -> Any:
        return self.configs[name]


NEEDS_CONFIG = Config()
