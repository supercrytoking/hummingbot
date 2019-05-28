# distutils: language=c++

from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class ArbitrageStrategy(StrategyBase):
    cdef:
        list _market_pairs
        bint _all_markets_ready
        dict _order_id_to_market
        dict _tracked_taker_orders
        double _min_profitability
        double _max_order_size
        double _min_order_size
        double _status_report_interval
        double _last_timestamp
        dict _last_trade_timestamps
        double _next_trade_delay
        EventListener _buy_order_completed_listener
        EventListener _sell_order_completed_listener
        EventListener _order_failed_listener
        EventListener _order_canceled_listener
        set _markets
        set _sell_markets
        set _buy_markets
        int64_t _logging_options
        object _exchange_rate_conversion

    cdef c_buy_with_specific_market(self, object market_symbol_pair, double amount,
                                    object order_type = *, double price = *)
    cdef c_sell_with_specific_market(self, object market_symbol_pair, double amount,
                                     object order_type = *, double price = *)
    cdef c_did_complete_buy_order(self, object buy_order_completed_event)
    cdef c_did_complete_sell_order(self, object sell_order_completed_event)
    cdef c_did_fail_order(self, object fail_event)
    cdef c_did_cancel_order(self, object cancel_event)
    cdef tuple c_calculate_arbitrage_top_order_profitability(self, object market_pair)
    cdef c_process_market_pair(self, object market_pair)
    cdef c_process_market_pair_inner(self, object buy_market_symbol_pair,object sell_market_symbol_pair)
    cdef tuple c_find_best_profitable_amount(self, object buy_market_symbol_pair, object sell_market_symbol_pair)
    cdef c_ready_for_new_orders(self, list market_symbol_pairs)
    cdef c_start_tracking_market_order(self, object market_symbol_pair, str order_id, bint is_buy, object quantity)
    cdef c_stop_tracking_market_order(self, str order_id)


cdef list c_find_profitable_arbitrage_orders(double min_profitability,
                                             OrderBook buy_order_book,
                                             OrderBook sell_order_book,
                                             str buy_market_quote_currency,
                                             str sell_market_quote_currency)
