from ..logging import logging


class BaseService:

    def __init__(self, *args, **kwargs):
        self.log = logging.getLogger(__name__)

    def request(self, *args, **kwargs):
        raise NotImplementedError('Must be implemented by the service!')
