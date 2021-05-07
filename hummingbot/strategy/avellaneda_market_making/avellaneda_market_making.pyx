from decimal import Decimal
import logging
import pandas as pd
import numpy as np
from typing import (
    List,
    Dict,
)
from math import (
    floor,
    ceil,
    isnan
)
import time
import datetime
import os
from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.core.event.events import OrderType

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.client.config.global_config_map import global_config_map

from .data_types import (
    Proposal,
    PriceSize
)
from ..order_tracker cimport OrderTracker
from ..__utils__.trailing_indicators.average_volatility import AverageVolatilityIndicator


NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_neg_one = Decimal(-1)
s_decimal_one = Decimal(1)
pmm_logger = None


cdef class AvellanedaMarketMakingStrategy(StrategyBase):
    OPTION_LOG_CREATE_ORDER = 1 << 3
    OPTION_LOG_MAKER_ORDER_FILLED = 1 << 4
    OPTION_LOG_STATUS_REPORT = 1 << 5
    OPTION_LOG_ALL = 0x7fffffffffffffff

    # These are exchanges where you're expected to expire orders instead of actively cancelling them.
    RADAR_RELAY_TYPE_EXCHANGES = {"radar_relay", "bamboo_relay"}

    @classmethod
    def logger(cls):
        global pmm_logger
        if pmm_logger is None:
            pmm_logger = logging.getLogger(__name__)
        return pmm_logger

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 order_amount: Decimal,
                 order_refresh_time: float = 30.0,
                 max_order_age = 1800.0,
                 order_refresh_tolerance_pct: Decimal = s_decimal_neg_one,
                 order_optimization_enabled = True,
                 filled_order_delay: float = 60.0,
                 inventory_target_base_pct: Decimal = s_decimal_zero,
                 add_transaction_costs_to_orders: bool = True,
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900,
                 hb_app_notification: bool = False,
                 parameters_based_on_spread: bool = True,
                 min_spread: Decimal = Decimal("0.15"),
                 max_spread: Decimal = Decimal("2"),
                 vol_to_spread_multiplier: Decimal = Decimal("1.3"),
                 volatility_sensibility: Decimal = Decimal("0.2"),
                 inventory_risk_aversion: Decimal = Decimal("0.5"),
                 order_book_depth_factor: Decimal = Decimal("0.1"),
                 risk_factor: Decimal = Decimal("0.5"),
                 order_amount_shape_factor: Decimal = Decimal("0.005"),
                 closing_time: Decimal = Decimal("1"),
                 debug_csv_path: str = '',
                 volatility_buffer_size: int = 30,
                 is_debug: bool = True,
                 ):
        super().__init__()
        self._sb_order_tracker = OrderTracker()
        self._market_info = market_info
        self._order_amount = order_amount
        self._order_optimization_enabled = order_optimization_enabled
        self._order_refresh_time = order_refresh_time
        self._max_order_age = max_order_age
        self._order_refresh_tolerance_pct = order_refresh_tolerance_pct
        self._filled_order_delay = filled_order_delay
        self._inventory_target_base_pct = inventory_target_base_pct
        self._add_transaction_costs_to_orders = add_transaction_costs_to_orders
        self._hb_app_notification = hb_app_notification

        self._cancel_timestamp = 0
        self._create_timestamp = 0
        self._limit_order_type = self._market_info.market.get_maker_order_type()
        self._all_markets_ready = False
        self._filled_buys_balance = 0
        self._filled_sells_balance = 0
        self._logging_options = logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._last_own_trade_price = Decimal('nan')

        self.c_add_markets([market_info.market])
        self._ticks_to_be_ready = volatility_buffer_size
        self._parameters_based_on_spread = parameters_based_on_spread
        self._min_spread = min_spread
        self._max_spread = max_spread
        self._vol_to_spread_multiplier = vol_to_spread_multiplier
        self._volatility_sensibility = volatility_sensibility
        self._inventory_risk_aversion = inventory_risk_aversion
        self._avg_vol = AverageVolatilityIndicator(volatility_buffer_size, 1)
        self._last_sampling_timestamp = 0
        self._kappa = order_book_depth_factor
        self._gamma = risk_factor
        self._eta = order_amount_shape_factor
        self._time_left = closing_time
        self._closing_time = closing_time
        self._latest_parameter_calculation_vol = s_decimal_zero
        self._reserved_price = s_decimal_zero
        self._optimal_spread = s_decimal_zero
        self._optimal_ask = s_decimal_zero
        self._optimal_bid = s_decimal_zero
        self._debug_csv_path = debug_csv_path
        self._is_debug = is_debug
        try:
            if self._is_debug:
                os.unlink(self._debug_csv_path)
        except FileNotFoundError:
            pass

    def all_markets_ready(self):
        return all([market.ready for market in self._sb_markets])

    @property
    def market_info(self) -> MarketTradingPairTuple:
        return self._market_info

    @property
    def order_refresh_tolerance_pct(self) -> Decimal:
        return self._order_refresh_tolerance_pct

    @order_refresh_tolerance_pct.setter
    def order_refresh_tolerance_pct(self, value: Decimal):
        self._order_refresh_tolerance_pct = value

    @property
    def order_amount(self) -> Decimal:
        return self._order_amount

    @order_amount.setter
    def order_amount(self, value: Decimal):
        self._order_amount = value

    @property
    def inventory_target_base_pct(self) -> Decimal:
        return self._inventory_target_base_pct

    @inventory_target_base_pct.setter
    def inventory_target_base_pct(self, value: Decimal):
        self._inventory_target_base_pct = value

    @property
    def order_optimization_enabled(self) -> bool:
        return self._order_optimization_enabled

    @order_optimization_enabled.setter
    def order_optimization_enabled(self, value: bool):
        self._order_optimization_enabled = value

    @property
    def order_refresh_time(self) -> float:
        return self._order_refresh_time

    @order_refresh_time.setter
    def order_refresh_time(self, value: float):
        self._order_refresh_time = value

    @property
    def filled_order_delay(self) -> float:
        return self._filled_order_delay

    @filled_order_delay.setter
    def filled_order_delay(self, value: float):
        self._filled_order_delay = value

    @property
    def filled_order_delay(self) -> float:
        return self._filled_order_delay

    @filled_order_delay.setter
    def filled_order_delay(self, value: float):
        self._filled_order_delay = value

    @property
    def add_transaction_costs_to_orders(self) -> bool:
        return self._add_transaction_costs_to_orders

    @add_transaction_costs_to_orders.setter
    def add_transaction_costs_to_orders(self, value: bool):
        self._add_transaction_costs_to_orders = value

    @property
    def base_asset(self):
        return self._market_info.base_asset

    @property
    def quote_asset(self):
        return self._market_info.quote_asset

    @property
    def trading_pair(self):
        return self._market_info.trading_pair

    def get_price(self) -> float:
        return self.get_mid_price()

    def get_last_price(self) -> float:
        return self._market_info.get_last_price()

    def get_mid_price(self) -> float:
        return self.c_get_mid_price()

    cdef object c_get_mid_price(self):
        return self._market_info.get_mid_price()

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    @property
    def active_orders(self) -> List[LimitOrder]:
        if self._market_info not in self.market_info_to_active_orders:
            return []
        return self.market_info_to_active_orders[self._market_info]

    @property
    def active_buys(self) -> List[LimitOrder]:
        return [o for o in self.active_orders if o.is_buy]

    @property
    def active_sells(self) -> List[LimitOrder]:
        return [o for o in self.active_orders if not o.is_buy]

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options

    @property
    def order_tracker(self):
        return self._sb_order_tracker

    def pure_mm_assets_df(self, to_show_current_pct: bool) -> pd.DataFrame:
        market, trading_pair, base_asset, quote_asset = self._market_info
        price = self._market_info.get_mid_price()
        base_balance = float(market.get_balance(base_asset))
        quote_balance = float(market.get_balance(quote_asset))
        available_base_balance = float(market.get_available_balance(base_asset))
        available_quote_balance = float(market.get_available_balance(quote_asset))
        base_value = base_balance * float(price)
        total_in_quote = base_value + quote_balance
        base_ratio = base_value / total_in_quote if total_in_quote > 0 else 0
        quote_ratio = quote_balance / total_in_quote if total_in_quote > 0 else 0
        data=[
            ["", base_asset, quote_asset],
            ["Total Balance", round(base_balance, 4), round(quote_balance, 4)],
            ["Available Balance", round(available_base_balance, 4), round(available_quote_balance, 4)],
            [f"Current Value ({quote_asset})", round(base_value, 4), round(quote_balance, 4)]
        ]
        if to_show_current_pct:
            data.append(["Current %", f"{base_ratio:.1%}", f"{quote_ratio:.1%}"])
        df = pd.DataFrame(data=data)
        return df

    def active_orders_df(self) -> pd.DataFrame:
        market, trading_pair, base_asset, quote_asset = self._market_info
        price = self.get_price()
        active_orders = self.active_orders
        no_sells = len([o for o in active_orders if not o.is_buy and o.client_order_id])
        active_orders.sort(key=lambda x: x.price, reverse=True)
        columns = ["Level", "Type", "Price", "Spread", "Amount (Orig)", "Amount (Adj)", "Age"]
        data = []
        lvl_buy, lvl_sell = 0, 0
        for idx in range(0, len(active_orders)):
            order = active_orders[idx]
            spread = 0 if price == 0 else abs(order.price - price)/price
            age = "n/a"
            # // indicates order is a paper order so 'n/a'. For real orders, calculate age.
            if "//" not in order.client_order_id:
                age = pd.Timestamp(int(time.time()) - int(order.client_order_id[-16:])/1e6,
                                   unit='s').strftime('%H:%M:%S')
            amount_orig = self._order_amount
            data.append([
                "",
                "buy" if order.is_buy else "sell",
                float(order.price),
                f"{spread:.2%}",
                amount_orig,
                float(order.quantity),
                age
            ])

        return pd.DataFrame(data=data, columns=columns)

    def market_status_data_frame(self, market_trading_pair_tuples: List[MarketTradingPairTuple]) -> pd.DataFrame:
        markets_data = []
        markets_columns = ["Exchange", "Market", "Best Bid", "Best Ask", f"MidPrice"]
        markets_columns.append('Reserved Price')
        market_books = [(self._market_info.market, self._market_info.trading_pair)]
        for market, trading_pair in market_books:
            bid_price = market.get_price(trading_pair, False)
            ask_price = market.get_price(trading_pair, True)
            ref_price = self.get_price()
            markets_data.append([
                market.display_name,
                trading_pair,
                float(bid_price),
                float(ask_price),
                float(ref_price),
                round(self._reserved_price, 5),
            ])
        return pd.DataFrame(data=markets_data, columns=markets_columns).replace(np.nan, '', regex=True)

    def format_status(self) -> str:
        if not self._all_markets_ready:
            return "Market connectors are not ready."
        cdef:
            list lines = []
            list warning_lines = []
        warning_lines.extend(self.network_warning([self._market_info]))

        markets_df = self.market_status_data_frame([self._market_info])
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        assets_df = self.pure_mm_assets_df(True)
        first_col_length = max(*assets_df[0].apply(len))
        df_lines = assets_df.to_string(index=False, header=False,
                                       formatters={0: ("{:<" + str(first_col_length) + "}").format}).split("\n")
        lines.extend(["", "  Assets:"] + ["    " + line for line in df_lines])

        # See if there are any open orders.
        if len(self.active_orders) > 0:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        else:
            lines.extend(["", "  No active maker orders."])

        volatility_pct = self._avg_vol.current_value / float(self.get_price()) * 100.0
        if all((self._gamma, self._kappa, not isnan(volatility_pct))):
            lines.extend(["", f"  Strategy parameters:",
                          f"    risk_factor(\u03B3)= {self._gamma:.5E}",
                          f"    order_book_depth_factor(\u03BA)= {self._kappa:.5E}",
                          f"    volatility= {volatility_pct:.3f}%",
                          f"    time until end of trading cycle= {str(datetime.timedelta(seconds=float(self._time_left)//1e3))}"])

        warning_lines.extend(self.balance_warning([self._market_info]))

        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def execute_orders_proposal(self, proposal: Proposal):
        return self.c_execute_orders_proposal(proposal)

    def cancel_order(self, order_id: str):
        return self.c_cancel_order(self._market_info, order_id)

    # ---------------------------------------------------------------

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self._last_timestamp = timestamp
        # start tracking any restored limit order
        restored_order_ids = self.c_track_restored_orders(self.market_info)
        self._time_left = self._closing_time

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)
        cdef:
            int64_t current_tick = <int64_t>(timestamp // self._status_report_interval)
            int64_t last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            bint should_report_warnings = ((current_tick > last_tick) and
                                           (self._logging_options & self.OPTION_LOG_STATUS_REPORT))
            cdef object proposal
        try:
            if not self._all_markets_ready:
                self._all_markets_ready = all([mkt.ready for mkt in self._sb_markets])
                if not self._all_markets_ready:
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning(f"Markets are not ready. No market making trades are permitted.")
                    return

            if should_report_warnings:
                if not all([mkt.network_status is NetworkStatus.CONNECTED for mkt in self._sb_markets]):
                    self.logger().warning(f"WARNING: Some markets are not connected or are down at the moment. Market "
                                          f"making may be dangerous when markets or networks are unstable.")

            self.c_collect_market_variables(timestamp)
            if self.c_is_algorithm_ready():
                proposal = None
                if self._create_timestamp <= self._current_timestamp:
                    # If gamma or kappa are -1 then it's the first time they are calculated.
                    # Also, if volatility goes beyond the threshold specified, we consider volatility regime has changed
                    # so parameters need to be recalculated.
                    if (self._gamma is None) or (self._kappa is None) or \
                            (self._parameters_based_on_spread and
                             self.volatility_diff_from_last_parameter_calculation(self.get_volatility()) >
                             self._volatility_sensibility):
                        self.c_recalculate_parameters()
                    self.c_calculate_reserved_price_and_optimal_spread()

                    # 1. Create base order proposals
                    proposal = self.c_create_base_proposal()
                    # 2. Apply functions that modify orders amount
                    self.c_apply_order_amount_eta_transformation(proposal)
                    # 3. Apply functions that modify orders price
                    self.c_apply_order_price_modifiers(proposal)
                    # 4. Apply budget constraint, i.e. can't buy/sell more than what you have.
                    self.c_apply_budget_constraint(proposal)

                self.c_cancel_active_orders(proposal)
                if self._is_debug:
                    self.dump_debug_variables()
                refresh_proposal = self.c_aged_order_refresh()
                # Firstly restore cancelled aged order
                if refresh_proposal is not None:
                    self.c_execute_orders_proposal(refresh_proposal)
                if self.c_to_create_orders(proposal):
                    self.c_execute_orders_proposal(proposal)
            else:
                self._ticks_to_be_ready-=1
                if self._ticks_to_be_ready % 5 == 0:
                    self.logger().info(f"Calculating volatility... {self._ticks_to_be_ready} seconds to start trading")
        finally:
            self._last_timestamp = timestamp

    cdef c_collect_market_variables(self, double timestamp):
        market, trading_pair, base_asset, quote_asset = self._market_info
        self._last_sampling_timestamp = timestamp
        self._time_left = max(self._time_left - Decimal(timestamp - self._last_timestamp) * 1000, 0)
        price = self.get_price()
        self._avg_vol.add_sample(price)
        # Calculate adjustment factor to have 0.01% of inventory resolution
        base_balance = market.get_balance(base_asset)
        quote_balance = market.get_balance(quote_asset)
        inventory_in_base = quote_balance / price + base_balance
        self._q_adjustment_factor = Decimal(
            "1e5") / inventory_in_base
        if self._time_left == 0:
            # Re-cycle algorithm
            self._time_left = self._closing_time
            if self._parameters_based_on_spread:
                self.c_recalculate_parameters()
            self.logger().info("Recycling algorithm time left and parameters if needed.")

    def volatility_diff_from_last_parameter_calculation(self, current_vol):
        if self._latest_parameter_calculation_vol == 0:
            return s_decimal_zero
        return abs(self._latest_parameter_calculation_vol - Decimal(str(current_vol))) / self._latest_parameter_calculation_vol

    cdef double c_get_spread(self):
        cdef:
            ExchangeBase market = self._market_info.market
            str trading_pair = self._market_info.trading_pair

        return market.c_get_price(trading_pair, True) - market.c_get_price(trading_pair, False)

    def get_volatility(self):
        vol = Decimal(str(self._avg_vol.current_value))
        if vol == s_decimal_zero:
            if self._latest_parameter_calculation_vol != s_decimal_zero:
                vol = Decimal(str(self._latest_parameter_calculation_vol))
            else:
                # Default value at start time if price has no activity
                vol = Decimal(str(self.c_get_spread()/2))
        return vol

    cdef c_calculate_reserved_price_and_optimal_spread(self):
        cdef:
            ExchangeBase market = self._market_info.market

        time_left_fraction = Decimal(str(self._time_left / self._closing_time))

        price = self.get_price()
        q = (market.get_balance(self.base_asset) - Decimal(str(self.c_calculate_target_inventory()))) * self._q_adjustment_factor
        vol = self.get_volatility()
        mid_price_variance = vol ** 2

        self._reserved_price = price - (q * self._gamma * mid_price_variance * time_left_fraction)
        self._optimal_spread = self._gamma * mid_price_variance * time_left_fraction + 2 * Decimal(
            1 + self._gamma / self._kappa).ln() / self._gamma

        spread_inflation_due_to_volatility = max(self._vol_to_spread_multiplier * vol, price * self._min_spread)/(price * self._min_spread)

        if self._parameters_based_on_spread:
            min_limit_bid = price * (1 - self._max_spread * spread_inflation_due_to_volatility)
            max_limit_bid = price * (1 - self._min_spread * spread_inflation_due_to_volatility)
            min_limit_ask = price * (1 + self._min_spread * spread_inflation_due_to_volatility)
            max_limit_ask = price * (1 + self._max_spread * spread_inflation_due_to_volatility)
        else:
            min_limit_bid = s_decimal_zero
            max_limit_bid = min_limit_ask = price
            max_limit_ask = Decimal("Inf")

        self._optimal_ask = min(max(self._reserved_price + self._optimal_spread / 2,
                                    min_limit_ask),
                                max_limit_ask)
        self._optimal_bid = min(max(self._reserved_price - self._optimal_spread / 2,
                                    min_limit_bid),
                                max_limit_bid)
        # This is not what the algorithm will use as proposed bid and ask. This is just the raw output.
        # Optimal bid and optimal ask prices will be used
        if self._is_debug:
            self.logger().info(f"bid={(price-(self._reserved_price - self._optimal_spread / 2)) / price * 100:.4f}% | "
                               f"ask={((self._reserved_price + self._optimal_spread / 2) - price) / price * 100:.4f}% | "
                               f"q={q/self._q_adjustment_factor:.4f} | "
                               f"vol={vol:.4f}")

    cdef object c_calculate_target_inventory(self):
        cdef:
            ExchangeBase market = self._market_info.market
            str trading_pair = self._market_info.trading_pair
            str base_asset = self._market_info.base_asset
            str quote_asset = self._market_info.quote_asset
            object mid_price
            object base_value
            object inventory_value
            object target_inventory_value

        price = self.get_price()
        base_asset_amount = market.get_balance(base_asset)
        quote_asset_amount = market.get_balance(quote_asset)
        base_value = base_asset_amount * price
        inventory_value = base_value + quote_asset_amount
        target_inventory_value = inventory_value * self._inventory_target_base_pct
        return market.c_quantize_order_amount(trading_pair, Decimal(str(target_inventory_value / price)))

    cdef c_recalculate_parameters(self):
        cdef:
            ExchangeBase market = self._market_info.market

        q = (market.get_balance(self.base_asset) - self.c_calculate_target_inventory()) * self._q_adjustment_factor
        vol = self.get_volatility()
        price=self.get_price()

        if q != 0:
            # min_spread will be the expected, unless volatility times the multiplier exceeds it
            min_spread = max(self._min_spread * price, self._vol_to_spread_multiplier * vol)
            # If min_spread got inflated due to the multiplier, we apply the same inflation to max_spread
            max_spread = (self._max_spread * price) * (min_spread / (self._min_spread * price))

            # GAMMA
            # If q or vol are close to 0, gamma will -> Inf. Is this desirable?
            max_possible_gamma = min(
                                    (max_spread - min_spread) / (2 * abs(q) * (vol ** 2)),
                                    (max_spread * (2-self._inventory_risk_aversion) /
                                     self._inventory_risk_aversion + min_spread) / (vol ** 2))
            self._gamma = self._inventory_risk_aversion * max_possible_gamma

            # KAPPA
            # Want the maximum possible spread but with restrictions to avoid negative kappa or division by 0
            max_spread_around_reserved_price = max_spread * (2-self._inventory_risk_aversion) + min_spread * self._inventory_risk_aversion
            if (max_spread_around_reserved_price * self._gamma - (vol * self._gamma) **2) <= s_decimal_zero:
                self._kappa = Decimal('1e100')  # Cap to kappa -> Infinity
            else:
                self._kappa = self._gamma / (Decimal.exp((max_spread_around_reserved_price * self._gamma - (vol * self._gamma) **2) / 2) - 1)

            # ETA
            # Want order_amount to be 10% of the original number if q is in the opposite extreme from target inventory
            q_where_to_decay_order_amount = self.c_calculate_target_inventory() / (self._inventory_risk_aversion * Decimal.ln(Decimal("10")))
            self._eta = s_decimal_one
            if q_where_to_decay_order_amount != s_decimal_zero:
                self._eta = self._eta / q_where_to_decay_order_amount

            self._latest_parameter_calculation_vol = vol

    cdef bint c_is_algorithm_ready(self):
        return self._avg_vol.is_sampling_buffer_full

    cdef object c_create_base_proposal(self):
        cdef:
            ExchangeBase market = self._market_info.market
            list buys = []
            list sells = []

        price = market.c_quantize_order_price(self.trading_pair, Decimal(str(self._optimal_bid)))
        size = market.c_quantize_order_amount(self.trading_pair, self._order_amount)
        if size>0:
            buys.append(PriceSize(price, size))

        price = market.c_quantize_order_price(self.trading_pair, Decimal(str(self._optimal_ask)))
        size = market.c_quantize_order_amount(self.trading_pair, self._order_amount)
        if size>0:
            sells.append(PriceSize(price, size))

        return Proposal(buys, sells)

    cdef tuple c_get_adjusted_available_balance(self, list orders):
        """
        Calculates the available balance, plus the amount attributed to orders.
        :return: (base amount, quote amount) in Decimal
        """
        cdef:
            ExchangeBase market = self._market_info.market
            object base_balance = market.c_get_available_balance(self.base_asset)
            object quote_balance = market.c_get_available_balance(self.quote_asset)

        for order in orders:
            if order.is_buy:
                quote_balance += order.quantity * order.price
            else:
                base_balance += order.quantity

        return base_balance, quote_balance

    cdef c_apply_order_price_modifiers(self, object proposal):
        if self._order_optimization_enabled:
            self.c_apply_order_optimization(proposal)

        if self._add_transaction_costs_to_orders:
            self.c_apply_add_transaction_costs(proposal)

    cdef c_apply_budget_constraint(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
            object quote_size
            object base_size
            object adjusted_amount

        base_balance, quote_balance = self.c_get_adjusted_available_balance(self.active_orders)

        for buy in proposal.buys:
            buy_fee = market.c_get_fee(self.base_asset, self.quote_asset, OrderType.LIMIT, TradeType.BUY,
                                       buy.size, buy.price)
            quote_size = buy.size * buy.price * (Decimal(1) + buy_fee.percent)

            # Adjust buy order size to use remaining balance if less than the order amount
            if quote_balance < quote_size:
                adjusted_amount = quote_balance / (buy.price * (Decimal("1") + buy_fee.percent))
                adjusted_amount = market.c_quantize_order_amount(self.trading_pair, adjusted_amount)
                buy.size = adjusted_amount
                quote_balance = s_decimal_zero
            elif quote_balance == s_decimal_zero:
                buy.size = s_decimal_zero
            else:
                quote_balance -= quote_size

        proposal.buys = [o for o in proposal.buys if o.size > 0]

        for sell in proposal.sells:
            base_size = sell.size

            # Adjust sell order size to use remaining balance if less than the order amount
            if base_balance < base_size:
                adjusted_amount = market.c_quantize_order_amount(self.trading_pair, base_balance)
                sell.size = adjusted_amount
                base_balance = s_decimal_zero
            elif base_balance == s_decimal_zero:
                sell.size = s_decimal_zero
            else:
                base_balance -= base_size

        proposal.sells = [o for o in proposal.sells if o.size > 0]

    # Compare the market price with the top bid and top ask price
    cdef c_apply_order_optimization(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
            object own_buy_size = s_decimal_zero
            object own_sell_size = s_decimal_zero
            object best_order_spread

        for order in self.active_orders:
            if order.is_buy:
                own_buy_size = order.quantity
            else:
                own_sell_size = order.quantity

        if len(proposal.buys) > 0:
            # Get the top bid price in the market using order_optimization_depth and your buy order volume
            top_bid_price = self._market_info.get_price_for_volume(
                False, own_buy_size).result_price
            price_quantum = market.c_get_order_price_quantum(
                self.trading_pair,
                top_bid_price
            )
            # Get the price above the top bid
            price_above_bid = (ceil(top_bid_price / price_quantum) + 1) * price_quantum

            # If the price_above_bid is lower than the price suggested by the top pricing proposal,
            # lower the price and from there apply the best_order_spread to each order in the next levels
            proposal.buys = sorted(proposal.buys, key = lambda p: p.price, reverse = True)
            lower_buy_price = min(proposal.buys[0].price, price_above_bid)
            for i, proposed in enumerate(proposal.buys):
                proposal.buys[i].price = market.c_quantize_order_price(self.trading_pair, lower_buy_price)

        if len(proposal.sells) > 0:
            # Get the top ask price in the market using order_optimization_depth and your sell order volume
            top_ask_price = self._market_info.get_price_for_volume(
                True, own_sell_size).result_price
            price_quantum = market.c_get_order_price_quantum(
                self.trading_pair,
                top_ask_price
            )
            # Get the price below the top ask
            price_below_ask = (floor(top_ask_price / price_quantum) - 1) * price_quantum

            # If the price_below_ask is higher than the price suggested by the pricing proposal,
            # increase your price and from there apply the best_order_spread to each order in the next levels
            proposal.sells = sorted(proposal.sells, key = lambda p: p.price)
            higher_sell_price = max(proposal.sells[0].price, price_below_ask)
            for i, proposed in enumerate(proposal.sells):
                proposal.sells[i].price = market.c_quantize_order_price(self.trading_pair, higher_sell_price)

    cdef c_apply_order_amount_eta_transformation(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
            str trading_pair = self._market_info.trading_pair

        # eta parameter is described in the paper as the shape parameter for having exponentially decreasing order amount
        # for orders that go against inventory target (i.e. Want to buy when excess inventory or sell when deficit inventory)
        q = market.get_balance(self.base_asset) - self.c_calculate_target_inventory()
        if len(proposal.buys) > 0:
            if q > 0:
                for i, proposed in enumerate(proposal.buys):

                    proposal.buys[i].size = market.c_quantize_order_amount(trading_pair, proposal.buys[i].size * Decimal.exp(-self._eta * q))
                proposal.buys = [o for o in proposal.buys if o.size > 0]

        if len(proposal.sells) > 0:
            if q < 0:
                for i, proposed in enumerate(proposal.sells):
                    proposal.sells[i].size = market.c_quantize_order_amount(trading_pair, proposal.sells[i].size * Decimal.exp(self._eta * q))
                proposal.sells = [o for o in proposal.sells if o.size > 0]

    cdef object c_apply_add_transaction_costs(self, object proposal):
        cdef:
            ExchangeBase market = self._market_info.market
        for buy in proposal.buys:
            fee = market.c_get_fee(self.base_asset, self.quote_asset,
                                   self._limit_order_type, TradeType.BUY, buy.size, buy.price)
            price = buy.price * (Decimal(1) - fee.percent)
            buy.price = market.c_quantize_order_price(self.trading_pair, price)
        for sell in proposal.sells:
            fee = market.c_get_fee(self.base_asset, self.quote_asset,
                                   self._limit_order_type, TradeType.SELL, sell.size, sell.price)
            price = sell.price * (Decimal(1) + fee.percent)
            sell.price = market.c_quantize_order_price(self.trading_pair, price)

    cdef c_did_fill_order(self, object order_filled_event):
        cdef:
            str order_id = order_filled_event.order_id
            object market_info = self._sb_order_tracker.c_get_shadow_market_pair_from_order_id(order_id)
            tuple order_fill_record

        if market_info is not None:
            limit_order_record = self._sb_order_tracker.c_get_shadow_limit_order(order_id)
            order_fill_record = (limit_order_record, order_filled_event)

            if order_filled_event.trade_type is TradeType.BUY:
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.trading_pair}) Maker buy order of "
                        f"{order_filled_event.amount} {market_info.base_asset} filled."
                    )
            else:
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_info.trading_pair}) Maker sell order of "
                        f"{order_filled_event.amount} {market_info.base_asset} filled."
                    )

    cdef c_did_complete_buy_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            limit_order_record = self._sb_order_tracker.c_get_limit_order(self._market_info, order_id)
        if limit_order_record is None:
            return
        active_sell_ids = [x.client_order_id for x in self.active_orders if not x.is_buy]

        # delay order creation by filled_order_delay (in seconds)
        self._create_timestamp = self._current_timestamp + self._filled_order_delay
        self._cancel_timestamp = min(self._cancel_timestamp, self._create_timestamp)

        self._filled_buys_balance += 1
        self._last_own_trade_price = limit_order_record.price

        self.log_with_clock(
            logging.INFO,
            f"({self.trading_pair}) Maker buy order {order_id} "
            f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
        )
        self.notify_hb_app(
            f"Maker BUY order {limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency} is filled."
        )

    cdef c_did_complete_sell_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            LimitOrder limit_order_record = self._sb_order_tracker.c_get_limit_order(self._market_info, order_id)
        if limit_order_record is None:
            return
        active_buy_ids = [x.client_order_id for x in self.active_orders if x.is_buy]

        # delay order creation by filled_order_delay (in seconds)
        self._create_timestamp = self._current_timestamp + self._filled_order_delay
        self._cancel_timestamp = min(self._cancel_timestamp, self._create_timestamp)

        self._filled_sells_balance += 1
        self._last_own_trade_price = limit_order_record.price

        self.log_with_clock(
            logging.INFO,
            f"({self.trading_pair}) Maker sell order {order_id} "
            f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
        )
        self.notify_hb_app(
            f"Maker SELL order {limit_order_record.quantity} {limit_order_record.base_currency} @ "
            f"{limit_order_record.price} {limit_order_record.quote_currency} is filled."
        )

    cdef bint c_is_within_tolerance(self, list current_prices, list proposal_prices):
        if len(current_prices) != len(proposal_prices):
            return False
        current_prices = sorted(current_prices)
        proposal_prices = sorted(proposal_prices)
        for current, proposal in zip(current_prices, proposal_prices):
            # if spread diff is more than the tolerance or order quantities are different, return false.
            if abs(proposal - current)/current > self._order_refresh_tolerance_pct:
                return False
        return True

    # Cancel active orders
    # Return value: whether order cancellation is deferred.
    cdef c_cancel_active_orders(self, object proposal):
        if self._cancel_timestamp > self._current_timestamp:
            return
        if not global_config_map.get("0x_active_cancels").value:
            if ((self._market_info.market.name in self.RADAR_RELAY_TYPE_EXCHANGES) or
                    (self._market_info.market.name == "bamboo_relay" and not self._market_info.market.use_coordinator)):
                return

        cdef:
            list active_orders = self.active_orders
            list active_buy_prices = []
            list active_sells = []
            bint to_defer_canceling = False
        if len(active_orders) == 0:
            return
        if proposal is not None:
            active_buy_prices = [Decimal(str(o.price)) for o in active_orders if o.is_buy]
            active_sell_prices = [Decimal(str(o.price)) for o in active_orders if not o.is_buy]
            proposal_buys = [buy.price for buy in proposal.buys]
            proposal_sells = [sell.price for sell in proposal.sells]
            if self.c_is_within_tolerance(active_buy_prices, proposal_buys) and \
                    self.c_is_within_tolerance(active_sell_prices, proposal_sells):
                to_defer_canceling = True

        if not to_defer_canceling:
            for order in active_orders:
                self.c_cancel_order(self._market_info, order.client_order_id)
        else:
            self.set_timers()

    # Refresh all active order that are older that the _max_order_age
    cdef c_aged_order_refresh(self):
        cdef:
            list active_orders = self.active_orders
            list buys = []
            list sells = []

        for order in active_orders:
            age = 0 if "//" in order.client_order_id else \
                int(int(time.time()) - int(order.client_order_id[-16:])/1e6)

            # To prevent duplicating orders due to delay in receiving cancel response
            refresh_check = [o for o in active_orders if o.price == order.price
                             and o.quantity == order.quantity]
            if len(refresh_check) > 1:
                continue

            if age >= self._max_order_age:
                if order.is_buy:
                    buys.append(PriceSize(order.price, order.quantity))
                else:
                    sells.append(PriceSize(order.price, order.quantity))
                self.logger().info(f"Refreshing {'Buy' if order.is_buy else 'Sell'} order with ID - "
                                   f"{order.client_order_id} because it reached maximum order age of "
                                   f"{self._max_order_age} seconds.")
                self.c_cancel_order(self._market_info, order.client_order_id)
        return Proposal(buys, sells)

    cdef bint c_to_create_orders(self, object proposal):
        return self._create_timestamp < self._current_timestamp and \
            proposal is not None

    cdef c_execute_orders_proposal(self, object proposal):
        cdef:
            double expiration_seconds = (self._order_refresh_time
                                         if ((self._market_info.market.name in self.RADAR_RELAY_TYPE_EXCHANGES) or
                                             (self._market_info.market.name == "bamboo_relay" and
                                              not self._market_info.market.use_coordinator))
                                         else NaN)
            str bid_order_id, ask_order_id
            bint orders_created = False

        if len(proposal.buys) > 0:
            if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                price_quote_str = [f"{buy.size.normalize()} {self.base_asset}, "
                                   f"{buy.price.normalize()} {self.quote_asset}"
                                   for buy in proposal.buys]
                self.logger().info(
                    f"({self.trading_pair}) Creating {len(proposal.buys)} bid orders "
                    f"at (Size, Price): {price_quote_str}"
                )
            for buy in proposal.buys:
                bid_order_id = self.c_buy_with_specific_market(
                    self._market_info,
                    buy.size,
                    order_type=self._limit_order_type,
                    price=buy.price,
                    expiration_seconds=expiration_seconds
                )
                orders_created = True
        if len(proposal.sells) > 0:
            if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                price_quote_str = [f"{sell.size.normalize()} {self.base_asset}, "
                                   f"{sell.price.normalize()} {self.quote_asset}"
                                   for sell in proposal.sells]
                self.logger().info(
                    f"({self.trading_pair}) Creating {len(proposal.sells)} ask "
                    f"orders at (Size, Price): {price_quote_str}"
                )
            for sell in proposal.sells:
                ask_order_id = self.c_sell_with_specific_market(
                    self._market_info,
                    sell.size,
                    order_type=self._limit_order_type,
                    price=sell.price,
                    expiration_seconds=expiration_seconds
                )
                orders_created = True
        if orders_created:
            self.set_timers()

    cdef set_timers(self):
        cdef double next_cycle = self._current_timestamp + self._order_refresh_time
        if self._create_timestamp <= self._current_timestamp:
            self._create_timestamp = next_cycle
        if self._cancel_timestamp <= self._current_timestamp:
            self._cancel_timestamp = min(self._create_timestamp, next_cycle)

    def notify_hb_app(self, msg: str):
        if self._hb_app_notification:
            from hummingbot.client.hummingbot_application import HummingbotApplication
            HummingbotApplication.main_application()._notify(msg)

    def dump_debug_variables(self):
        market = self._market_info.market
        mid_price = self.get_price()
        spread = Decimal(str(self.c_get_spread()))

        best_ask = mid_price + spread / 2
        new_ask = self._reserved_price + self._optimal_spread / 2
        best_bid = mid_price - spread / 2
        new_bid = self._reserved_price - self._optimal_spread / 2
        if not os.path.exists(self._debug_csv_path):
            df_header = pd.DataFrame([('mid_price',
                                       'spread',
                                       'reserved_price',
                                       'optimal_spread',
                                       'optimal_bid',
                                       'optimal_ask',
                                       'optimal_bid_to_mid_%',
                                       'optimal_ask_to_mid_%',
                                       'current_inv',
                                       'target_inv',
                                       'time_left_fraction',
                                       'mid_price std_dev',
                                       'gamma',
                                       'kappa',
                                       'eta',
                                       'current_vol_to_calculation_vol',
                                       'inventory_target_pct',
                                       'min_spread',
                                       'max_spread',
                                       'vol_to_spread_multiplier')])
            df_header.to_csv(self._debug_csv_path, mode='a', header=False, index=False)
        df = pd.DataFrame([(mid_price,
                            spread,
                            self._reserved_price,
                            self._optimal_spread,
                            self._optimal_bid,
                            self._optimal_ask,
                            (mid_price - (self._reserved_price - self._optimal_spread / 2)) / mid_price,
                            ((self._reserved_price + self._optimal_spread / 2) - mid_price) / mid_price,
                            market.get_balance(self.base_asset),
                            self.c_calculate_target_inventory(),
                            self._time_left / self._closing_time,
                            self._avg_vol.current_value,
                            self._gamma,
                            self._kappa,
                            self._eta,
                            self.volatility_diff_from_last_parameter_calculation(self.get_volatility()),
                            self.inventory_target_base_pct,
                            self._min_spread,
                            self._max_spread,
                            self._vol_to_spread_multiplier)])
        df.to_csv(self._debug_csv_path, mode='a', header=False, index=False)
