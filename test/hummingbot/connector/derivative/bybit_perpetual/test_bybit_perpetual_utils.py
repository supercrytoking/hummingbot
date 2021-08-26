import pandas as pd
from unittest import TestCase
from unittest.mock import patch

from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_constants as CONSTANTS, bybit_perpetual_utils as utils


class BybitPerpetualUtilsTests(TestCase):

    @patch('hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils.get_tracking_nonce')
    def test_client_order_id_creation(self, nonce_provider_mock):
        nonce_provider_mock.return_value = int(1e15)
        self.assertEqual("B-BTC-USDT-1000000000000000", utils.get_new_client_order_id(True, "BTC-USDT"))
        nonce_provider_mock.return_value = int(1e15) + 1
        self.assertEqual("S-ETH-USDT-1000000000000001", utils.get_new_client_order_id(False, "ETH-USDT"))

    def test_trading_pair_convertion(self):
        trading_pair = "BTC-USDT"
        self.assertEqual("BTCUSDT", utils.convert_to_exchange_trading_pair(trading_pair))

    def test_rest_api_url(self):
        endpoint = {"linear": "/testEndpoint/linear",
                    "non_linear": "/testEndpoint/non_linear"}

        url = utils.rest_api_url_for_endpoint(endpoint=endpoint, domain=None)
        self.assertEqual(CONSTANTS.REST_URLS.get("bybit_perpetual_main") + "/testEndpoint/non_linear", url)

        url = utils.rest_api_url_for_endpoint(endpoint=endpoint, domain=None, trading_pair="BTC-USD")
        self.assertEqual(CONSTANTS.REST_URLS.get("bybit_perpetual_main") + "/testEndpoint/non_linear", url)

        url = utils.rest_api_url_for_endpoint(endpoint=endpoint, domain=None, trading_pair="BTC-USDT")
        self.assertEqual(CONSTANTS.REST_URLS.get("bybit_perpetual_main") + "/testEndpoint/linear", url)

        url = utils.rest_api_url_for_endpoint(endpoint=endpoint, domain="bybit_perpetual_main")
        self.assertEqual(CONSTANTS.REST_URLS.get("bybit_perpetual_main") + "/testEndpoint/non_linear", url)

        url = utils.rest_api_url_for_endpoint(endpoint=endpoint, domain="bybit_perpetual_testnet")
        self.assertEqual(CONSTANTS.REST_URLS.get("bybit_perpetual_testnet") + "/testEndpoint/non_linear", url)

    def test_wss_url(self):
        url = utils.wss_url(None)
        self.assertEqual(CONSTANTS.WSS_URLS.get("bybit_perpetual_main"), url)

        url = utils.wss_url("bybit_perpetual_main")
        self.assertEqual(CONSTANTS.WSS_URLS.get("bybit_perpetual_main"), url)

        url = utils.wss_url("bybit_perpetual_testnet")
        self.assertEqual(CONSTANTS.WSS_URLS.get("bybit_perpetual_testnet"), url)

    def test_get_next_funding_timestamp(self):
        # Simulate 01:00 UTC
        timestamp = pd.Timestamp("2021-08-21-01:00:00", tz="UTC").timestamp()
        expected_ts = pd.Timestamp("2021-08-21-08:00:00", tz="UTC").timestamp()
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))

        # Simulate 09:00 UTC
        timestamp = pd.Timestamp("2021-08-21-09:00:00", tz="UTC").timestamp()
        expected_ts = pd.Timestamp("2021-08-21-16:00:00", tz="UTC").timestamp()
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))

        # Simulate 17:00 UTC
        timestamp = pd.Timestamp("2021-08-21-17:00:00", tz="UTC").timestamp()
        expected_ts = pd.Timestamp("2021-08-22-00:00:00", tz="UTC").timestamp()
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))
