#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import conf
import contextlib
from decimal import Decimal
import logging
import os
import time
from typing import (
    List,
    Optional
)
import unittest

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketWithdrawAssetEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    TradeFee,
    TradeType,
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.market.liquid.liquid_market import LiquidMarket
from hummingbot.market.deposit_info import DepositInfo
from hummingbot.market.markets_recorder import MarketsRecorder
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.wallet.ethereum.mock_wallet import MockWallet
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from test.integration.humming_web_app import HummingWebApp
from test.integration.assets.mock_data.fixture_liquid import FixtureLiquid
from unittest import mock

MAINNET_RPC_URL = "http://mainnet-rpc.mainnet:8545"
logging.basicConfig(level=METRICS_LOG_LEVEL)
API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.liquid_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.liquid_secret_key
API_HOST = "api.liquid.com"


class LiquidMarketUnitTest(unittest.TestCase):
    events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.WithdrawAsset,
        MarketEvent.OrderFilled,
        MarketEvent.TransactionFailure,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled
    ]

    market: LiquidMarket
    market_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        global MAINNET_RPC_URL
        cls.ev_loop = asyncio.get_event_loop()

        if API_MOCK_ENABLED:
            cls.web_app = HummingWebApp.get_instance()
            cls.web_app.add_host_to_mock(API_HOST, ["/products", "/currencies"])
            cls.web_app.start()
            cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
            cls._patcher = mock.patch("aiohttp.client.URL")
            cls._url_mock = cls._patcher.start()
            cls._url_mock.side_effect = cls.web_app.reroute_local
            cls.web_app.update_response("get", API_HOST, "/fiat_accounts", FixtureLiquid.FIAT_ACCOUNTS)
            cls.web_app.update_response("get", API_HOST, "/crypto_accounts",
                                        FixtureLiquid.CRYPTO_ACCOUNTS)
            cls.web_app.update_response("get", API_HOST, "/orders", FixtureLiquid.ORDERS_GET)
            cls._t_nonce_patcher = unittest.mock.patch("hummingbot.market.liquid.liquid_market.get_tracking_nonce")
            cls._t_nonce_mock = cls._t_nonce_patcher.start()
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: LiquidMarket = LiquidMarket(
            API_KEY, API_SECRET,
            order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
            user_stream_tracker_data_source_type=UserStreamTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=['CEL-ETH']
        )
        # cls.ev_loop.run_until_complete(cls.market._update_balances())
        print("Initializing Liquid market... this will take about a minute.")
        cls.clock.add_iterator(cls.market)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        if API_MOCK_ENABLED:
            cls.web_app.stop()
            cls._patcher.stop()
            cls._t_nonce_patcher.stop()
        cls.stack.close()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../liquid_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        for event_tag in self.events:
            self.market.add_listener(event_tag, self.market_logger)

    def tearDown(self):
        for event_tag in self.events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        maker_buy_trade_fee: TradeFee = self.market.get_fee("BTC", "USD", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                            Decimal(4000))
        self.assertGreater(maker_buy_trade_fee.percent, 0)
        self.assertEqual(len(maker_buy_trade_fee.flat_fees), 0)
        taker_buy_trade_fee: TradeFee = self.market.get_fee("BTC", "USD", OrderType.MARKET, TradeType.BUY, Decimal(1))
        self.assertGreater(taker_buy_trade_fee.percent, 0)
        self.assertEqual(len(taker_buy_trade_fee.flat_fees), 0)
        sell_trade_fee: TradeFee = self.market.get_fee("BTC", "USD", OrderType.LIMIT, TradeType.SELL, Decimal(1),
                                                       Decimal(4000))
        self.assertGreater(sell_trade_fee.percent, 0)
        self.assertEqual(len(sell_trade_fee.flat_fees), 0)

    def test_fee_overrides_config(self):
        fee_overrides_config_map["liquid_taker_fee"].value = None
        taker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.MARKET, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), taker_fee.percent)
        fee_overrides_config_map["liquid_taker_fee"].value = Decimal('0.2')
        taker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.MARKET, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.002"), taker_fee.percent)
        fee_overrides_config_map["liquid_maker_fee"].value = None
        maker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.001"), maker_fee.percent)
        fee_overrides_config_map["liquid_maker_fee"].value = Decimal('0.5')
        maker_fee: TradeFee = self.market.get_fee("LINK", "ETH", OrderType.LIMIT, TradeType.BUY, Decimal(1),
                                                  Decimal('0.1'))
        self.assertAlmostEqual(Decimal("0.005"), maker_fee.percent)

    def place_order(self, is_buy, trading_pair, amount, order_type, price, nonce, order_resp, get_resp):
        order_id, exchange_id = None, None
        if API_MOCK_ENABLED:
            side = 'buy' if is_buy else 'sell'
            self._t_nonce_mock.return_value = nonce
            order_id = f"{side.lower()}-{trading_pair}-{str(nonce)}"
            resp = order_resp.copy()
            resp["client_order_id"] = order_id
            exchange_id = resp["id"]
            self.web_app.update_response("post", API_HOST, "/orders", resp)
        if is_buy:
            order_id = self.market.buy(trading_pair, amount, order_type, price)
        else:
            order_id = self.market.sell(trading_pair, amount, order_type, price)
        if API_MOCK_ENABLED:
            resp = get_resp.copy()
            resp["models"][0]["client_order_id"] = order_id
            self.web_app.update_response("get", API_HOST, "/orders", resp)
        return order_id, exchange_id

    def test_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.05"))

        current_price: Decimal = self.market.get_price("CEL-ETH", True)
        amount: Decimal = 1
        quantized_amount: Decimal = self.market.quantize_order_amount("CEL-ETH", amount)

        order_id, _ = self.place_order(True, "CEL-ETH", amount, OrderType.MARKET, current_price, 10001,
                                       FixtureLiquid.ORDER_BUY, FixtureLiquid.ORDERS_GET_AFTER_BUY)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("CEL", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

        # Reset the logs
        self.market_logger.clear()

        # Try to sell back the same amount of CEL to the exchange, and watch for completion event.
        amount = order_completed_event.base_asset_amount
        quantized_amount = order_completed_event.base_asset_amount
        order_id, _ = self.place_order(False, "CEL-ETH", amount, OrderType.MARKET, current_price, 10002,
                                       FixtureLiquid.ORDER_SELL, FixtureLiquid.ORDERS_GET_AFTER_SELL)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log
                        if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("CEL", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

    def test_limit_buy_and_sell(self):
        self.assertGreater(self.market.get_balance("ETH"), Decimal("0.001"))

        # Try to put limit buy order for 0.05 ETH worth of CEL, and watch for completion event.
        current_bid_price: Decimal = self.market.get_price("CEL-ETH", True)
        bid_price: Decimal = current_bid_price + Decimal("0.05") * current_bid_price
        quantize_bid_price: Decimal = self.market.quantize_order_price("CEL-ETH", bid_price)

        amount: Decimal = 1
        quantized_amount: Decimal = self.market.quantize_order_amount("CEL-ETH", amount)

        order_id, _ = self.place_order(True, "CEL-ETH", quantized_amount, OrderType.LIMIT, quantize_bid_price,
                                       10001, FixtureLiquid.ORDER_BUY_LIMIT, FixtureLiquid.ORDERS_GET_AFTER_LIMIT_BUY)
        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        trade_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                if isinstance(t, OrderFilledEvent)]
        base_amount_traded: Decimal = sum(t.amount for t in trade_events)
        quote_amount_traded: Decimal = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("CEL", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, BuyOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

        # Reset the logs
        self.market_logger.clear()

        # Try to put limit sell order for 0.05 ETH worth of CEL, and watch for completion event.
        current_ask_price: Decimal = self.market.get_price("CEL-ETH", False)
        ask_price: Decimal = current_ask_price - Decimal("0.05") * current_ask_price
        quantize_ask_price: Decimal = self.market.quantize_order_price("CEL-ETH", ask_price)

        quantized_amount = order_completed_event.base_asset_amount

        order_id, _ = self.place_order(False, "CEL-ETH", quantized_amount, OrderType.LIMIT, quantize_ask_price,
                                       10002, FixtureLiquid.ORDER_SELL_LIMIT, FixtureLiquid.ORDERS_GET_AFTER_SELL_LIMIT)

        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        trade_events = [t for t in self.market_logger.event_log
                        if isinstance(t, OrderFilledEvent)]
        base_amount_traded = sum(t.amount for t in trade_events)
        quote_amount_traded = sum(t.amount * t.price for t in trade_events)

        self.assertTrue([evt.order_type == OrderType.LIMIT for evt in trade_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(quantized_amount, order_completed_event.base_asset_amount)
        self.assertEqual("CEL", order_completed_event.base_asset)
        self.assertEqual("ETH", order_completed_event.quote_asset)
        self.assertAlmostEqual(base_amount_traded, order_completed_event.base_asset_amount)
        self.assertAlmostEqual(quote_amount_traded, order_completed_event.quote_asset_amount)
        self.assertGreater(order_completed_event.fee_amount, Decimal(0))
        self.assertTrue(any([isinstance(event, SellOrderCreatedEvent) and event.order_id == order_id
                             for event in self.market_logger.event_log]))

    def test_deposit_info(self):
        [deposit_info] = self.run_parallel(
            self.market.get_deposit_info("ETH")
        )
        deposit_info: DepositInfo = deposit_info
        self.assertIsInstance(deposit_info, DepositInfo)
        self.assertGreater(len(deposit_info.address), 0)
        self.assertGreater(len(deposit_info.extras), 0)
        self.assertTrue("currency_type" in deposit_info.extras.get('extras'))
        self.assertEqual("ETH", deposit_info.extras.get('extras').get('currency'))

    @unittest.skipUnless(any("test_withdraw" in arg for arg in sys.argv), "Withdraw test requires manual action.")
    def test_withdraw(self):
        # CEL_ABI contract file can be found in
        # https://etherscan.io/address/0xe41d2489571d322189246dafa5ebde1f4699f498#code
        with open(realpath(join(__file__, "../../../data/CELABI.json"))) as fd:
            zrx_abi: str = fd.read()

        local_wallet: MockWallet = MockWallet(conf.web3_test_private_key_a,
                                              conf.test_web3_provider_list[0],
                                              {"0xE41d2489571d322189246DaFA5ebDe1F4699F498": zrx_abi},
                                              chain_id=1)

        # Ensure the market account has enough balance for withdraw testing.
        self.assertGreaterEqual(self.market.get_balance("CEL"), Decimal('10'))

        # Withdraw CEL from Liquid to test wallet.
        self.market.withdraw(local_wallet.address, "CEL", Decimal('10'))
        [withdraw_asset_event] = self.run_parallel(
            self.market_logger.wait_for(MarketWithdrawAssetEvent)
        )
        withdraw_asset_event: MarketWithdrawAssetEvent = withdraw_asset_event
        self.assertEqual(local_wallet.address, withdraw_asset_event.to_address)
        self.assertEqual("CEL", withdraw_asset_event.asset_name)
        self.assertEqual(Decimal('10'), withdraw_asset_event.amount)
        self.assertGreater(withdraw_asset_event.fee_amount, Decimal(0))

    def test_cancel_all(self):
        trading_pair = "CEL-ETH"
        bid_price: Decimal = self.market.get_price(trading_pair, True)
        ask_price: Decimal = self.market.get_price(trading_pair, False)
        amount: Decimal = 1
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # Intentionally setting invalid price to prevent getting filled
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price * Decimal("0.7"))
        quantize_ask_price: Decimal = self.market.quantize_order_price(trading_pair, ask_price * Decimal("1.5"))

        _, buy_exchange_id = self.place_order(True, trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price,
                                              10001, FixtureLiquid.ORDER_BUY_CANCEL_ALL,
                                              FixtureLiquid.ORDERS_GET_AFTER_BUY)
        _, sell_exchange_id = self.place_order(False, trading_pair, quantized_amount, OrderType.LIMIT,
                                               quantize_ask_price, 10002, FixtureLiquid.ORDER_SELL_CANCEL_ALL,
                                               FixtureLiquid.ORDERS_GET_AFTER_SELL)

        self.run_parallel(asyncio.sleep(1))
        if API_MOCK_ENABLED:
            order_cancel_resp = FixtureLiquid.ORDER_CANCEL_ALL_1
            self.web_app.update_response("put", API_HOST, f"/orders/{str(buy_exchange_id)}/cancel",
                                         order_cancel_resp)
            order_cancel_resp = FixtureLiquid.ORDER_CANCEL_ALL_2
            self.web_app.update_response("put", API_HOST, f"/orders/{str(sell_exchange_id)}/cancel",
                                         order_cancel_resp)
        [cancellation_results] = self.run_parallel(self.market.cancel_all(5))
        for cr in cancellation_results:
            self.assertEqual(cr.success, True)

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states))

            # Try to put limit buy order for 0.005 ETH worth of CEL, and watch for order creation event.
            current_bid_price: Decimal = self.market.get_price("CEL-ETH", True)
            bid_price: Decimal = current_bid_price * Decimal("0.8")
            quantize_bid_price: Decimal = self.market.quantize_order_price("CEL-ETH", bid_price)

            amount: Decimal = 1
            quantized_amount: Decimal = self.market.quantize_order_amount("CEL-ETH", amount)

            order_id, buy_exchange_id = self.place_order(True, "CEL-ETH", quantized_amount, OrderType.LIMIT,
                                                         quantize_bid_price, 10001, FixtureLiquid.ORDER_SAVE_RESTORE,
                                                         FixtureLiquid.ORDERS_GET_AFTER_BUY)
            [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
            order_created_event: BuyOrderCreatedEvent = order_created_event
            self.assertEqual(order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.market.tracking_states))
            self.assertEqual(order_id, list(self.market.tracking_states.keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.market)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(order_id, recorded_orders[0].id)

            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(config_path, self.market)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertGreater(len(saved_market_states.saved_state), 0)

            # Close out the current market and start another market.
            self.clock.remove_iterator(self.market)
            for event_tag in self.events:
                self.market.remove_listener(event_tag, self.market_logger)

            self.market: LiquidMarket = LiquidMarket(
                API_KEY, API_SECRET,
                order_book_tracker_data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
                user_stream_tracker_data_source_type=UserStreamTrackerDataSourceType.EXCHANGE_API,
                trading_pairs=['ETH-USD', 'CEL-ETH']
            )

            for event_tag in self.events:
                self.market.add_listener(event_tag, self.market_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.clock.add_iterator(self.market)
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            self.market.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(self.market.limit_orders))
            self.assertEqual(1, len(self.market.tracking_states))

            # Cancel the order and verify that the change is saved.
            if API_MOCK_ENABLED:
                order_cancel_resp = FixtureLiquid.ORDER_CANCEL_SAVE_RESTORE.copy()
                self.web_app.update_response("put", API_HOST, f"/orders/{str(buy_exchange_id)}/cancel",
                                             order_cancel_resp)
            self.market.cancel("CEL-ETH", order_id)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states))
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.assertEqual(0, len(saved_market_states.saved_state))
        finally:
            if order_id is not None:
                self.market.cancel("CEL-ETH", order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 1 CEL from the exchange, and watch for completion event.
            current_price: Decimal = self.market.get_price("CEL-ETH", True)
            amount: Decimal = 1
            order_id, _ = self.place_order(True, "CEL-ETH", amount, OrderType.MARKET, current_price, 10001,
                                           FixtureLiquid.ORDER_BUY_LIMIT, FixtureLiquid.ORDERS_GET_AFTER_LIMIT_BUY)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of CEL to the exchange, and watch for completion event.
            amount = buy_order_completed_event.base_asset_amount
            order_id, _ = self.place_order(False, "CEL-ETH", amount, OrderType.MARKET, current_price, 10002,
                                           FixtureLiquid.ORDER_SELL_LIMIT, FixtureLiquid.ORDERS_GET_AFTER_SELL_LIMIT)
            [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            self.assertGreaterEqual(len(trade_fills), 2)
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertGreaterEqual(len(buy_fills), 1)
            self.assertGreaterEqual(len(sell_fills), 1)

            order_id = None

        finally:
            if order_id is not None:
                self.market.cancel("CEL-ETH", order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)


if __name__ == "__main__":
    logging.getLogger("hummingbot.core.event.event_reporter").setLevel(logging.WARNING)
    unittest.main()
