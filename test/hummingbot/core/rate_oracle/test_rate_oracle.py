import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable, Dict
from unittest.mock import patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.ascend_ex.ascend_ex_api_order_book_data_source import AscendExAPIOrderBookDataSource
from hummingbot.core.rate_oracle.rate_oracle import RateOracle, RateOracleSource
from hummingbot.core.rate_oracle.utils import find_rate

from .fixture import Fixture


class RateOracleTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls._binance_connector = RateOracle._binance_connector_without_private_keys(domain="com")
        cls._binance_connector._set_trading_pair_symbol_map(bidict(
            {"ETHBTC": "ETH-BTC",
             "LTCBTC": "LTC-BTC",
             "BTCUSDT": "BTC-USDT",
             "SCRTBTC": "SCRT-BTC"}))
        cls._binance_connector_us = RateOracle._binance_connector_without_private_keys(domain="us")
        cls._binance_connector_us._set_trading_pair_symbol_map(bidict(
            {"BTCUSD": "BTC-USD",
             "ETHUSD": "ETH-USD"}))
        AscendExAPIOrderBookDataSource._trading_pair_symbol_map = bidict(
            {"ETH/BTC": "ETH-BTC",
             "LTC/BTC": "LTC-BTC",
             "BTC/USDT": "BTC-USDT",
             "SCRT/BTC": "SCRT-BTC",
             "MAPS/USDT": "MAPS-USDT",
             "QTUM/BTC": "QTUM-BTC"}
        )
        cls._kucoin_connector = RateOracle._kucoin_connector_without_private_keys()
        cls._kucoin_connector._set_trading_pair_symbol_map(bidict(
            {"SHA-USDT": "SHA-USDT",
             "LOOM-BTC": "LOOM-BTC",
             }))

    @classmethod
    def tearDownClass(cls) -> None:
        AscendExAPIOrderBookDataSource._trading_pair_symbol_map = {}
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        RateOracle.source = RateOracleSource.binance
        RateOracle.get_binance_prices.cache_clear()
        RateOracle.get_kucoin_prices.cache_clear()
        RateOracle.get_ascend_ex_prices.cache_clear()
        RateOracle.get_coingecko_prices.cache_clear()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    @patch("hummingbot.core.rate_oracle.rate_oracle.RateOracle._binance_connector_without_private_keys")
    def test_find_rate_from_source(self, mock_api, connector_creator_mock):
        connector_creator_mock.side_effect = [self._binance_connector, self._binance_connector_us]

        url = RateOracle.binance_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.Binance), repeat=True)

        url = RateOracle.binance_us_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Fixture.Binance
        mock_api.get(regex_url, body=json.dumps(Fixture.BinanceUS), repeat=True)

        expected_rate = (Decimal("33327.43000000") + Decimal("33327.44000000")) / Decimal(2)

        rate = self.async_run_with_timeout(RateOracle.rate_async("BTC-USDT"))
        self.assertEqual(expected_rate, rate)

    @aioresponses()
    def test_get_rate_coingecko(self, mock_api):
        url = RateOracle.coingecko_usd_price_url.format("cryptocurrency", 1, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoCryptocurrencyPage1), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format("cryptocurrency", 2, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoCryptocurrencyPage2), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format("decentralized-exchange", 1, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoDEXPage1), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format("decentralized-exchange", 2, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoDEXPage2), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format("decentralized-finance-defi", 1, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoDEFIPage1), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format("decentralized-finance-defi", 2, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoDEFIPage2), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format("smart-contract-platform", 1, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoSmartContractPage1), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format("smart-contract-platform", 2, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoSmartContractPage2), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format("stablecoins", 1, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoStableCoinsPage1), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format("stablecoins", 2, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoStableCoinsPage2), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format("wrapped-tokens", 1, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoWrappedTokensPage1), repeat=True)

        url = RateOracle.coingecko_usd_price_url.format("wrapped-tokens", 2, "USD")
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoWrappedTokensPage2), repeat=True)

        url = RateOracle.coingecko_supported_vs_tokens_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.CoinGeckoVSCurrencies), repeat=True)

        rates = self.async_run_with_timeout(RateOracle.get_coingecko_prices_by_page("USD", 1, "cryptocurrency"))
        self._assert_rate_dict(rates)
        rates = self.async_run_with_timeout(RateOracle.get_coingecko_prices("USD"))
        self._assert_rate_dict(rates)

    @aioresponses()
    @patch("hummingbot.core.rate_oracle.rate_oracle.RateOracle._binance_connector_without_private_keys")
    def test_rate_oracle_network(self, mock_api, connector_creator_mock):
        connector_creator_mock.side_effect = [self._binance_connector, self._binance_connector_us]
        url = RateOracle.binance_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.Binance))

        url = RateOracle.binance_us_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Fixture.Binance
        mock_api.get(regex_url, body=json.dumps(Fixture.BinanceUS))

        oracle = RateOracle()
        oracle.start()
        self.async_run_with_timeout(oracle.get_ready())
        self.assertGreater(len(oracle.prices), 0)
        rate = oracle.rate("SCRT-USDT")
        self.assertGreater(rate, 0)
        rate1 = oracle.rate("BTC-USDT")
        self.assertGreater(rate1, 100)
        oracle.stop()

    def test_find_rate(self):
        prices = {"HBOT-USDT": Decimal("100"), "AAVE-USDT": Decimal("50"), "USDT-GBP": Decimal("0.75")}
        rate = find_rate(prices, "HBOT-USDT")
        self.assertEqual(rate, Decimal("100"))
        rate = find_rate(prices, "ZBOT-USDT")
        self.assertEqual(rate, None)
        rate = find_rate(prices, "USDT-HBOT")
        self.assertEqual(rate, Decimal("0.01"))
        rate = find_rate(prices, "HBOT-AAVE")
        self.assertEqual(rate, Decimal("2"))
        rate = find_rate(prices, "AAVE-HBOT")
        self.assertEqual(rate, Decimal("0.5"))
        rate = find_rate(prices, "HBOT-GBP")
        self.assertEqual(rate, Decimal("75"))

    @aioresponses()
    @patch("hummingbot.core.rate_oracle.rate_oracle.RateOracle._binance_connector_without_private_keys")
    def test_get_binance_prices(self, mock_api, connector_creator_mock):
        connector_creator_mock.side_effect = [
            self._binance_connector,
            self._binance_connector_us,
            self._binance_connector,
            self._binance_connector_us]

        url = RateOracle.binance_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.Binance), repeat=True)

        url = RateOracle.binance_us_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Fixture.Binance
        mock_api.get(regex_url, body=json.dumps(Fixture.BinanceUS), repeat=True)

        com_prices = self.async_run_with_timeout(RateOracle.get_binance_prices_by_domain(RateOracle.binance_price_url))
        self._assert_rate_dict(com_prices)

        us_prices = self.async_run_with_timeout(
            RateOracle.get_binance_prices_by_domain(RateOracle.binance_us_price_url, "USD", domain="us"))
        self._assert_rate_dict(us_prices)
        self.assertGreater(len(us_prices), 1)

        quotes = {p.split("-")[1] for p in us_prices}
        self.assertEqual(len(quotes), 1)
        self.assertEqual(list(quotes)[0], "USD")
        combined_prices = self.async_run_with_timeout(RateOracle.get_binance_prices())
        self._assert_rate_dict(combined_prices)
        self.assertGreater(len(combined_prices), len(com_prices))

    @aioresponses()
    @patch("hummingbot.core.rate_oracle.rate_oracle.RateOracle._kucoin_connector_without_private_keys")
    def test_get_kucoin_prices(self, mock_api, connector_creator_mock):
        connector_creator_mock.side_effect = [self._kucoin_connector]
        url = RateOracle.kucoin_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.Kucoin), repeat=True)

        prices = self.async_run_with_timeout(RateOracle.get_kucoin_prices())
        self._assert_rate_dict(prices)

    def _assert_rate_dict(self, rates: Dict[str, Decimal]):
        self.assertGreater(len(rates), 0)
        self.assertTrue(all(r > 0 for r in rates.values()))
        self.assertTrue(all(isinstance(k, str) and isinstance(v, Decimal) for k, v in rates.items()))

    @aioresponses()
    def test_get_ascend_ex_prices(self, mock_api):
        url = RateOracle.ascend_ex_price_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, body=json.dumps(Fixture.AscendEx), repeat=True)

        prices = self.async_run_with_timeout(RateOracle.get_ascend_ex_prices())
        self._assert_rate_dict(prices)
