from bin import path_util     # noqa: F401

from aiounittest import async_test
from aiohttp import ClientSession
import asyncio
from async_timeout import timeout
from contextlib import ExitStack
from decimal import Decimal
from os.path import join, realpath
import time
from typing import List, Dict
import unittest
from unittest.mock import patch

from hummingbot.connector.gateway_EVM_AMM import (
    GatewayEVMAMM,
    GatewayInFlightOrder,
)
from hummingbot.core.clock import (
    Clock,
    ClockMode,
)
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    TradeType,
    OrderType,
    TokenApprovalEvent,
    TokenApprovalSuccessEvent,
    MarketEvent,
    OrderFilledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future

from test.mock.http_recorder import HttpPlayer

ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
s_decimal_0: Decimal = Decimal(0)


class GatewayEVMAMMConnectorUnitTest(unittest.TestCase):
    _db_path: str
    _http_player: HttpPlayer
    _patch_stack: ExitStack
    _clock: Clock
    _connector: GatewayEVMAMM

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._db_path = realpath(join(__file__, "../fixtures/gateway_evm_amm_fixture.db"))
        cls._http_player = HttpPlayer(cls._db_path)
        cls._clock: Clock = Clock(ClockMode.REALTIME)
        cls._connector: GatewayEVMAMM = GatewayEVMAMM(
            "uniswap",
            "ethereum",
            "ropsten",
            "0x5821715133bB451bDE2d5BC6a4cE3430a4fdAF92",
            trading_pairs=["DAI-WETH"],
            trading_required=True
        )
        cls._clock.add_iterator(cls._connector)
        cls._patch_stack = ExitStack()
        cls._patch_stack.enter_context(cls._http_player.patch_aiohttp_client())
        cls._patch_stack.enter_context(
            patch(
                "hummingbot.core.gateway.gateway_http_client.GatewayHttpClient._http_client",
                return_value=ClientSession()
            )
        )
        cls._patch_stack.enter_context(cls._clock)
        GatewayHttpClient.get_instance().base_url = "https://localhost:5000"
        ev_loop.run_until_complete(cls.wait_til_ready())

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patch_stack.close()

    def setUp(self) -> None:
        self._http_player.replay_timestamp_ms = None

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now: float = time.time()
            next_iteration = now // 1.0 + 1
            if cls._connector.ready:
                break
            else:
                await cls._clock.run_til(next_iteration + 0.1)

    async def run_clock(self):
        while True:
            now: float = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration + 0.1)

    @async_test(loop=ev_loop)
    async def test_update_balances(self):
        self._connector._account_balances.clear()
        self.assertEqual(0, len(self._connector.get_all_balances()))
        await self._connector._update_balances(on_interval=False)
        self.assertEqual(3, len(self._connector.get_all_balances()))
        self.assertAlmostEqual(Decimal("58.919555905095740084"), self._connector.get_balance("ETH"))
        self.assertAlmostEqual(Decimal("1000"), self._connector.get_balance("DAI"))

    @async_test(loop=ev_loop)
    async def test_get_allowances(self):
        big_num: Decimal = Decimal("1000000000000000000000000000")
        allowances: Dict[str, Decimal] = await self._connector.get_allowances()
        self.assertEqual(2, len(allowances))
        self.assertGreater(allowances.get("WETH"), big_num)
        self.assertGreater(allowances.get("DAI"), big_num)

    @async_test(loop=ev_loop)
    async def test_get_chain_info(self):
        self._connector._chain_info.clear()
        await self._connector.get_chain_info()
        self.assertGreater(len(self._connector._chain_info), 2)
        self.assertEqual("ETH", self._connector._chain_info.get("nativeCurrency"))

    @async_test(loop=ev_loop)
    async def test_update_approval_status(self):
        def create_approval_record(token_symbol: str, tx_hash: str) -> GatewayInFlightOrder:
            return GatewayInFlightOrder(
                client_order_id=self._connector.create_approval_order_id(token_symbol),
                exchange_order_id=tx_hash,
                trading_pair=token_symbol,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=s_decimal_0,
                amount=s_decimal_0,
                gas_price=s_decimal_0,
                creation_timestamp=self._connector.current_timestamp
            )
        successful_records: List[GatewayInFlightOrder] = [
            create_approval_record(
                "WETH",
                "0x66b533792f45780fc38573bfd60d6043ab266471607848fb71284cd0d9eecff9"        # noqa: mock
            ),
            create_approval_record(
                "DAI",
                "0x4f81aa904fcb16a8938c0e0a76bf848df32ce6378e9e0060f7afc4b2955de405"        # noqa: mock
            ),
        ]
        fake_records: List[GatewayInFlightOrder] = [
            create_approval_record(
                "WETH",
                "0x66b533792f45780fc38573bfd60d6043ab266471607848fb71284cd0d9eecff8"        # noqa: mock
            ),
            create_approval_record(
                "DAI",
                "0x4f81aa904fcb16a8938c0e0a76bf848df32ce6378e9e0060f7afc4b2955de404"        # noqa: mock
            ),
        ]

        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)
        self._connector.add_listener(TokenApprovalEvent.ApprovalFailed, event_logger)

        try:
            await self._connector.update_token_approval_status(successful_records + fake_records)
            self.assertEqual(2, len(event_logger.event_log))
            self.assertEqual(
                {"WETH", "DAI"},
                set(e.token_symbol for e in event_logger.event_log)
            )
        finally:
            self._connector.remove_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)
            self._connector.remove_listener(TokenApprovalEvent.ApprovalFailed, event_logger)

    @async_test(loop=ev_loop)
    async def test_update_order_status(self):
        def create_order_record(
                trading_pair: str,
                trade_type: TradeType,
                tx_hash: str,
                price: Decimal,
                amount: Decimal,
                gas_price: Decimal) -> GatewayInFlightOrder:
            return GatewayInFlightOrder(
                client_order_id=self._connector.create_market_order_id(trade_type, trading_pair),
                exchange_order_id=tx_hash,
                trading_pair=trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=trade_type,
                price=price,
                amount=amount,
                gas_price=gas_price,
                creation_timestamp=self._connector.current_timestamp
            )
        successful_records: List[GatewayInFlightOrder] = [
            create_order_record(
                "DAI-WETH",
                TradeType.BUY,
                "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",  # noqa: mock
                Decimal("0.00267589"),
                Decimal("1000"),
                Decimal("29")
            )
        ]
        fake_records: List[GatewayInFlightOrder] = [
            create_order_record(
                "DAI-WETH",
                TradeType.BUY,
                "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e17",       # noqa: mock
                Decimal("0.00267589"),
                Decimal("1000"),
                Decimal("29")
            )
        ]

        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.OrderFilled, event_logger)

        try:
            await self._connector._update_order_status(successful_records + fake_records)
            self.assertEqual(1, len(event_logger.event_log))
            filled_event: OrderFilledEvent = event_logger.event_log[0]
            self.assertEqual(
                "0xc7287236f64484b476cfbec0fd21bc49d85f8850c8885665003928a122041e18",       # noqa: mock
                filled_event.exchange_trade_id)
        finally:
            self._connector.remove_listener(MarketEvent.OrderFilled, event_logger)

    @async_test(loop=ev_loop)
    async def test_get_quote_price(self):
        buy_price: Decimal = await self._connector.get_quote_price("DAI-WETH", True, Decimal(1000))
        sell_price: Decimal = await self._connector.get_quote_price("DAI-WETH", False, Decimal(1000))
        self.assertEqual(Decimal("0.0028530896"), buy_price)
        self.assertEqual(Decimal("0.0028231006"), sell_price)

    @async_test(loop=ev_loop)
    async def test_approve_token(self):
        self._http_player.replay_timestamp_ms = 1647320090844
        weth_in_flight_order: GatewayInFlightOrder = await self._connector.approve_token("WETH")
        self._http_player.replay_timestamp_ms = 1647320094877
        dai_in_flight_order: GatewayInFlightOrder = await self._connector.approve_token("DAI")

        self.assertEqual(
            "0x3dda596305131598b33e6c08ad765553af8364f4421e2cc35a0a4fac5c30a190",       # noqa: mock
            weth_in_flight_order.exchange_order_id
        )
        self.assertEqual(
            "0x13bd403d422a28f5df1f9591b768f00234d3bac93b616868d0c0e552ff9ca3ec",       # noqa: mock
            dai_in_flight_order.exchange_order_id
        )

        clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(TokenApprovalEvent.ApprovalSuccessful, event_logger)

        self._http_player.replay_timestamp_ms = 1647320203735
        try:
            async with timeout(10):
                while len(event_logger.event_log) < 2:
                    await event_logger.wait_for(TokenApprovalSuccessEvent)
            self.assertEqual(2, len(event_logger.event_log))
            self.assertEqual(
                {"WETH", "DAI"},
                set(e.token_symbol for e in event_logger.event_log)
            )
        finally:
            clock_task.cancel()
            try:
                await clock_task
            except asyncio.CancelledError:
                pass

    @async_test(loop=ev_loop)
    async def test_buy_order(self):
        self._http_player.replay_timestamp_ms = 1647320210070
        clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.BuyOrderCreated, event_logger)
        self._connector.add_listener(MarketEvent.OrderFilled, event_logger)

        try:
            self._connector.buy("DAI-WETH", Decimal(100), OrderType.LIMIT, Decimal("0.002861464039500"))
            order_created_event: BuyOrderCreatedEvent = await event_logger.wait_for(
                BuyOrderCreatedEvent,
                timeout_seconds=5
            )
            self.assertEqual(
                "0xeaf6b51033b8060c527d58f71ec66226da8d98ec77290017ec7787ed7ab60ae6",       # noqa: mock
                order_created_event.exchange_order_id
            )
            self._http_player.replay_timestamp_ms = 1647320316482
            order_filled_event: OrderFilledEvent = await event_logger.wait_for(OrderFilledEvent, timeout_seconds=5)
            self.assertEqual(
                "0xeaf6b51033b8060c527d58f71ec66226da8d98ec77290017ec7787ed7ab60ae6",       # noqa: mock
                order_filled_event.exchange_trade_id
            )
        finally:
            clock_task.cancel()
            try:
                await clock_task
            except asyncio.CancelledError:
                pass

    @async_test(loop=ev_loop)
    async def test_sell_order(self):
        self._http_player.replay_timestamp_ms = 1647320318718
        clock_task: asyncio.Task = safe_ensure_future(self.run_clock())
        event_logger: EventLogger = EventLogger()
        self._connector.add_listener(MarketEvent.SellOrderCreated, event_logger)
        self._connector.add_listener(MarketEvent.OrderFilled, event_logger)

        try:
            self._connector.sell("DAI-WETH", Decimal(100), OrderType.LIMIT, Decimal("0.002816023229500"))
            order_created_event: SellOrderCreatedEvent = await event_logger.wait_for(
                SellOrderCreatedEvent,
                timeout_seconds=5
            )
            self.assertEqual(
                "0x6d5b02fc76b8234a4bc8067b6487dfb711307c85cf37daac12a3ce0afe0b4340",       # noqa: mock
                order_created_event.exchange_order_id
            )
            self._http_player.replay_timestamp_ms = 1647320411486
            order_filled_event: OrderFilledEvent = await event_logger.wait_for(OrderFilledEvent, timeout_seconds=5)
            self.assertEqual(
                "0x6d5b02fc76b8234a4bc8067b6487dfb711307c85cf37daac12a3ce0afe0b4340",       # noqa: mock
                order_filled_event.exchange_trade_id
            )
        finally:
            clock_task.cancel()
            try:
                await clock_task
            except asyncio.CancelledError:
                pass
