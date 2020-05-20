from hummingbot.market.market_base cimport MarketBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class BitcoinComMarket(MarketBase):
    cdef:
        object _user_stream_tracker
        object _bitcoin_com_auth
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _last_order_update_timestamp
        double _poll_interval
        dict _in_flight_orders
        TransactionTracker _tx_tracker
        dict _trading_rules
        dict _trade_fees
        dict _withdraw_fees
        object _data_source_type
        object _coro_queue
        public object _status_polling_task
        public object _coro_scheduler_task
        public object _user_stream_tracker_task
        public object _user_stream_event_listener_task
        public object _trading_rules_polling_task
        public object _withdraw_fees_polling_task
        public object _shared_client

    cdef c_start_tracking_order(self,
                                str order_id,
                                str symbol,
                                object trade_type,
                                object order_type,
                                object price,
                                object amount)
    cdef c_did_timeout_tx(self, str tracking_id)
