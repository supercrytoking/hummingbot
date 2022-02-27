from typing import Callable, Optional, Dict, Any

import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTMethod
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BinancePerpetualRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = (
            "application/json" if request.method == RESTMethod.POST else "application/x-www-form-urlencoded"
        )
        return request


def rest_url(path_url: str, domain: str = "binance_perpetual", api_version: str = CONSTANTS.API_VERSION):
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == "binance_perpetual" else CONSTANTS.TESTNET_BASE_URL
    return base_url + api_version + path_url


def wss_url(endpoint: str, domain: str = "binance_perpetual"):
    base_ws_url = CONSTANTS.PERPETUAL_WS_URL if domain == "binance_perpetual" else CONSTANTS.TESTNET_WS_URL
    return base_ws_url + endpoint


def build_api_factory(
        time_synchronizer: TimeSynchronizer,
        time_provider: Callable,
        auth: Optional[AuthBase] = None, ) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
            BinancePerpetualRESTPreProcessor(),
        ])
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor() -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(rest_pre_processors=[BinancePerpetualRESTPreProcessor()])
    return api_factory


async def api_request(path: str,
                      rest_assistant: RESTAssistant,
                      throttler: AsyncThrottler,
                      time_synchronizer: TimeSynchronizer,
                      domain: str = CONSTANTS.DOMAIN,
                      params: Optional[Dict[str, Any]] = None,
                      data: Optional[Dict[str, Any]] = None,
                      method: RESTMethod = RESTMethod.GET,
                      add_timestamp: bool = False,
                      is_auth_required: bool = False,
                      return_err: bool = False,
                      api_version: str = CONSTANTS.API_VERSION,
                      limit_id: Optional[str] = None,
                      timeout: Optional[float] = None):

    async with throttler.execute_task(limit_id=limit_id if limit_id else path):
        if add_timestamp:
            if method == RESTMethod.POST:
                data = data or {}
                data["recvWindow"] = f"{20000}"
                data["timestamp"] = str(int(time_synchronizer.time() * 1e3))
            else:
                params = params or {}
                params["recvWindow"] = f"{20000}"
                params["timestamp"] = str(int(time_synchronizer.time() * 1e3))

        url = rest_url(path, domain, api_version)

        request = RESTRequest(
            method=method,
            url=url,
            params=params,
            data=data,
            is_auth_required=is_auth_required,
            throttler_limit_id=limit_id if limit_id else path
        )
        response = await rest_assistant.call(request=request, timeout=timeout)

        if response.status != 200:
            error_response = await response.json()
            if return_err:
                return error_response
            else:
                raise IOError(f"Error executing request {method.name} {path}. "
                              f"HTTP status is {response.status}. "
                              f"Error: {error_response}")
        return await response.json()


async def get_current_server_time(
        throttler: AsyncThrottler,
        time_synchronizer: TimeSynchronizer,
        domain: str,
) -> float:
    rest_assistant = await build_api_factory_without_time_synchronizer_pre_processor().get_rest_assistant()
    response = await api_request(
        path=CONSTANTS.SERVER_TIME_PATH_URL,
        rest_assistant=rest_assistant,
        throttler=throttler,
        time_synchronizer=time_synchronizer,
        domain=domain,
        method=RESTMethod.GET)
    server_time = response["serverTime"]

    return server_time
