from ..logging import getLogger


class BaseService:

    def __init__(self, *args, **kwargs):
        self.log = getLogger(__name__)

    def request(self, *args, **kwargs):
        raise NotImplementedError('Must be implemented by the service!')
