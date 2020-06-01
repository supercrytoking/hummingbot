# distutils: language=c++

from libc.stdint cimport int64_t
from hummingbot.strategy.strategy_base cimport StrategyBase


cdef class PureMarketMakingStrategyV3(StrategyBase):
    cdef:
        object _market_info

        object _bid_spread
        object _ask_spread
        object _order_amount
        int _order_levels
        int _buy_levels
        int _sell_levels
        object _order_level_spread
        object _order_level_amount
        double _order_refresh_time
        object _order_refresh_tolerance_pct
        double _filled_order_delay
        bint _inventory_skew_enabled
        object _inventory_target_base_pct
        object _inventory_range_multiplier
        bint _hanging_orders_enabled
        object _hanging_orders_cancel_pct
        bint _order_optimization_enabled
        object _order_optimization_depth
        bint _add_transaction_costs_to_orders
        object _asset_price_delegate
        object _price_ceiling
        object _price_floor
        bint _ping_pong_enabled

        double _cancel_timestamp
        double _create_timestamp
        object _limit_order_type
        bint _all_markets_ready
        double _expiration_seconds
        int _filled_buys_sells_balance
        list _hanging_order_ids
        double _last_timestamp
        double _status_report_interval
        int64_t _logging_options

    cdef c_set_buy_sell_levels(self)
    cdef c_apply_price_band(self)
    cdef c_apply_ping_pong(self)
    cdef object c_create_base_proposal(self)
    cdef object c_apply_order_price_modifiers(self, object proposal)
    cdef object c_apply_order_size_modifiers(self, object proposal)
    cdef object c_apply_inventory_skew(self, object proposal)
    cdef object c_filter_proposal_for_takers(self, object proposal)
    cdef object c_apply_order_optimization(self, object proposal)
    cdef object c_apply_add_transaction_costs(self, object proposal)
    cdef bint c_is_within_tolerance(self, list current_prices, list proposal_prices)
    cdef c_cancel_active_orders(self, object proposal)
    cdef c_cancel_hanging_orders(self)
    cdef bint c_to_create_orders(self, object proposal)
    cdef c_execute_orders_proposal(self, object proposal)
    cdef set_timers(self)
