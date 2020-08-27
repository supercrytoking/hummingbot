from hummingbot.core.event.event_reporter cimport EventReporter
from hummingbot.core.event.event_logger cimport EventLogger
from hummingbot.core.network_iterator cimport NetworkIterator

cdef class ConnectorBase(NetworkIterator):
    cdef:
        EventReporter _event_reporter
        EventLogger _event_logger
        public dict _account_available_balances
        public dict _account_balances
        dict _balance_limits
        dict _fee_estimates
        public bint _trading_required
        public bint _real_time_balance_update
        public dict _in_flight_orders_snapshot
        public double _in_flight_orders_snapshot_timestamp

    cdef str c_buy(self, str trading_pair, object amount, object order_type=*, object price=*, dict kwargs=*)
    cdef str c_sell(self, str trading_pair, object amount, object order_type=*, object price=*, dict kwargs=*)
    cdef c_cancel(self, str trading_pair, str client_order_id)
    cdef c_stop_tracking_order(self, str order_id)
    cdef object c_get_balance(self, str currency)
    cdef object c_get_available_balance(self, str currency)
    cdef object c_get_price(self, str trading_pair, bint is_buy)
    cdef object c_get_order_price_quantum(self, str trading_pair, object price)
    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size)
    cdef object c_quantize_order_price(self, str trading_pair, object price)
    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=*)
