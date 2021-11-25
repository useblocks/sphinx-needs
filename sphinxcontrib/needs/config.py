class Config:
    """
    Stores sphinx-needs specific configuration values.

    This is used to avoid the usage of the sphinx internal config option, as these can be reset or cleaned in
    unspecific order during different events.

    So this Config class somehow collects possible configurations and stores it in a save way.
    """

    def __init__(self):
        self.configs = {}

    def add(self, name, value, option_type=str, append=False, overwrite=False):
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

    def create(self, name, option_type=str, overwrite=False):
        if name in self.configs and not overwrite:
            raise Exception(f"option {name} exists.")
        self.configs[name] = option_type()

    def create_or_get(self, name, option_type=str):
        if name not in self.configs:
            self.configs[name] = option_type()
        return self.configs.get(name, None)

    def get(self, name):
        return self.configs[name]


NEEDS_CONFIG = Config()
