import json
from asyncio import wait_for
from copy import deepcopy
from typing import Any, Dict, List, Optional, Union

from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase


class RESTAssistant:
    """A helper class to contain all REST-related logic.

    The class can be injected with additional functionality by passing a list of objects inheriting from
    the `RESTPreProcessorBase` and `RESTPostProcessorBase` classes. The pre-processors are applied to a request
    before it is sent out, while the post-processors are applied to a response before it is returned to the caller.
    """
    def __init__(
        self,
        connection: RESTConnection,
        throttler: AsyncThrottlerBase,
        rest_pre_processors: Optional[List[RESTPreProcessorBase]] = None,
        rest_post_processors: Optional[List[RESTPostProcessorBase]] = None,
        auth: Optional[AuthBase] = None,
    ):
        self._connection = connection
        self._rest_pre_processors = rest_pre_processors or []
        self._rest_post_processors = rest_post_processors or []
        self._auth = auth
        self._throttler = throttler

    async def execute_request(
            self,
            url: str,
            throttler_limit_id: str,
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            method: RESTMethod = RESTMethod.GET,
            is_auth_required: bool = False,
            return_err: bool = False,
            timeout: Optional[float] = None,
            headers: Optional[Dict[str, Any]] = None) -> Union[str, Dict[str, Any]]:

        headers = headers or {}

        local_headers = {
            "Content-Type": ("application/json" if method in [RESTMethod.POST, RESTMethod.PUT]
                             else "application/x-www-form-urlencoded")}
        local_headers.update(headers)

        data = json.dumps(data) if data is not None else data

        request = RESTRequest(
            method=method,
            url=url,
            params=params,
            data=data,
            headers=local_headers,
            is_auth_required=is_auth_required,
            throttler_limit_id=throttler_limit_id
        )

        async with self._throttler.execute_task(limit_id=throttler_limit_id):
            response = await self.call(request=request, timeout=timeout)

            if 400 <= response.status:
                if return_err:
                    error_response = await response.json()
                    return error_response
                else:
                    error_response = await response.text()
                    raise IOError(f"Error executing request {method.name} {url}. HTTP status is {response.status}. "
                                  f"Error: {error_response}")
            result = await response.json()
            return result

    async def call(self, request: RESTRequest, timeout: Optional[float] = None) -> RESTResponse:
        request = deepcopy(request)
        request = await self._pre_process_request(request)
        request = await self._authenticate(request)
        resp = await wait_for(self._connection.call(request), timeout)
        resp = await self._post_process_response(resp)
        return resp

    async def _pre_process_request(self, request: RESTRequest) -> RESTRequest:
        for pre_processor in self._rest_pre_processors:
            request = await pre_processor.pre_process(request)
        return request

    async def _authenticate(self, request: RESTRequest):
        if self._auth is not None and request.is_auth_required:
            request = await self._auth.rest_authenticate(request)
        return request

    async def _post_process_response(self, response: RESTResponse) -> RESTResponse:
        for post_processor in self._rest_post_processors:
            response = await post_processor.post_process(response)
        return response
