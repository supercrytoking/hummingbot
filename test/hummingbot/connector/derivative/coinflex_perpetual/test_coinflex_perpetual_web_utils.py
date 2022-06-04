import asyncio
import json
import logging
import re
import unittest
from typing import Awaitable
from unittest.mock import patch

from aioresponses.core import aioresponses

import hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils as web_utils
import hummingbot.connector.derivative.coinflex_perpetual.constants as CONSTANTS
from hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils import (
    CoinflexPerpetualRESTPreProcessor,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class CoinflexPerpetualWebUtilsUnitTests(unittest.TestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.pre_processor = CoinflexPerpetualRESTPreProcessor()
        cls.rest_assistant = None
        cls.logger = logging.getLogger(__name__)
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.rest_assistant = self.async_run_with_timeout(web_utils.build_api_factory().get_rest_assistant())
        self.logger.setLevel(1)
        self.logger.addHandler(self)
        self.log_records = []
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _get_regex_url(self,
                       endpoint,
                       return_url=False,
                       endpoint_api_version=None,
                       public=True):
        prv_or_pub = web_utils.public_rest_url if public else web_utils.private_rest_url
        url = prv_or_pub(endpoint, domain=self.domain, endpoint_api_version=endpoint_api_version)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        if return_url:
            return url, regex_url
        return regex_url

    def test_public_rest_url(self):
        path_url = "TEST_PATH"
        domain = CONSTANTS.DEFAULT_DOMAIN
        expected_url = "https://" + CONSTANTS.REST_URL.format(CONSTANTS.PUBLIC_API_VERSION) + f"/{CONSTANTS.PUBLIC_API_VERSION}/{path_url}"
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url, domain))
        self.assertEqual(CONSTANTS.REST_URL.format(CONSTANTS.PUBLIC_API_VERSION), web_utils.public_rest_url(path_url, domain, only_hostname=True))

    def test_private_rest_url(self):
        path_url = "TEST_PATH"
        domain = CONSTANTS.DEFAULT_DOMAIN
        expected_url = "https://" + CONSTANTS.REST_URL.format(CONSTANTS.PRIVATE_API_VERSION) + f"/{CONSTANTS.PRIVATE_API_VERSION}/{path_url}"
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url, domain))

    def test_testnet_rest_url(self):
        path_url = "TEST_PATH"
        domain = "coinflex_perpetual_testnet"
        expected_url = "https://" + CONSTANTS.REST_URL.format(CONSTANTS.PRIVATE_API_VERSION + "stg") + f"/{CONSTANTS.PRIVATE_API_VERSION}/{path_url}"
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url, domain))

    def test_coinflex_perpetual_rest_pre_processor_non_post_request(self):
        request: web_utils.CoinflexPerpetualRESTRequest = web_utils.CoinflexPerpetualRESTRequest(
            method=RESTMethod.GET,
            url="/TEST_URL",
        )

        result_request: web_utils.CoinflexPerpetualRESTRequest = self.async_run_with_timeout(self.pre_processor.pre_process(request))

        self.assertIn("Content-Type", result_request.headers)
        self.assertEqual(result_request.headers["Content-Type"], "application/json")

    def test_coinflex_perpetual_rest_pre_processor_post_request(self):
        request: web_utils.CoinflexPerpetualRESTRequest = web_utils.CoinflexPerpetualRESTRequest(
            method=RESTMethod.POST,
            url="/TEST_URL",
        )

        result_request: web_utils.CoinflexPerpetualRESTRequest = self.async_run_with_timeout(self.pre_processor.pre_process(request))

        self.assertIn("Content-Type", result_request.headers)
        self.assertEqual(result_request.headers["Content-Type"], "application/json")

    def test_build_api_factory(self):
        api_factory = web_utils.build_api_factory()

        self.assertIsInstance(api_factory, WebAssistantsFactory)
        self.assertIsNone(api_factory._auth)

        self.assertTrue(2, len(api_factory._rest_pre_processors))

    @aioresponses()
    def test_web_utils_error_request_error(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.ACCOUNT_INFO_URL)
        mock_response = {"error": "Error"}
        mock_api.get(regex_url, body=json.dumps(mock_response))
        request = web_utils.CoinflexPerpetualRESTRequest(method=RESTMethod.GET, endpoint=CONSTANTS.ACCOUNT_INFO_URL)
        expected_error = {
            **mock_response,
            "errors": "Error"
        }
        with self.assertRaisesRegex(web_utils.CoinflexPerpetualAPIError, str(expected_error)):
            self.async_run_with_timeout(web_utils.api_call_with_retries(request=request,
                                                                        rest_assistant=self.rest_assistant,
                                                                        throttler=self.throttler,
                                                                        logger=self.logger))

    @aioresponses()
    def test_web_utils_error_request_errors(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.ACCOUNT_INFO_URL)
        mock_response = {"errors": "Error"}
        mock_api.get(regex_url, body=json.dumps(mock_response))
        request = web_utils.CoinflexPerpetualRESTRequest(method=RESTMethod.GET, endpoint=CONSTANTS.ACCOUNT_INFO_URL)
        expected_error = {
            **mock_response,
        }
        with self.assertRaisesRegex(web_utils.CoinflexPerpetualAPIError, str(expected_error)):
            self.async_run_with_timeout(web_utils.api_call_with_retries(request=request,
                                                                        rest_assistant=self.rest_assistant,
                                                                        throttler=self.throttler,
                                                                        logger=self.logger))

    @aioresponses()
    def test_web_utils_error_request_success_false(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.ACCOUNT_INFO_URL)
        mock_response = {"success": "false", "message": "Error"}
        mock_api.get(regex_url, body=json.dumps(mock_response))
        request = web_utils.CoinflexPerpetualRESTRequest(method=RESTMethod.GET, endpoint=CONSTANTS.ACCOUNT_INFO_URL)
        expected_error = {
            **mock_response,
            "errors": "Error"
        }
        with self.assertRaisesRegex(web_utils.CoinflexPerpetualAPIError, str(expected_error)):
            self.async_run_with_timeout(web_utils.api_call_with_retries(request=request,
                                                                        rest_assistant=self.rest_assistant,
                                                                        throttler=self.throttler,
                                                                        logger=self.logger))

    @aioresponses()
    def test_web_utils_error_request_data_success_false(self, mock_api):
        regex_url = self._get_regex_url(CONSTANTS.ACCOUNT_INFO_URL)
        mock_response = {
            "data": [{
                "success": "false",
                "message": "Error"
            }]
        }
        mock_api.get(regex_url, body=json.dumps(mock_response))
        request = web_utils.CoinflexPerpetualRESTRequest(method=RESTMethod.GET, endpoint=CONSTANTS.ACCOUNT_INFO_URL)
        with self.assertRaises(web_utils.CoinflexPerpetualAPIError):
            self.async_run_with_timeout(web_utils.api_call_with_retries(request=request,
                                                                        rest_assistant=self.rest_assistant,
                                                                        throttler=self.throttler,
                                                                        logger=self.logger))

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_web_utils_error_request_empty_string(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        regex_url = self._get_regex_url(CONSTANTS.ACCOUNT_INFO_URL)
        mock_api.get(regex_url, body="")
        request = web_utils.CoinflexPerpetualRESTRequest(method=RESTMethod.GET, endpoint=CONSTANTS.ACCOUNT_INFO_URL)
        with self.assertRaises(web_utils.CoinflexPerpetualAPIError):
            self.async_run_with_timeout(web_utils.api_call_with_retries(request=request,
                                                                        rest_assistant=self.rest_assistant,
                                                                        throttler=self.throttler,
                                                                        logger=self.logger))

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_web_utils_error_request_truncated_string(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        regex_url = self._get_regex_url(CONSTANTS.ACCOUNT_INFO_URL)
        mock_api.get(regex_url, body="a" * 101)
        request = web_utils.CoinflexPerpetualRESTRequest(method=RESTMethod.GET, endpoint=CONSTANTS.ACCOUNT_INFO_URL)
        with self.assertRaises(web_utils.CoinflexPerpetualAPIError):
            self.async_run_with_timeout(web_utils.api_call_with_retries(request=request,
                                                                        rest_assistant=self.rest_assistant,
                                                                        throttler=self.throttler,
                                                                        logger=self.logger))

    @aioresponses()
    @patch("hummingbot.connector.derivative.coinflex_perpetual.coinflex_perpetual_web_utils.retry_sleep_time")
    def test_web_utils_retries(self, mock_api, retry_sleep_time_mock):
        retry_sleep_time_mock.side_effect = lambda *args, **kwargs: 0
        url, regex_url = self._get_regex_url(CONSTANTS.ACCOUNT_INFO_URL, return_url=True)
        mock_response = "invalid"
        for i in range(CONSTANTS.API_MAX_RETRIES * 2):
            mock_api.get(regex_url, body=mock_response)
        request = web_utils.CoinflexPerpetualRESTRequest(method=RESTMethod.GET, endpoint=CONSTANTS.ACCOUNT_INFO_URL)
        with self.assertRaises(web_utils.CoinflexPerpetualAPIError):
            self.async_run_with_timeout(web_utils.api_call_with_retries(request=request,
                                                                        rest_assistant=self.rest_assistant,
                                                                        throttler=self.throttler,
                                                                        logger=self.logger))
        with self.assertRaises(web_utils.CoinflexPerpetualAPIError):
            self.async_run_with_timeout(web_utils.api_call_with_retries(request=request,
                                                                        rest_assistant=self.rest_assistant,
                                                                        throttler=self.throttler))

        self.assertTrue(self._is_logged("NETWORK",
                                        f"Error fetching data from {url}. HTTP status is 200. Retrying in 0s. invalid"))

    def test_web_utils_bad_requests(self):
        with self.assertRaises(ValueError):
            request = web_utils.CoinflexPerpetualRESTRequest(method=RESTMethod.GET, endpoint=CONSTANTS.ACCOUNT_INFO_URL, data="")

        request = web_utils.CoinflexPerpetualRESTRequest(method=RESTMethod.GET, url=CONSTANTS.ACCOUNT_INFO_URL)
        with self.assertRaises(ValueError):
            print(request.auth_path)
