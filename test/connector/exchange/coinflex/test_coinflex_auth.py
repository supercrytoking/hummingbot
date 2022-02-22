#!/usr/bin/env python
import sys
import asyncio
import unittest
import conf
import os
import logging
from async_timeout import timeout
from os.path import join, realpath
from typing import Dict, Any
from hummingbot.connector.exchange.coinflex.coinflex_auth import CoinflexAuth
from hummingbot.connector.exchange.coinflex.coinflex_http_utils import (
    api_call_with_retries,
    build_api_factory,
    CoinflexRESTRequest,
)
from hummingbot.connector.exchange.coinflex import coinflex_utils
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod,
    RESTResponse,
    WSRequest,
)
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
import hummingbot.connector.exchange.coinflex.coinflex_constants as CONSTANTS

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        cls._domain = os.getenv("COINFLEX_DOMAIN", "live")
        cls._logger = logging.getLogger(__name__)
        api_key = conf.coinflex_api_key
        secret_key = conf.coinflex_api_secret
        cls._coinflex_time_synchronizer = TimeSynchronizer()
        cls._auth = CoinflexAuth(
            api_key=api_key,
            secret_key=secret_key,
            time_provider=cls._coinflex_time_synchronizer)
        cls._api_factory = build_api_factory(auth=cls._auth)

    async def rest_auth(self) -> RESTResponse:
        rest_assistant = await self._api_factory.get_rest_assistant()
        request = CoinflexRESTRequest(method=RESTMethod.GET, endpoint=CONSTANTS.ACCOUNTS_PATH_URL, domain=self._domain, is_auth_required=True)
        response = await api_call_with_retries(request=request, rest_assistant=rest_assistant, throttler=self._throttler, logger=self._logger)
        return response

    async def ws_auth(self) -> Dict[Any, Any]:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=coinflex_utils.websocket_url(domain=self._domain), ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        async with timeout(30):
            await ws.send(WSRequest({}, is_auth_required=True))
            payload = {
                "op": "subscribe",
                "args": CONSTANTS.WS_CHANNELS["USER_STREAM"],
                "tag": 101
            }
            await ws.send(WSRequest(payload=payload))
            async for response in ws.iter_messages():
                if all(x in response.data for x in ["channel", "success", "event"]):
                    if response.data["channel"] == "balance:all":
                        return response.data
        return None

    def test_rest_auth(self):
        result = self.ev_loop.run_until_complete(self.rest_auth())
        assert "event" in result
        assert result["event"] == "balances"
        assert "data" in result

    def test_ws_auth(self):
        try:
            subscribed = self.ev_loop.run_until_complete(self.ws_auth())
            no_errors = True
        except Exception as e:
            no_errors = False
            print(f"Error during WS auth test: `{e}")
        assert no_errors is True
        assert subscribed is not None
        assert subscribed["channel"] == "balance:all"
        assert subscribed["success"] is True
