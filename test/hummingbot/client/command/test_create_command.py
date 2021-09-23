import asyncio
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import patch, MagicMock, AsyncMock

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
from test.mock.mock_cli import CLIMockingAssistant


class CreateCommandTest(unittest.TestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    def setUp(self, _: MagicMock) -> None:
        super().setUp()
        self.app = HummingbotApplication()
        self.ev_loop = asyncio.get_event_loop()
        self.cli_mock_assistant = CLIMockingAssistant()
        self.cli_mock_assistant.start()

    def tearDown(self) -> None:
        super().tearDown()
        self.cli_mock_assistant.stop()

    async def raise_timeout(*args, **kwargs):
        raise asyncio.TimeoutError

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def async_run_with_timeout_coroutine_must_raise_timeout(self, coroutine: Awaitable, timeout: float = 1):
        class DesiredError(Exception):
            pass

        async def run_coro_that_raises(coro: Awaitable):
            try:
                await coro
            except asyncio.TimeoutError:
                raise DesiredError

        try:
            self.async_run_with_timeout(run_coro_that_raises(coroutine), timeout)
        except DesiredError:  # the coroutine raised an asyncio.TimeoutError as expected
            raise asyncio.TimeoutError
        except asyncio.TimeoutError:  # the coroutine did not finish on time
            raise RuntimeError

    @patch("shutil.copy")
    @patch("hummingbot.client.command.create_command.save_to_yml")
    @patch("hummingbot.client.config.security.Security.is_decryption_done")
    @patch("hummingbot.client.command.status_command.StatusCommand.validate_required_connections")
    @patch("hummingbot.client.config.config_helpers.get_last_price")
    def test_prompt_for_configuration_re_prompts_on_lower_than_minimum_amount(
        self,
        get_last_price_mock: AsyncMock,
        validate_required_connections_mock: AsyncMock,
        is_decryption_done_mock: MagicMock,
        save_to_yml_mock: MagicMock,
        _: MagicMock,
    ):
        get_last_price_mock.return_value = Decimal("11")
        validate_required_connections_mock.return_value = {}
        is_decryption_done_mock.return_value = True
        config_maps = []
        save_to_yml_mock.side_effect = lambda _, cm: config_maps.append(cm)

        global_config_map["create_command_timeout"].value = 10
        global_config_map["other_commands_timeout"].value = 30
        global_config_map["min_quote_order_amount"].value = {"USDT": 11}
        strategy_name = "some-strategy"
        strategy_file_name = f"{strategy_name}.yml"
        base_strategy = "pure_market_making"
        self.cli_mock_assistant.queue_prompt_reply(base_strategy)  # strategy
        self.cli_mock_assistant.queue_prompt_reply("binance")  # spot connector
        self.cli_mock_assistant.queue_prompt_reply("BTC-USDT")  # trading pair
        self.cli_mock_assistant.queue_prompt_reply("1")  # bid spread
        self.cli_mock_assistant.queue_prompt_reply("1")  # ask spread
        self.cli_mock_assistant.queue_prompt_reply("30")  # order refresh time
        self.cli_mock_assistant.queue_prompt_reply("0")  # unacceptable order amount
        self.cli_mock_assistant.queue_prompt_reply("1")  # acceptable order amount
        self.cli_mock_assistant.queue_prompt_reply("No")  # ping pong feature

        self.async_run_with_timeout(self.app.prompt_for_configuration(strategy_file_name))
        self.assertEqual(strategy_file_name, self.app.strategy_file_name)
        self.assertEqual(base_strategy, self.app.strategy_name)
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg="Order amount must be at least 1.0000."
            )
        )

    @patch("shutil.copy")
    @patch("hummingbot.client.command.create_command.save_to_yml")
    @patch("hummingbot.client.config.security.Security.is_decryption_done")
    @patch("hummingbot.client.command.status_command.StatusCommand.validate_required_connections")
    @patch("hummingbot.client.config.config_helpers.get_last_price")
    def test_prompt_for_configuration_accepts_zero_amount_on_get_last_price_network_timeout(
        self,
        get_last_price_mock: AsyncMock,
        validate_required_connections_mock: AsyncMock,
        is_decryption_done_mock: MagicMock,
        save_to_yml_mock: MagicMock,
        _: MagicMock,
    ):
        get_last_price_mock.side_effect = self.raise_timeout
        validate_required_connections_mock.return_value = {}
        is_decryption_done_mock.return_value = True
        config_maps = []
        save_to_yml_mock.side_effect = lambda _, cm: config_maps.append(cm)

        global_config_map["create_command_timeout"].value = 10
        global_config_map["other_commands_timeout"].value = 30
        strategy_name = "some-strategy"
        strategy_file_name = f"{strategy_name}.yml"
        base_strategy = "pure_market_making"
        self.cli_mock_assistant.queue_prompt_reply(base_strategy)  # strategy
        self.cli_mock_assistant.queue_prompt_reply("binance")  # spot connector
        self.cli_mock_assistant.queue_prompt_reply("BTC-USDT")  # trading pair
        self.cli_mock_assistant.queue_prompt_reply("1")  # bid spread
        self.cli_mock_assistant.queue_prompt_reply("1")  # ask spread
        self.cli_mock_assistant.queue_prompt_reply("30")  # order refresh time
        self.cli_mock_assistant.queue_prompt_reply("0")  # order amount
        self.cli_mock_assistant.queue_prompt_reply("No")  # ping pong feature

        self.async_run_with_timeout(self.app.prompt_for_configuration(strategy_file_name))
        self.assertEqual(strategy_file_name, self.app.strategy_file_name)
        self.assertEqual(base_strategy, self.app.strategy_name)

    @patch("shutil.copy")
    @patch("hummingbot.client.command.create_command.save_to_yml")
    @patch("hummingbot.client.config.security.Security.is_decryption_done")
    @patch("hummingbot.client.command.status_command.StatusCommand.validate_required_connections")
    @patch("hummingbot.client.config.config_helpers.get_last_price")
    def test_prompt_for_configuration_handles_status_network_timeout(
        self,
        get_last_price_mock: AsyncMock,
        validate_required_connections_mock: AsyncMock,
        is_decryption_done_mock: MagicMock,
        _: MagicMock,
        __: MagicMock,
    ):
        get_last_price_mock.return_value = None
        validate_required_connections_mock.side_effect = self.raise_timeout
        is_decryption_done_mock.return_value = True
        global_config_map["create_command_timeout"].value = 10
        global_config_map["other_commands_timeout"].value = 30
        global_config_map["min_quote_order_amount"].value = {"USDT": 11}
        strategy_file_name = "some-strategy.yml"
        self.cli_mock_assistant.queue_prompt_reply("pure_market_making")  # strategy
        self.cli_mock_assistant.queue_prompt_reply("binance")  # spot connector
        self.cli_mock_assistant.queue_prompt_reply("BTC-USDT")  # trading pair
        self.cli_mock_assistant.queue_prompt_reply("1")  # bid spread
        self.cli_mock_assistant.queue_prompt_reply("1")  # ask spread
        self.cli_mock_assistant.queue_prompt_reply("30")  # order refresh time
        self.cli_mock_assistant.queue_prompt_reply("1")  # order amount
        self.cli_mock_assistant.queue_prompt_reply("No")  # ping pong feature

        with self.assertRaises(asyncio.TimeoutError):
            self.async_run_with_timeout_coroutine_must_raise_timeout(
                self.app.prompt_for_configuration(strategy_file_name)
            )
        self.assertEqual(None, self.app.strategy_file_name)
        self.assertEqual(None, self.app.strategy_name)
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with(
                msg="\nA network error prevented the connection check to complete. See logs for more details."
            )
        )
