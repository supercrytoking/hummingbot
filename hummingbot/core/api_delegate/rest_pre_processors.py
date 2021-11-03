import abc

from hummingbot.core.api_delegate.connections.data_types import RESTRequest


class RESTPreProcessorBase(abc.ABC):
    @abc.abstractmethod
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        ...
