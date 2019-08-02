from collections import (
    defaultdict,
    deque,
)
from decimal import Decimal
import logging
from typing import (
    List,
    Tuple,
    Optional,
    Dict,
    Deque
)

from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import (
    TradeType
)
from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import (
    MarketBase,
    OrderType
)
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion

from .cross_exchange_market_pair import CrossExchangeMarketPair
from .order_id_market_pair_tracker import OrderIDMarketPairTracker

NaN = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_nan = Decimal("nan")
s_logger = None


cdef class CrossExchangeMarketMakingStrategy(StrategyBase):
    OPTION_LOG_NULL_ORDER_SIZE = 1 << 0
    OPTION_LOG_REMOVING_ORDER = 1 << 1
    OPTION_LOG_ADJUST_ORDER = 1 << 2
    OPTION_LOG_CREATE_ORDER = 1 << 3
    OPTION_LOG_MAKER_ORDER_FILLED = 1 << 4
    OPTION_LOG_STATUS_REPORT = 1 << 5
    OPTION_LOG_MAKER_ORDER_HEDGED = 1 << 6
    OPTION_LOG_ALL = 0x7fffffffffffffff

    ORDER_ADJUST_SAMPLE_INTERVAL = 5
    ORDER_ADJUST_SAMPLE_WINDOW = 12

    SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION = 60.0 * 15
    CANCEL_EXPIRY_DURATION = 60.0

    @classmethod
    def logger(cls):
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self, market_pairs: List[CrossExchangeMarketPair], min_profitability: float,
                 trade_size_override: Optional[float] = 0.0,
                 order_size_taker_volume_factor: float = 0.25,
                 order_size_taker_balance_factor: float = 0.995,
                 order_size_portfolio_ratio_limit: float = 0.1667,
                 limit_order_min_expiration: float = 130.0,
                 cancel_order_threshold: float = -1,
                 active_order_canceling: bint = True,
                 anti_hysteresis_duration: float = 60.0,
                 logging_options: int = OPTION_LOG_ALL,
                 status_report_interval: float = 900):
        if len(market_pairs) < 0:
            raise ValueError(f"market_pairs must not be empty.")
        if not 0 <= order_size_taker_volume_factor <= 1:
            raise ValueError(f"order_size_taker_volume_factor must be between 0 and 1.")
        if not 0 <= order_size_taker_balance_factor <= 1:
            raise ValueError(f"order_size_taker_balance_factor must be between 0 and 1.")

        super().__init__()
        self._market_pairs = {
            (market_pair.maker.market, market_pair.maker.trading_pair): market_pair
            for market_pair in market_pairs
        }
        self._maker_markets = set([market_pair.maker.market for market_pair in market_pairs])
        self._taker_markets = set([market_pair.taker.market for market_pair in market_pairs])
        self._all_markets_ready = False
        self._min_profitability = min_profitability
        self._order_size_taker_volume_factor = order_size_taker_volume_factor
        self._order_size_taker_balance_factor = order_size_taker_balance_factor
        self._trade_size_override = trade_size_override
        self._order_size_portfolio_ratio_limit = order_size_portfolio_ratio_limit
        self._anti_hysteresis_timers = {}
        self._order_fill_buy_events = {}
        self._order_fill_sell_events = {}
        self._suggested_price_samples = {}
        self._anti_hysteresis_duration = anti_hysteresis_duration
        self._logging_options = <int64_t>logging_options
        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._cancel_order_threshold = cancel_order_threshold
        self._active_order_canceling = active_order_canceling
        self._exchange_rate_conversion = ExchangeRateConversion.get_instance()
        self._market_pair_tracker = OrderIDMarketPairTracker()

        self.limit_order_min_expiration = limit_order_min_expiration

        cdef:
            list all_markets = list(self._maker_markets | self._taker_markets)

        self.c_add_markets(all_markets)

    @property
    def active_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.active_maker_orders

    @property
    def cached_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return self._sb_order_tracker.shadow_maker_orders

    @property
    def active_bids(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_maker_orders if limit_order.is_buy]

    @property
    def active_asks(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_maker_orders if not limit_order.is_buy]

    @property
    def suggested_price_samples(self) -> Dict[CrossExchangeMarketPair, Tuple[Deque[Decimal], Deque[Decimal]]]:
        return self._suggested_price_samples

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, int64_t logging_options):
        self._logging_options = logging_options

    @property
    def exchange_rate_conversion(self) -> ExchangeRateConversion:
        return self._exchange_rate_conversion

    def format_status(self) -> str:
        cdef:
            list lines = []
            list warning_lines = []
            dict tracked_maker_orders = {}
            LimitOrder typed_limit_order

        # Go through the currently open limit orders, and group them by market pair.
        for _, limit_order in self.active_maker_orders:
            typed_limit_order = limit_order
            market_pair = self._market_pair_tracker.c_get_market_pair_from_order_id(typed_limit_order.client_order_id)
            if market_pair not in tracked_maker_orders:
                tracked_maker_orders[market_pair] = {typed_limit_order.client_order_id: typed_limit_order}
            else:
                tracked_maker_orders[market_pair][typed_limit_order.client_order_id] = typed_limit_order

        for market_pair in self._market_pairs.values():
            warning_lines.extend(self.network_warning([market_pair.maker, market_pair.taker]))

            markets_df = self.market_status_data_frame([market_pair.maker, market_pair.taker])
            lines.extend(["", "  Markets:"] +
                         ["    " + line for line in str(markets_df).split("\n")])

            assets_df = self.wallet_balance_data_frame([market_pair.maker, market_pair.taker])
            lines.extend(["", "  Assets:"] +
                         ["    " + line for line in str(assets_df).split("\n")])

            bid_profitability, ask_profitability = self.c_calculate_market_making_profitability(
                market_pair
            )
            lines.extend(["", "  Profitability:"] +
                         [f"    make bid on {market_pair.maker.market.name}, "
                          f"take bid on {market_pair.taker.market.name}: {round(bid_profitability * 100, 4)} %"] +
                         [f"    make ask on {market_pair.maker.market.name}, "
                          f"take ask on {market_pair.taker.market.name}: {round(ask_profitability * 100, 4)} %"])

            # See if there're any open orders.
            if market_pair in tracked_maker_orders and len(tracked_maker_orders[market_pair]) > 0:
                limit_orders = list(tracked_maker_orders[market_pair].values())
                df = LimitOrder.to_pandas(limit_orders)
                df_lines = str(df).split("\n")
                lines.extend(["", "  Active orders:"] +
                             ["    " + line for line in df_lines])
            else:
                lines.extend(["", "  No active maker orders."])

            warning_lines.extend(self.balance_warning([market_pair.maker, market_pair.taker]))

        if len(warning_lines) > 0:
            lines.extend(["", "  *** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def get_market_making_price_and_size_limit(self, market_pair: CrossExchangeMarketPair, is_bid: bool,
                                               own_order_depth: float = 0.0) -> Tuple[Decimal, Decimal]:
        return self.c_get_market_making_price_and_size_limit(market_pair, is_bid, own_order_depth=own_order_depth)

    def get_order_size_after_portfolio_ratio_limit(self, market_pair: CrossExchangeMarketPair,
                                                   original_order_size: float) -> float:
        return self.c_get_order_size_after_portfolio_ratio_limit(market_pair, original_order_size)

    def get_adjusted_limit_order_size(self, market_pair: CrossExchangeMarketPair, price: float,
                                      original_order_size: float) -> float:
        return self.c_get_adjusted_limit_order_size(market_pair, price, original_order_size)

    def has_market_making_profit_potential(self, market_pair: CrossExchangeMarketPair) -> Tuple[bool, bool]:
        return self.c_has_market_making_profit_potential(market_pair)

    def get_market_making_price_and_size_limit(self, market_pair: CrossExchangeMarketPair,
                                               is_bid: bool,
                                               own_order_depth: float = 0) -> Tuple[Decimal, Decimal]:
        return self.c_get_market_making_price_and_size_limit(market_pair, is_bid, own_order_depth=own_order_depth)

    def calculate_effective_hedging_price(self, OrderBook taker_order_book,
                                          is_maker_bid: bool,
                                          maker_order_size: float) -> float:
        return self.c_calculate_effective_hedging_price(taker_order_book, is_maker_bid, maker_order_size)

    def check_if_still_profitable(self, market_pair: CrossExchangeMarketPair,
                                  LimitOrder active_order,
                                  double current_hedging_price) -> bool:
        return self.c_check_if_still_profitable(market_pair, active_order, current_hedging_price)

    def check_if_sufficient_balance(self, market_pair: CrossExchangeMarketPair,
                                    LimitOrder active_order) -> bool:
        return self.c_check_if_sufficient_balance(market_pair, active_order)

    def check_if_price_correct(self, market_pair: CrossExchangeMarketPair,
                               LimitOrder active_order,
                               double current_hedging_price) -> bool:
        return self.c_check_if_price_correct(market_pair, active_order, current_hedging_price)
    # ---------------------------------------------------------------

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self._last_timestamp = timestamp

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)

        cdef:
            int64_t current_tick = <int64_t>(timestamp // self._status_report_interval)
            int64_t last_tick = <int64_t>(self._last_timestamp // self._status_report_interval)
            bint should_report_warnings = ((current_tick > last_tick) and
                                           (self._logging_options & self.OPTION_LOG_STATUS_REPORT))
            list active_maker_orders = self.active_maker_orders
            LimitOrder limit_order

        try:
            self._market_pair_tracker.c_tick(timestamp)

            if not self._all_markets_ready:
                self._all_markets_ready = all([market.ready for market in self._sb_markets])
                if not self._all_markets_ready:
                    # Markets not ready yet. Don't do anything.
                    if should_report_warnings:
                        self.logger().warning(f"Markets are not ready. No market making trades are permitted.")
                    return
                else:
                    if self.OPTION_LOG_STATUS_REPORT:
                        self.logger().info(f"Markets are ready. Trading started.")

            if should_report_warnings:
                if not all([market.network_status is NetworkStatus.CONNECTED for market in self._sb_markets]):
                    self.logger().warning(f"WARNING: Some markets are not connected or are down at the moment. Market "
                                          f"making may be dangerous when markets or networks are unstable.")

            market_pair_to_active_orders = defaultdict(list)

            for maker_market, limit_order in active_maker_orders:
                market_pair = self._market_pairs.get((maker_market, limit_order.symbol))
                if market_pair is None:
                    self.log_with_clock(logging.WARNING,
                                        f"The in-flight maker order in for the symbol '{limit_order.symbol}' "
                                        f"does not correspond to any whitelisted market pairs. Skipping.")
                    continue

                if not self._sb_order_tracker.c_has_in_flight_cancel(limit_order.client_order_id):
                    market_pair_to_active_orders[market_pair].append(limit_order)

            for market_pair in self._market_pairs.values():
                self.c_process_market_pair(market_pair, market_pair_to_active_orders[market_pair])
        finally:
            self._last_timestamp = timestamp

    cdef c_process_market_pair(self, object market_pair, list active_orders):
        cdef:
            double current_hedging_price
            MarketBase taker_market
            bint is_buy
            bint has_active_bid = False
            bint has_active_ask = False
            bint need_adjust_order = False
            double anti_hysteresis_timer = self._anti_hysteresis_timers.get(market_pair, 0)
            dict tracked_taker_orders = self._sb_order_tracker.c_get_taker_orders()

        global s_decimal_zero

        # Take suggested bid / ask price samples.
        self.c_take_suggested_price_sample(market_pair, active_orders)

        for active_order in active_orders:
            # Mark the has_active_bid and has_active_ask flags
            is_buy = active_order.is_buy
            if is_buy:
                has_active_bid = True
            else:
                has_active_ask = True

            current_hedging_price = self.c_calculate_effective_hedging_price(
                market_pair.taker.order_book,
                is_buy,
                float(active_order.quantity)
            )

            # See if it's still profitable to keep the order on maker market. If not, remove it.
            if not self.c_check_if_still_profitable(market_pair, active_order, current_hedging_price):
                continue

            # If active order canceling is disabled, do not adjust orders actively
            if not self._active_order_canceling:
                continue

            # See if I still have enough balance on my wallet to fill the order on maker market, and to hedge the
            # order on taker market. If not, adjust it.
            if not self.c_check_if_sufficient_balance(market_pair, active_order):
                continue
            # Am I still the top order on maker market? If not, re-calculate the price/size and re-submit.
            if self._current_timestamp > anti_hysteresis_timer:
                if not self.c_check_if_price_correct(market_pair, active_order, current_hedging_price):
                    need_adjust_order = True
                    continue

        # If order adjustment is needed in the next tick, set the anti-hysteresis timer s.t. the next order adjustment
        # for the same pair wouldn't happen within the time limit.
        if need_adjust_order:
            self._anti_hysteresis_timers[market_pair] = self._current_timestamp + self._anti_hysteresis_duration

        # If there's both an active bid and ask, then there's no need to think about making new limit orders.
        if has_active_bid and has_active_ask:
            return

        # If there are pending market orders, wait for them to complete
        if len(tracked_taker_orders.get(market_pair, {})) > 0:
            return

        # See if it's profitable to place a limit order on maker market.
        self.c_check_and_create_new_orders(market_pair, has_active_bid, has_active_ask)

    cdef c_did_fill_order(self, object order_filled_event):
        cdef:
            str order_id = order_filled_event.order_id
            object market_pair = self._market_pair_tracker.c_get_market_pair_from_order_id(order_id)
            tuple order_fill_record

        if market_pair is not None:
            limit_order_record = self._sb_order_tracker.c_get_shadow_limit_order(order_id)
            order_fill_record = (limit_order_record, order_filled_event)

            if order_filled_event.trade_type is TradeType.BUY:
                if market_pair not in self._order_fill_buy_events:
                    self._order_fill_buy_events[market_pair] = [order_fill_record]
                else:
                    self._order_fill_buy_events[market_pair].append(order_fill_record)

                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) Maker buy order of "
                        f"{order_filled_event.amount} {market_pair.maker.base_asset} filled."
                    )
            else:
                if market_pair not in self._order_fill_sell_events:
                    self._order_fill_sell_events[market_pair] = [order_fill_record]
                else:
                    self._order_fill_sell_events[market_pair].append(order_fill_record)

                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_FILLED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) Maker sell order of "
                        f"{order_filled_event.amount} {market_pair.maker.base_asset} filled."
                    )

            try:
                self.c_check_and_hedge_orders(market_pair)
            except Exception:
                self.log_with_clock(logging.ERROR, "Unexpected error.", exc_info=True)

    cdef c_did_complete_buy_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_pair = self._market_pair_tracker.c_get_market_pair_from_order_id(order_id)
            LimitOrder limit_order_record
            object order_type = order_completed_event.order_type

        if market_pair is not None:
            if order_type == OrderType.LIMIT:
                limit_order_record = self._sb_order_tracker.c_get_limit_order(market_pair.maker, order_id)
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Maker buy order {order_id} "
                    f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
                )
            if order_type == OrderType.MARKET:
                market_order_record = self._sb_order_tracker.c_get_market_order(market_pair.taker, order_id)
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.taker.trading_pair}) Taker buy order {order_id} for "
                    f"({market_order_record.amount} {market_order_record.base_asset} has been completely filled."
                )

    cdef c_did_complete_sell_order(self, object order_completed_event):
        cdef:
            str order_id = order_completed_event.order_id
            object market_pair = self._market_pair_tracker.c_get_market_pair_from_order_id(order_id)
            LimitOrder limit_order_record

        order_type = order_completed_event.order_type
        if market_pair is not None:
            if order_type == OrderType.LIMIT:
                limit_order_record = self._sb_order_tracker.c_get_limit_order(market_pair.maker, order_id)
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Maker sell order {order_id} "
                    f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
                )
            if order_type == OrderType.MARKET:
                market_order_record = self._sb_order_tracker.c_get_market_order(market_pair.taker, order_id)
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.taker.trading_pair}) Taker sell order {order_id} for "
                    f"({market_order_record.amount} {market_order_record.base_asset} has been completely filled."
                )

    cdef c_check_and_hedge_orders(self, object market_pair):
        cdef:
            MarketBase taker_market = market_pair.taker.market
            str taker_symbol = market_pair.taker.trading_pair
            OrderBook taker_order_book = market_pair.taker.order_book
            list buy_fill_records = self._order_fill_buy_events.get(market_pair, [])
            list sell_fill_records = self._order_fill_sell_events.get(market_pair, [])
            double buy_fill_quantity = sum([fill_event.amount for _, fill_event in buy_fill_records])
            double sell_fill_quantity = sum([fill_event.amount for _, fill_event in sell_fill_records])
            double taker_top
            double hedged_order_quantity
            double avg_fill_price

        global s_decimal_zero

        if buy_fill_quantity > 0:
            hedged_order_quantity = min(
                buy_fill_quantity,
                (taker_market.c_get_available_balance(market_pair.taker.base_asset) *
                 self._order_size_taker_balance_factor)
            )
            quantized_hedge_amount = taker_market.c_quantize_order_amount(taker_symbol, hedged_order_quantity)
            taker_top = taker_market.c_get_price(taker_symbol, False)
            avg_fill_price = (sum([r.price * r.amount for _, r in buy_fill_records]) /
                              sum([r.amount for _, r in buy_fill_records]))

            if quantized_hedge_amount > s_decimal_zero:
                self.c_sell_with_specific_market(market_pair, quantized_hedge_amount)

                del self._order_fill_buy_events[market_pair]
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_HEDGED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) Hedged maker buy order(s) of "
                        f"{buy_fill_quantity} {market_pair.maker.base_asset} on taker market to lock in profits. "
                        f"(maker avg price={avg_fill_price}, taker top={taker_top})"
                    )
            else:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Current maker buy fill amount of "
                    f"{buy_fill_quantity} {market_pair.maker.base_asset} is less than the minimum order amount "
                    f"allowed on the taker market. No hedging possible yet."
                )

        if sell_fill_quantity > 0:
            hedged_order_quantity = min(
                sell_fill_quantity,
                (taker_market.c_get_available_balance(market_pair.taker.quote_asset) /
                 taker_order_book.c_get_price_for_volume(True, sell_fill_quantity).result_price *
                 self._order_size_taker_balance_factor)
            )
            quantized_hedge_amount = taker_market.c_quantize_order_amount(taker_symbol, hedged_order_quantity)
            taker_top = taker_market.c_get_price(taker_symbol, True)
            avg_fill_price = (sum([r.price * r.amount for _, r in sell_fill_records]) /
                              sum([r.amount for _, r in sell_fill_records]))

            if quantized_hedge_amount > s_decimal_zero:
                self.c_buy_with_specific_market(market_pair, quantized_hedge_amount)

                del self._order_fill_sell_events[market_pair]
                if self._logging_options & self.OPTION_LOG_MAKER_ORDER_HEDGED:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) Hedged maker sell order(s) of "
                        f"{sell_fill_quantity} {market_pair.maker.base_asset} on taker market to lock in profits. "
                        f"(maker avg price={avg_fill_price}, taker top={taker_top})"
                    )
            else:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Current maker sell fill amount of "
                    f"{sell_fill_quantity} {market_pair.maker.base_asset} is less than the minimum order amount "
                    f"allowed on the taker market. No hedging possible yet."
                )

    cdef object c_get_adjusted_limit_order_size(self, object market_pair, double price, double original_order_size):
        cdef:
            MarketBase maker_market = market_pair.maker.market
            str symbol = market_pair.maker.trading_pair
            double adjusted_order_size

        if self._trade_size_override and self._trade_size_override > 0:
            quote_trade_size_limit = min(self._trade_size_override, original_order_size * price)
            adjusted_base_order_size = quote_trade_size_limit / price
            return maker_market.c_quantize_order_amount(symbol, adjusted_base_order_size)
        else:
            return self.c_get_order_size_after_portfolio_ratio_limit(market_pair, original_order_size)

    cdef object c_get_order_size_after_portfolio_ratio_limit(self, object market_pair, double original_order_size):
        cdef:
            MarketBase maker_market = market_pair.maker.market
            str symbol = market_pair.maker.trading_pair
            double base_balance = maker_market.c_get_balance(market_pair.maker.base_asset)
            double quote_balance = maker_market.c_get_balance(market_pair.maker.quote_asset)
            double current_price = (maker_market.c_get_price(symbol, True) +
                                    maker_market.c_get_price(symbol, False)) * 0.5
            double maker_portfolio_value = base_balance + quote_balance / current_price
            double adjusted_order_size = min(
                original_order_size,
                maker_portfolio_value * self._order_size_portfolio_ratio_limit
            )
        return maker_market.c_quantize_order_amount(symbol, adjusted_order_size)

    cdef double c_sum_flat_fees(self, str quote_currency, list flat_fees):
        """
        Converts flat fees to quote token and sums up all flat fees 
        """
        cdef:
            double total_flat_fees = 0.0
 
        for flat_fee_currency, flat_fee_amount in flat_fees:
            if flat_fee_currency == quote_currency:
                total_flat_fees += flat_fee_amount
            else:
                # if the flat fee currency symbol does not match quote symbol, convert to quote currency value
                total_flat_fees += ExchangeRateConversion.get_instance().convert_token_value(
                    amount=flat_fee_amount,
                    from_currency=flat_fee_currency,
                    to_currency=quote_currency
                )
        return total_flat_fees

    cdef double c_calculate_bid_profitability(self, object market_pair, double bid_order_size = 0.0):
        cdef:
            double maker_bid_price = (<OrderBook> market_pair.maker.order_book).c_get_price_for_quote_volume(
                False,
                0.0
            ).result_price
            double taker_bid_price = (<OrderBook> market_pair.taker.order_book).c_get_price(False)
            double maker_bid_price_adjusted = self._exchange_rate_conversion.adjust_token_rate(
                market_pair.maker.quote_asset,
                maker_bid_price
            )
            double taker_bid_price_adjusted = self._exchange_rate_conversion.adjust_token_rate(
                market_pair.taker.quote_asset,
                taker_bid_price
            )
        if bid_order_size == 0.0:
            return taker_bid_price_adjusted / maker_bid_price_adjusted - 1
        
        cdef:
            object maker_bid_fee = (<MarketBase> market_pair.maker.market).c_get_fee(
                market_pair.maker.base_asset,
                market_pair.maker.quote_asset,
                OrderType.LIMIT,
                TradeType.BUY,
                bid_order_size,
                maker_bid_price_adjusted
            )
            double maker_bid_fee_flat_fees = self.c_sum_flat_fees(
                market_pair.maker.quote_asset,
                maker_bid_fee.flat_fees
            )
            object taker_bid_fee = (<MarketBase> market_pair.taker.market).c_get_fee(
                market_pair.taker.base_asset,
                market_pair.taker.quote_asset,
                OrderType.MARKET,
                TradeType.SELL,
                bid_order_size,
                taker_bid_price_adjusted
            )
            double taker_bid_fee_flat_fees = self.c_sum_flat_fees(
                market_pair.taker.quote_asset,
                taker_bid_fee.flat_fees
            )
            double bid_net_sell_proceeds = taker_bid_price_adjusted * bid_order_size * \
                (1 - taker_bid_fee.percent) - taker_bid_fee_flat_fees
            double bid_net_buy_costs = maker_bid_price_adjusted * bid_order_size * \
                (1 + maker_bid_fee.percent) + maker_bid_fee_flat_fees
            double bid_profitability = bid_net_sell_proceeds / bid_net_buy_costs - 1
        
        return bid_profitability

    cdef double c_calculate_ask_profitability(self, object market_pair, double ask_order_size = 0.0):
        cdef:
            double maker_ask_price = (<OrderBook> market_pair.maker.order_book).c_get_price_for_quote_volume(
                True,
                0.0
            ).result_price
            double taker_ask_price = (<OrderBook> market_pair.taker.order_book).c_get_price(True)
            double maker_ask_price_adjusted = self._exchange_rate_conversion.adjust_token_rate(
                market_pair.maker.quote_asset,
                maker_ask_price
            )
            double taker_ask_price_adjusted = self._exchange_rate_conversion.adjust_token_rate(
                market_pair.taker.quote_asset,
                taker_ask_price
            )
        if ask_order_size == 0.0:
            return maker_ask_price_adjusted / taker_ask_price_adjusted - 1

        cdef:
            object maker_ask_fee = (<MarketBase> market_pair.maker.market).c_get_fee(
                market_pair.maker.base_asset,
                market_pair.maker.quote_asset,
                OrderType.LIMIT,
                TradeType.SELL,
                ask_order_size,
                maker_ask_price_adjusted
            )
            double maker_ask_fee_flat_fees = self.c_sum_flat_fees(
                market_pair.maker.quote_asset,
                maker_ask_fee.flat_fees
            )
            object taker_ask_fee = (<MarketBase> market_pair.taker.market).c_get_fee(
                market_pair.taker.base_asset,
                market_pair.taker.quote_asset,
                OrderType.MARKET,
                TradeType.BUY,
                ask_order_size,
                taker_ask_price_adjusted
            )
            double taker_ask_fee_flat_fees = self.c_sum_flat_fees(
                market_pair.taker.quote_asset,
                taker_ask_fee.flat_fees
            )
            double ask_net_sell_proceeds = maker_ask_price_adjusted * \
                ask_order_size * (1 - maker_ask_fee.percent) - maker_ask_fee_flat_fees
            double ask_net_buy_costs = taker_ask_price_adjusted * \
                ask_order_size * (1 + taker_ask_fee.percent) + taker_ask_fee_flat_fees
            double ask_profitability = ask_net_sell_proceeds / ask_net_buy_costs - 1

        return ask_profitability

    cdef tuple c_calculate_market_making_profitability(self, object market_pair):
        """
        :param market_pair: The hedging market pair.        
        :return: a (double, double) tuple. Calculates the profitability ratio of bid limit orders and ask limit orders
        """
        bid_price, bid_size_limit = self.c_get_market_making_price_and_size_limit(
            market_pair,
            True,
            own_order_depth=0
        )
        bid_order_size = float(self.c_get_adjusted_limit_order_size(
            market_pair,
            float(bid_price),
            float(bid_size_limit)
        ))
        ask_price, ask_size_limit = self.c_get_market_making_price_and_size_limit(
            market_pair,
            False,
            own_order_depth=0
        )
        ask_order_size = float(self.c_get_adjusted_limit_order_size(
            market_pair,
            float(ask_price),
            float(ask_size_limit)
        ))

        cdef:
            double bid_profitability = self.c_calculate_bid_profitability(
                market_pair,
                bid_order_size
            )
            double ask_profitability = self.c_calculate_ask_profitability(
                market_pair,
                ask_order_size
            )
        return bid_profitability, ask_profitability

    cdef tuple c_has_market_making_profit_potential(self, object market_pair):
        """
        :param market_pair: The hedging market pair.        
        :return: a (boolean, boolean) tuple. First item indicates whether bid limit order is profitable. Second item
                 indicates whether ask limit order is profitable.
        """
        bid_profitability, ask_profitability = self.c_calculate_market_making_profitability(market_pair)

        return bid_profitability > self._min_profitability, ask_profitability > self._min_profitability

    cdef tuple c_get_market_making_price_and_size_limit(self,
                                                        object market_pair,
                                                        bint is_bid,
                                                        double own_order_depth = 0):
        """
        Get the ideal market making order size and maximum order size given a market pair and a side.

        This function does a few things:
         1. Get the widest possible order price for market making on the maker market.
         2. Calculate the largest order size possible given the current balances on both maker and taker markets.
         3. Calculate the largest order size possible that's still profitable after hedging.

        The price returned is calculated from step 1. The order size returned is the minimum from 2 and 3. If either
        there's not enough balance for the maker order or the hedging trade; or if it's not possible to hedge the
        trade profitably, then the returned order size will be 0.

        :param market_pair: The cross exchange market pair to calculate order price/size limits.
        :param is_bid: Whether the order to make will be bid or ask.
        :param own_order_depth: Market depth caused by existing order issued by ourselves.
        :return: a (Decimal, Decimal) tuple. First item is price, second item is size limit.
        """
        cdef:
            MarketBase maker_market = market_pair.maker.market
            MarketBase taker_market = market_pair.taker.market
            OrderBook taker_order_book = market_pair.taker.order_book
            OrderBook maker_order_book = market_pair.maker.order_book
            double top_bid_price
            double top_ask_price
            double raw_size_limit
            double profitable_hedge_price
            double maker_balance_size_limit
            double taker_balance_size_limit
            double taker_order_book_size_limit
            double adjusted_taker_price

        # Get the top-of-order-book prices, taking the top depth tolerance into account.
        try:
            top_bid_price = maker_order_book.c_get_price_for_quote_volume(
                False, market_pair.top_depth_tolerance + own_order_depth
            ).result_price
        except EnvironmentError:
            top_bid_price = maker_order_book.c_get_price(False)

        try:
            top_ask_price = maker_order_book.c_get_price_for_quote_volume(
                True, market_pair.top_depth_tolerance + own_order_depth
            ).result_price
        except EnvironmentError:
            top_ask_price = maker_order_book.c_get_price(True)

        # Calculate the next price from the top, and the order size limit.
        if is_bid:
            price_quantum = maker_market.c_get_order_price_quantum(
                market_pair.maker.trading_pair,
                top_bid_price
            )
            next_price = (round(Decimal(top_bid_price) / price_quantum) + 1) * price_quantum

            # Calculate the order size limit from maker and taker market balances.
            maker_balance_size_limit = (maker_market.c_get_available_balance(market_pair.maker.quote_asset) /
                                        float(next_price))
            taker_balance_size_limit = (taker_market.c_get_available_balance(market_pair.taker.base_asset) *
                                        self._order_size_taker_balance_factor)

            # Convert the proposed maker order price to the equivalent price on the taker market.
            adjusted_taker_price = (self._exchange_rate_conversion.adjust_token_rate(
                market_pair.maker.quote_asset,
                float(next_price)
            ) / self._exchange_rate_conversion.adjust_token_rate(
                market_pair.taker.quote_asset,
                1.0
            ))

            # Calculate the order size limit from the minimal profitable hedge on the taker market.
            profitable_hedge_price = adjusted_taker_price * (1 + self._min_profitability)
            taker_order_book_size_limit = (
                taker_order_book.c_get_volume_for_price(False, profitable_hedge_price).result_volume *
                self._order_size_taker_volume_factor
            )

            raw_size_limit = min(
                taker_order_book_size_limit,
                maker_balance_size_limit,
                taker_balance_size_limit
            )
            size_limit = maker_market.c_quantize_order_amount(market_pair.maker.trading_pair, raw_size_limit)
            return next_price, size_limit
        else:
            price_quantum = maker_market.c_get_order_price_quantum(
                market_pair.maker.trading_pair,
                top_ask_price
            )
            next_price = (round(Decimal(top_ask_price) / price_quantum) - 1) * price_quantum

            # Calculate the order size limit from maker and taker market balances.
            maker_balance_size_limit = maker_market.c_get_available_balance(market_pair.maker.base_asset)
            taker_balance_size_limit = (taker_market.c_get_available_balance(market_pair.taker.quote_asset) /
                                        float(next_price) *
                                        self._order_size_taker_balance_factor)

            # Convert the proposed maker order price to the equivalent price on the taker market.
            adjusted_taker_price = (self._exchange_rate_conversion.adjust_token_rate(
                market_pair.maker.quote_asset,
                float(next_price)
            ) / self._exchange_rate_conversion.adjust_token_rate(
                market_pair.taker.quote_asset,
                1.0
            ))

            # Calculate the order size limit from the minimal profitable hedge on the taker market.
            profitable_hedge_price = adjusted_taker_price / (1 + self._min_profitability)
            taker_order_book_size_limit = (
                taker_order_book.c_get_volume_for_price(True, profitable_hedge_price).result_volume *
                self._order_size_taker_volume_factor
            )

            raw_size_limit = min(
                taker_order_book_size_limit,
                maker_balance_size_limit,
                taker_balance_size_limit
            )
            size_limit = maker_market.c_quantize_order_amount(market_pair.maker.trading_pair, raw_size_limit)
            return next_price, size_limit

    cdef double c_calculate_effective_hedging_price(self,
                                                    OrderBook taker_order_book,
                                                    bint is_maker_bid,
                                                    double maker_order_size) except? -1:
        cdef:
            double price_quantity_product_sum = 0
            double quantity_sum = 0
            double order_row_price = 0
            double order_row_amount = 0

        iter_func = taker_order_book.bid_entries
        if not is_maker_bid:
            iter_func = taker_order_book.ask_entries

        for order_row in iter_func():
            order_row_price = order_row.price
            order_row_amount = order_row.amount

            if quantity_sum + order_row_amount > maker_order_size:
                order_row_amount = maker_order_size - quantity_sum

            quantity_sum += order_row_amount
            price_quantity_product_sum += order_row_amount * order_row_price

            if quantity_sum >= maker_order_size:
                break

        return price_quantity_product_sum / quantity_sum

    cdef tuple c_get_suggested_price_samples(self, object market_pair):
        """
        :param market_pair: The market pair under which samples were collected for.
        :return: (bid order price samples, ask order price samples)
        """
        if market_pair in self._suggested_price_samples:
            return self._suggested_price_samples[market_pair]
        return deque(), deque()

    cdef c_take_suggested_price_sample(self, object market_pair, list active_orders):
        if ((self._last_timestamp // self.ORDER_ADJUST_SAMPLE_INTERVAL) <
                (self._current_timestamp // self.ORDER_ADJUST_SAMPLE_INTERVAL)):
            if market_pair not in self._suggested_price_samples:
                self._suggested_price_samples[market_pair] = (deque(), deque())

            own_bid_depth = float(sum([o.price * o.quantity for o in active_orders if o.is_buy is True]))
            own_ask_depth = float(sum([o.price * o.quantity for o in active_orders if o.is_buy is not True]))
            suggested_bid_price, _ = self.c_get_market_making_price_and_size_limit(
                market_pair,
                True,
                own_order_depth=own_bid_depth
            )
            suggested_ask_price, _ = self.c_get_market_making_price_and_size_limit(
                market_pair,
                False,
                own_order_depth=own_ask_depth
            )

            bid_price_samples_deque, ask_price_samples_deque = self._suggested_price_samples[market_pair]
            bid_price_samples_deque.append(suggested_bid_price)
            ask_price_samples_deque.append(suggested_ask_price)
            while len(bid_price_samples_deque) > self.ORDER_ADJUST_SAMPLE_WINDOW:
                bid_price_samples_deque.popleft()
            while len(ask_price_samples_deque) > self.ORDER_ADJUST_SAMPLE_WINDOW:
                ask_price_samples_deque.popleft()

    cdef bint c_check_if_still_profitable(self,
                                          object market_pair,
                                          LimitOrder active_order,
                                          double current_hedging_price):
        cdef:
            bint is_buy = active_order.is_buy
            str limit_order_type_str = "bid" if is_buy else "ask"
            double order_price = float(active_order.price)
            double cancel_order_threshold
            double order_price_adjusted = self._exchange_rate_conversion.adjust_token_rate(
                market_pair.taker.quote_asset, float(active_order.price))
            double current_hedging_price_adjusted = self._exchange_rate_conversion.adjust_token_rate(
                market_pair.taker.quote_asset, current_hedging_price)

        # If active order canceling is disabled, only cancel order when the profitability goes below
        # cancel_order_threshold
        if self._active_order_canceling:
            cancel_order_threshold = self._min_profitability
        else:
            cancel_order_threshold = self._cancel_order_threshold

        if ((is_buy and current_hedging_price_adjusted < order_price_adjusted * (1 + cancel_order_threshold)) or
                (not is_buy and order_price_adjusted < current_hedging_price_adjusted * (1 + cancel_order_threshold))):
            if self._logging_options & self.OPTION_LOG_REMOVING_ORDER:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Limit {limit_order_type_str} order at "
                    f"{order_price:.8g} {market_pair.maker.quote_asset} is no longer profitable. "
                    f"Removing the order."
                )
            self.c_cancel_order(market_pair, active_order.client_order_id)
            return False
        return True

    cdef bint c_check_if_sufficient_balance(self, object market_pair, LimitOrder active_order):
        cdef:
            bint is_buy = active_order.is_buy
            double order_price = float(active_order.price)
            MarketBase maker_market = market_pair.maker.market
            MarketBase taker_market = market_pair.taker.market
            double quote_asset_amount = maker_market.c_get_balance(market_pair.maker.quote_asset) if is_buy else \
                taker_market.c_get_balance(market_pair.taker.quote_asset)
            double base_asset_amount = taker_market.c_get_balance(market_pair.taker.base_asset) if is_buy else \
                maker_market.c_get_balance(market_pair.maker.base_asset)
            double order_size_limit

        order_size_limit = min(base_asset_amount, quote_asset_amount / order_price)
        quantized_size_limit = maker_market.c_quantize_order_amount(active_order.symbol, order_size_limit)

        if active_order.quantity > quantized_size_limit:
            if self._logging_options & self.OPTION_LOG_ADJUST_ORDER:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Order size limit ({order_size_limit:.8g}) "
                    f"is now less than the current active order amount ({active_order.quantity:.8g}). "
                    f"Going to adjust the order."
                )
            self.c_cancel_order(market_pair, active_order.client_order_id)
            return False
        return True

    cdef bint c_check_if_price_correct(self, object market_pair, LimitOrder active_order, double current_hedging_price):
        cdef:
            bint is_buy = active_order.is_buy
            double order_price = float(active_order.price)
            double order_quantity = float(active_order.quantity)
            MarketBase maker_market = market_pair.maker.market
            MarketBase taker_market = market_pair.taker.market
            OrderBook maker_order_book = market_pair.maker.order_book
            OrderBook taker_order_book = market_pair.taker.order_book
            double top_depth_tolerance = market_pair.top_depth_tolerance
            bint should_adjust_buy = False
            bint should_adjust_sell = False

        price_quantum = maker_market.c_get_order_price_quantum(
            market_pair.maker.trading_pair,
            order_price
        )
        bid_price_samples, ask_price_samples = self.c_get_suggested_price_samples(market_pair)

        if is_buy:
            above_price = order_price + float(price_quantum)
            above_quote_volume = maker_order_book.c_get_quote_volume_for_price(False, above_price).result_volume
            suggested_price, order_size_limit = self.c_get_market_making_price_and_size_limit(
                market_pair,
                True,
                own_order_depth=order_price * order_quantity
            )

            # Incorporate the past bid price samples.
            top_ask_price = maker_order_book.c_get_price(True)
            suggested_price = max([suggested_price] +
                                  [p for p in bid_price_samples
                                   if float(p) < top_ask_price])

            if suggested_price < active_order.price:
                if self._logging_options & self.OPTION_LOG_ADJUST_ORDER:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) The current limit bid order for "
                        f"{active_order.quantity} {market_pair.maker.base_asset} at "
                        f"{order_price:.8g} {market_pair.maker.quote_asset} is now above the suggested order "
                        f"price at {suggested_price}. Going to cancel the old order and create a new one..."
                    )
                should_adjust_buy = True
            elif suggested_price > active_order.price:
                if self._logging_options & self.OPTION_LOG_ADJUST_ORDER:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) The current limit bid order for "
                        f"{active_order.quantity} {market_pair.maker.base_asset} at "
                        f"{order_price:.8g} {market_pair.maker.quote_asset} is now below the suggested order "
                        f"price at {suggested_price}. Going to cancel the old order and create a new one..."
                    )
                should_adjust_buy = True

            if should_adjust_buy:
                self.c_cancel_order(market_pair, active_order.client_order_id)
                self.log_with_clock(logging.DEBUG,
                                    f"Current buy order price={order_price}, "
                                    f"above quote depth={above_quote_volume}, "
                                    f"suggested order price={suggested_price}")
                return False
        else:
            above_price = order_price - float(price_quantum)
            above_quote_volume = maker_order_book.c_get_quote_volume_for_price(True, above_price).result_volume
            suggested_price, order_size_limit = self.c_get_market_making_price_and_size_limit(
                market_pair,
                False,
                own_order_depth=order_price * order_quantity
            )

            # Incorporate the past ask price samples.
            top_bid_price = maker_order_book.c_get_price(False)
            suggested_price = min([suggested_price] +
                                  [p for p in ask_price_samples
                                   if float(p) > top_bid_price])

            if suggested_price > active_order.price:
                if self._logging_options & self.OPTION_LOG_ADJUST_ORDER:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) The current limit ask order for "
                        f"{active_order.quantity} {market_pair.maker.base_asset} at "
                        f"{order_price:.8g} {market_pair.maker.quote_asset} is now below the suggested order "
                        f"price at {suggested_price}. Going to cancel the old order and create a new one..."
                    )
                should_adjust_sell = True
            elif suggested_price < active_order.price:
                if self._logging_options & self.OPTION_LOG_ADJUST_ORDER:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) The current limit ask order for "
                        f"{active_order.quantity} {market_pair.maker.base_asset} at "
                        f"{order_price:.8g} {market_pair.maker.quote_asset} is now above the suggested order "
                        f"price at {suggested_price}. Going to cancel the old order and create a new one..."
                    )
                should_adjust_sell = True

            if should_adjust_sell:
                self.c_cancel_order(market_pair, active_order.client_order_id)
                self.log_with_clock(logging.DEBUG,
                                    f"Current sell order price={order_price}, "
                                    f"above quote depth={above_quote_volume}, "
                                    f"suggested order price={suggested_price}")
                return False
        return True

    cdef c_check_and_create_new_orders(self, object market_pair, bint has_active_bid, bint has_active_ask):
        cdef:
            double effective_hedging_price

        # See if it's profitable to place a limit order on maker market.
        is_bid_profitable, is_ask_profitable = self.c_has_market_making_profit_potential(market_pair)
        bid_price_samples, ask_price_samples = self.c_get_suggested_price_samples(market_pair)

        if is_bid_profitable and not has_active_bid:
            bid_price, bid_size_limit = self.c_get_market_making_price_and_size_limit(
                market_pair,
                True,
                own_order_depth=0
            )
            bid_size = self.c_get_adjusted_limit_order_size(
                market_pair,
                float(bid_price),
                float(bid_size_limit)
            )
            if bid_size > s_decimal_zero:
                effective_hedging_price = self.c_calculate_effective_hedging_price(
                    market_pair.taker.order_book,
                    True,
                    float(bid_size)
                )
                effective_hedging_price_adjusted = self._exchange_rate_conversion.adjust_token_rate(
                    market_pair.taker.quote_asset, effective_hedging_price
                )
                if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) Creating limit bid order for "
                        f"{bid_size} {market_pair.maker.base_asset} at "
                        f"{bid_price} {market_pair.maker.quote_asset}. "
                        f"Current hedging price: {effective_hedging_price} {market_pair.taker.quote_asset} "
                        f"(Rate adjusted: {effective_hedging_price_adjusted:.2f} {market_pair.taker.quote_asset})."
                    )
                self.c_buy_with_specific_market(
                    market_pair,
                    bid_size,
                    order_type=OrderType.LIMIT,
                    price=bid_price
                )
            else:
                if self._logging_options & self.OPTION_LOG_NULL_ORDER_SIZE:
                    self.log_with_clock(
                        logging.WARNING,
                        f"({market_pair.maker.trading_pair}) Attempting to place a limit bid but the "
                        f"bid size limit is 0. Skipping."
                    )
        if is_ask_profitable and not has_active_ask:
            ask_price, ask_size_limit = self.c_get_market_making_price_and_size_limit(
                market_pair,
                False,
                own_order_depth=0
            )
            ask_size = self.c_get_adjusted_limit_order_size(
                market_pair,
                float(ask_price),
                float(ask_size_limit)
            )
            if ask_size > s_decimal_zero:
                effective_hedging_price = self.c_calculate_effective_hedging_price(
                    market_pair.taker.order_book,
                    False,
                    float(ask_size)
                )
                effective_hedging_price_adjusted = self._exchange_rate_conversion.adjust_token_rate(
                    market_pair.maker.quote_asset, effective_hedging_price
                )
                if self._logging_options & self.OPTION_LOG_CREATE_ORDER:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) Creating limit ask order for "
                        f"{ask_size} {market_pair.maker.base_asset} at "
                        f"{ask_price} {market_pair.maker.quote_asset}. "
                        f"Current hedging price: {effective_hedging_price} {market_pair.maker.quote_asset} "
                        f"(Rate adjusted: {effective_hedging_price_adjusted:.2f} {market_pair.maker.quote_asset})."
                    )
                self.c_sell_with_specific_market(
                    market_pair,
                    ask_size,
                    order_type=OrderType.LIMIT,
                    price=ask_price
                )
            else:
                if self._logging_options & self.OPTION_LOG_NULL_ORDER_SIZE:
                    self.log_with_clock(
                        logging.WARNING,
                        f"({market_pair.maker.trading_pair}) Attempting to place a limit ask but the "
                        f"ask size limit is 0. Skipping."
                    )

    # <editor-fold desc="+ Creating and cancelling orders">
    # Override the default buy, sell and cancel functions to allow the use of XEMM market pair, and the correct
    # attribution of trades to XEMM market pairs.
    # ----------------------------------------------------------------------------------------------------------
    cdef str c_buy_with_specific_market(self, object market_pair, object amount,
                                    object order_type = OrderType.MARKET,
                                    object price = s_decimal_nan,
                                    double expiration_seconds = NaN):
        if not isinstance(market_pair, CrossExchangeMarketPair):
            raise TypeError("market_pair must be a CrossExchangeMarketPair.")

        market_symbol_pair = market_pair.maker if order_type is OrderType.LIMIT else market_pair.taker

        cdef:
            str order_id = StrategyBase.c_buy_with_specific_market(self, market_symbol_pair, amount,
                                                                   order_type=order_type, price=price,
                                                                   expiration_seconds=expiration_seconds)
        self._market_pair_tracker.c_start_tracking_order_id(order_id, market_pair)
        return order_id

    cdef str c_sell_with_specific_market(self, object market_pair, object amount,
                                         object order_type = OrderType.MARKET,
                                         object price = s_decimal_nan,
                                         double expiration_seconds = NaN):
        if not isinstance(market_pair, CrossExchangeMarketPair):
            raise TypeError("market_pair must be a CrossExchangeMarketPair.")

        market_symbol_pair = market_pair.maker if order_type is OrderType.LIMIT else market_pair.taker

        cdef:
            str order_id = StrategyBase.c_sell_with_specific_market(self, market_symbol_pair, amount,
                                                                    order_type=order_type, price=price,
                                                                    expiration_seconds=expiration_seconds)
        self._market_pair_tracker.c_start_tracking_order_id(order_id, market_pair)
        return order_id

    cdef c_cancel_order(self, object market_pair, str order_id):
        market_symbol_pair = self._sb_order_tracker.c_get_market_pair_from_order_id(order_id)
        StrategyBase.c_cancel_order(self, market_symbol_pair, order_id)
    # ----------------------------------------------------------------------------------------------------------
    # </editor-fold>

    # <editor-fold desc="+ Order tracking entry points">
    # Override the stop tracking entry points to include the market pair tracker as well.
    # ----------------------------------------------------------------------------------------------------------
    cdef c_stop_tracking_limit_order(self, object market_symbol_pair, str order_id):
        self._market_pair_tracker.c_stop_tracking_order_id(order_id)
        StrategyBase.c_stop_tracking_limit_order(self, market_symbol_pair, order_id)

    cdef c_stop_tracking_market_order(self, object market_symbol_pair, str order_id):
        self._market_pair_tracker.c_stop_tracking_order_id(order_id)
        StrategyBase.c_stop_tracking_market_order(self, market_symbol_pair, order_id)
    # ----------------------------------------------------------------------------------------------------------
    # </editor-fold>
