from sphinxcontrib.needs.logging import get_logger


class BaseService:
    def __init__(self, *args, **kwargs):
        self.log = get_logger(__name__)

    def request(self, *args, **kwargs):
        raise NotImplementedError("Must be implemented by the service!")
