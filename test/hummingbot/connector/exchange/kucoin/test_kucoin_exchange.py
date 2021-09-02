import asyncio
import json
import re
import time
import unittest
from collections import Awaitable
from decimal import Decimal
from functools import partial
from typing import Dict

from aioresponses import aioresponses
from hummingbot.connector.exchange.kucoin.kucoin_exchange import KucoinExchange, KUCOIN_ROOT_API
from hummingbot.connector.exchange.kucoin import kucoin_constants as CONSTANTS
from hummingbot.core.network_iterator import NetworkStatus

from hummingbot.connector.exchange.kucoin.kucoin_in_flight_order import \
    KucoinInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class TestKucoinExchange(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.api_key = "someKey"
        cls.api_passphrase = "somePassPhrase"
        cls.api_secret_key = "someSecretKey"

    def setUp(self) -> None:
        super().setUp()
        self.exchange = KucoinExchange(
            self.api_key, self.api_passphrase, self.api_secret_key, trading_pairs=[self.trading_pair]
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_accounts_data_mock(self) -> Dict:
        acc_data = {
            "code": "200000",
            "data": [
                {
                    "id": "someId1",
                    "currency": self.base_asset,
                    "type": "trade",
                    "balance": "81.8446241",
                    "available": "81.8446241",
                    "holds": "0",
                },
                {
                    "id": "someId2",
                    "currency": self.quote_asset,
                    "type": "trade",
                    "balance": "41.3713",
                    "available": "41.3713",
                    "holds": "0",
                },
            ],
        }
        return acc_data

    def get_exchange_rules_mock(self) -> Dict:
        exchange_rules = {
            "code": "200000",
            "data": [
                {
                    "symbol": self.trading_pair,
                    "name": self.trading_pair,
                    "baseCurrency": self.base_asset,
                    "quoteCurrency": self.quote_asset,
                    "feeCurrency": self.quote_asset,
                    "market": "ALTS",
                    "baseMinSize": "1",
                    "quoteMinSize": "0.1",
                    "baseMaxSize": "10000000000",
                    "quoteMaxSize": "99999999",
                    "baseIncrement": "0.1",
                    "quoteIncrement": "0.01",
                    "priceIncrement": "0.01",
                    "priceLimitRate": "0.1",
                    "isMarginEnabled": False,
                    "enableTrading": True,
                },
            ],
        }
        return exchange_rules

    def get_in_flight_order_mock(self, order_id, exchange_id) -> KucoinInFlightOrder:
        order = KucoinInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10.0"),
            amount=Decimal("1"),
        )
        return order

    @aioresponses()
    def test_check_network_success(self, mock_api):
        url = KUCOIN_ROOT_API + CONSTANTS.SERVER_TIME_PATH_URL
        resp = time.time()
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.CONNECTED)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        url = KUCOIN_ROOT_API + CONSTANTS.SERVER_TIME_PATH_URL
        mock_api.get(url, status=500)

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_update_balances(self, mock_api):
        url = KUCOIN_ROOT_API + CONSTANTS.ACCOUNTS_PATH_URL
        resp = self.get_accounts_data_mock()
        mock_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_balances())

        self.assertTrue(self.quote_asset in self.exchange.available_balances)

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        url = KUCOIN_ROOT_API + CONSTANTS.SYMBOLS_PATH_URL
        resp = self.get_exchange_rules_mock()
        mock_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)

    @aioresponses()
    def test_get_order_status(self, mock_api):
        url = KUCOIN_ROOT_API + CONSTANTS.ORDERS_PATH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = "someStatus"
        mock_api.get(regex_url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.get_order_status(exchange_order_id="someId"))

        self.assertEqual(resp, ret)

    @aioresponses()
    def test_place_order(self, mock_api):
        url = KUCOIN_ROOT_API + CONSTANTS.ORDERS_PATH_URL
        resp = {
            "code": "200000",
            "data": {
                "orderId": "someId",
            }
        }
        call_inputs = []

        def callback(*args, **kwargs):
            call_inputs.append((args, kwargs))

        mock_api.post(url, body=json.dumps(resp), callback=callback)
        amount = Decimal("1")
        price = Decimal("10.0")
        ret = self.async_run_with_timeout(
            coroutine=self.exchange.place_order(
                order_id="internalId",
                trading_pair=self.trading_pair,
                amount=amount,
                is_buy=True,
                order_type=OrderType.LIMIT,
                price=price,
            )
        )

        self.assertEqual(ret, resp["data"]["orderId"])

        call_kwargs = call_inputs[0][1]
        call_data = call_kwargs["data"]
        expected_data = json.dumps(
            {
                "size": str(amount),
                "clientOid": "internalId",
                "side": "buy",
                "symbol": self.trading_pair,
                "type": "limit",
                "price": str(price),
            }
        )
        self.assertEqual(call_data, expected_data)

    @aioresponses()
    def test_execute_cancel(self, mock_api):
        url = KUCOIN_ROOT_API + CONSTANTS.ORDERS_PATH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        called = asyncio.Event()

        def callback(*args, **kwargs):
            called.set()

        mock_api.delete(regex_url, callback=callback)

        order_id = "internalId"
        self.exchange.in_flight_orders[order_id] = self.get_in_flight_order_mock(order_id, exchange_id="someId")
        self.async_run_with_timeout(coroutine=self.exchange.execute_cancel(self.trading_pair, order_id))

        self.assertTrue(called.is_set())

    @aioresponses()
    def test_cancel_all(self, mock_api):
        url = KUCOIN_ROOT_API + CONSTANTS.ORDERS_PATH_URL
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        called1 = asyncio.Event()
        called2 = asyncio.Event()

        def callback(ev, *args, **kwargs):
            ev.set()

        mock_api.delete(regex_url, callback=partial(callback, called1))
        mock_api.delete(regex_url, callback=partial(callback, called2))

        order_id1 = "internalId1"
        order_id2 = "internalId2"
        self.exchange.in_flight_orders[order_id1] = self.get_in_flight_order_mock(order_id1, exchange_id="someId1")
        self.exchange.in_flight_orders[order_id2] = self.get_in_flight_order_mock(order_id2, exchange_id="someId2")
        self.async_run_with_timeout(coroutine=self.exchange.cancel_all(timeout_seconds=1))

        self.assertTrue(called1.is_set())
        self.assertTrue(called2.is_set())
