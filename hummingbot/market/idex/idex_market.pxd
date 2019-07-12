from hummingbot.market.market_base cimport MarketBase
from hummingbot.core.data_type.transaction_tracker cimport TransactionTracker


cdef class IDEXMarket(MarketBase):
    cdef:
        object _shared_client
        object _wallet
        object _order_book_tracker
        dict _account_balances
        dict _account_available_balances
        object _ev_loop
        object _poll_notifier
        double _last_timestamp
        double _last_update_balances_timestamp
        double _last_update_order_timestamp
        double _last_update_asset_info_timestamp
        double _last_update_next_nonce_timestamp
        double _last_update_contract_address_timestamp
        double _poll_interval
        dict _in_flight_orders
        object _in_flight_cancels
        object _order_expiry_queue
        object _order_expiry_set
        TransactionTracker _tx_tracker
        object _w3
        public object _status_polling_task
        public object _order_tracker_task
        public object _approval_tx_polling_task
        object _api_response_records
        object _assets_info
        object _next_nonce
        object _contract_address
        object _async_scheduler

    cdef c_start_tracking_order(self,
                                str order_id,
                                str symbol,
                                object trade_type,
                                object order_type,
                                object amount,
                                object price)
    cdef c_expire_order(self, str order_id)
    cdef c_check_and_remove_expired_orders(self)
    cdef c_stop_tracking_order(self, str order_id)
