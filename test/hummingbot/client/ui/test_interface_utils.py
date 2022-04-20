import unittest
from copy import deepcopy
from decimal import Decimal
import asyncio
from typing import Awaitable
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock

import pandas as pd

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.ui.interface_utils import start_trade_monitor, \
    format_bytes, start_timer, start_process_monitor, format_df_for_printout


class ExpectedException(Exception):
    pass


class InterfaceUtilsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        for task in asyncio.all_tasks(ev_loop):
            task.cancel()

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.global_config_backup = deepcopy(global_config_map)

    def tearDown(self) -> None:
        self.reset_global_config()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def reset_global_config(self):
        for key, value in self.global_config_backup.items():
            global_config_map[key] = value

    def test_format_bytes(self):
        size = 1024.
        self.assertEqual("1.00 KB", format_bytes(size))
        self.assertEqual("157.36 GB", format_bytes(168963795964))

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    def test_start_timer(self, mock_sleep):
        mock_timer = MagicMock()
        mock_sleep.side_effect = [None, ExpectedException()]
        with self.assertRaises(ExpectedException):
            self.async_run_with_timeout(start_timer(mock_timer))
        self.assertEqual('Duration: 0:00:02', mock_timer.log.call_args_list[0].args[0])
        self.assertEqual('Duration: 0:00:03', mock_timer.log.call_args_list[1].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("psutil.Process")
    def test_start_process_monitor(self, mock_process, mock_sleep):
        mock_process.return_value.num_threads.return_value = 2
        mock_process.return_value.cpu_percent.return_value = 30

        memory_info = MagicMock()
        type(memory_info).vms = PropertyMock(return_value=1024.0)
        type(memory_info).rss = PropertyMock(return_value=1024.0)

        mock_process.return_value.memory_info.return_value = memory_info
        mock_monitor = MagicMock()
        mock_sleep.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(start_process_monitor(mock_monitor))
        self.assertEqual(
            "CPU:    30%, Mem:   512.00 B (1.00 KB), Threads:   2, ",
            mock_monitor.log.call_args_list[0].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.ui.interface_utils.PerformanceMetrics.create", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_multi_loops(self, mock_hb_app, mock_perf, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=True)}
        mock_app._get_trades_from_session.return_value = [MagicMock(market="ExchangeA", symbol="HBOT-USDT")]
        mock_app.get_current_balances = AsyncMock()
        mock_perf.side_effect = [MagicMock(return_pct=Decimal("0.01"), total_pnl=Decimal("2")),
                                 MagicMock(return_pct=Decimal("0.02"), total_pnl=Decimal("2"))]
        mock_sleep.side_effect = [None, asyncio.CancelledError()]
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(start_trade_monitor(mock_result))
        self.assertEqual(3, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])
        self.assertEqual('Trades: 1, Total P&L: 2.00 USDT, Return %: 1.00%', mock_result.log.call_args_list[1].args[0])
        self.assertEqual('Trades: 1, Total P&L: 2.00 USDT, Return %: 2.00%', mock_result.log.call_args_list[2].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.ui.interface_utils.PerformanceMetrics.create", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_multi_pairs_diff_quotes(self, mock_hb_app, mock_perf, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=True)}
        mock_app._get_trades_from_session.return_value = [
            MagicMock(market="ExchangeA", symbol="HBOT-USDT"),
            MagicMock(market="ExchangeA", symbol="HBOT-BTC")
        ]
        mock_app.get_current_balances = AsyncMock()
        mock_perf.side_effect = [MagicMock(return_pct=Decimal("0.01"), total_pnl=Decimal("2")),
                                 MagicMock(return_pct=Decimal("0.02"), total_pnl=Decimal("3"))]
        mock_sleep.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(start_trade_monitor(mock_result))
        self.assertEqual(2, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])
        self.assertEqual('Trades: 2, Total P&L: N/A, Return %: 1.50%', mock_result.log.call_args_list[1].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.ui.interface_utils.PerformanceMetrics.create", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_multi_pairs_same_quote(self, mock_hb_app, mock_perf, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=True)}
        mock_app._get_trades_from_session.return_value = [
            MagicMock(market="ExchangeA", symbol="HBOT-USDT"),
            MagicMock(market="ExchangeA", symbol="BTC-USDT")
        ]
        mock_app.get_current_balances = AsyncMock()
        mock_perf.side_effect = [MagicMock(return_pct=Decimal("0.01"), total_pnl=Decimal("2")),
                                 MagicMock(return_pct=Decimal("0.02"), total_pnl=Decimal("3"))]
        mock_sleep.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(start_trade_monitor(mock_result))
        self.assertEqual(2, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])
        self.assertEqual('Trades: 2, Total P&L: 5.00 USDT, Return %: 1.50%', mock_result.log.call_args_list[1].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_market_not_ready(self, mock_hb_app, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=False)}
        mock_sleep.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(start_trade_monitor(mock_result))
        self.assertEqual(1, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_market_no_trade(self, mock_hb_app, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.return_value = False
        mock_app.markets.return_values = {"a": MagicMock(ready=True)}
        mock_app._get_trades_from_session.return_value = []
        mock_sleep.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(start_trade_monitor(mock_result))
        self.assertEqual(1, mock_result.log.call_count)
        self.assertEqual('Trades: 0, Total P&L: 0.00, Return %: 0.00%', mock_result.log.call_args_list[0].args[0])

    @patch("hummingbot.client.ui.interface_utils._sleep", new_callable=AsyncMock)
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication")
    def test_start_trade_monitor_loop_continues_on_failure(self, mock_hb_app, mock_sleep):
        mock_result = MagicMock()
        mock_app = mock_hb_app.main_application()
        mock_app.strategy_task.done.side_effect = [RuntimeError(), asyncio.CancelledError()]
        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(start_trade_monitor(mock_result))
        self.assertEqual(2, mock_app.strategy_task.done.call_count)  # was called again after exception

    def test_format_df_for_printout(self):
        df = pd.DataFrame(
            data={
                "first": [1, 2],
                "second": ["12345", "67890"],
            }
        )

        df_str = format_df_for_printout(df, table_format="psql")
        target_str = (
            "+---------+----------+"
            "\n|   first |   second |"
            "\n|---------+----------|"
            "\n|       1 |    12345 |"
            "\n|       2 |    67890 |"
            "\n+---------+----------+"
        )

        self.assertEqual(target_str, df_str)

        df_str = format_df_for_printout(df, table_format="psql", max_col_width=4)
        target_str = (
            "+--------+--------+"
            "\n|   f... | s...   |"
            "\n|--------+--------|"
            "\n|      1 | 1...   |"
            "\n|      2 | 6...   |"
            "\n+--------+--------+"
        )

        self.assertEqual(target_str, df_str)

        df_str = format_df_for_printout(df, table_format="psql", index=True)
        target_str = (
            "+----+---------+----------+"
            "\n|    |   first |   second |"
            "\n|----+---------+----------|"
            "\n|  0 |       1 |    12345 |"
            "\n|  1 |       2 |    67890 |"
            "\n+----+---------+----------+"
        )

        self.assertEqual(target_str, df_str)

    def test_format_df_for_printout_table_format_from_global_config(self):
        df = pd.DataFrame(
            data={
                "first": [1, 2],
                "second": ["12345", "67890"],
            }
        )

        global_config_map.get("tables_format").value = "psql"
        df_str = format_df_for_printout(df)
        target_str = (
            "+---------+----------+"
            "\n|   first |   second |"
            "\n|---------+----------|"
            "\n|       1 |    12345 |"
            "\n|       2 |    67890 |"
            "\n+---------+----------+"
        )

        self.assertEqual(target_str, df_str)

        global_config_map.get("tables_format").value = "simple"
        df_str = format_df_for_printout(df)
        target_str = (
            "  first    second"
            "\n-------  --------"
            "\n      1     12345"
            "\n      2     67890"
        )

        self.assertEqual(target_str, df_str)
