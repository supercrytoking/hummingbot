# distutils: language=c++

from libc.stdint cimport int64_t
from hummingbot.strategy.strategy_base cimport StrategyBase


cdef class AvellanedaMarketMakingStrategy(StrategyBase):
    cdef:
        object _market_info
        object _minimum_spread
        object _order_amount
        double _order_refresh_time
        double _max_order_age
        object _order_refresh_tolerance_pct
        double _filled_order_delay
        object _inventory_target_base_pct
        bint _order_optimization_enabled
        bint _add_transaction_costs_to_orders
        bint _hb_app_notification
        bint _is_debug

        double _cancel_timestamp
        double _create_timestamp
        object _limit_order_type
        bint _all_markets_ready
        int _filled_buys_balance
        int _filled_sells_balance
        double _last_timestamp
        double _status_report_interval
        int64_t _logging_options
        object _last_own_trade_price
        int _volatility_sampling_period
        double _last_sampling_timestamp
        bint _parameters_based_on_spread
        int _ticks_to_be_ready
        object _min_spread
        object _max_spread
        object _vol_to_spread_multiplier
        object _volatility_sensibility
        object _inventory_risk_aversion
        object _kappa
        object _gamma
        object _eta
        object _closing_time
        object _time_left
        object _q_adjustment_factor
        object _reserved_price
        object _optimal_spread
        object _optimal_bid
        object _optimal_ask
        object _latest_parameter_calculation_vol
        str _debug_csv_path
        object _avg_vol

    cdef object c_get_mid_price(self)
    cdef object c_create_base_proposal(self)
    cdef tuple c_get_adjusted_available_balance(self, list orders)
    cdef c_apply_order_price_modifiers(self, object proposal)
    cdef c_apply_order_amount_eta_transformation(self, object proposal)
    cdef c_apply_budget_constraint(self, object proposal)
    cdef c_apply_order_optimization(self, object proposal)
    cdef c_apply_add_transaction_costs(self, object proposal)
    cdef bint c_is_within_tolerance(self, list current_prices, list proposal_prices)
    cdef c_cancel_active_orders(self, object proposal)
    cdef c_aged_order_refresh(self)
    cdef bint c_to_create_orders(self, object proposal)
    cdef c_execute_orders_proposal(self, object proposal)
    cdef set_timers(self)
    cdef double c_get_spread(self)
    cdef c_collect_market_variables(self, double timestamp)
    cdef bint c_is_algorithm_ready(self)
    cdef c_calculate_reserved_price_and_optimal_spread(self)
    cdef object c_calculate_target_inventory(self)
    cdef c_recalculate_parameters(self)
