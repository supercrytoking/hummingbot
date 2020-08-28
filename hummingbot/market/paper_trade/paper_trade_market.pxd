from libcpp.set cimport set as cpp_set
from libcpp.string cimport string
from libcpp.unordered_map cimport unordered_map
from libcpp.utility cimport pair

from hummingbot.core.data_type.LimitOrder cimport LimitOrder as CPPLimitOrder
from hummingbot.core.data_type.OrderExpirationEntry cimport OrderExpirationEntry as CPPOrderExpirationEntry
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.market.market_base cimport MarketBase
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.event.events import MarketEvent, OrderType

from .market_config import (
    MarketConfig,
    AssetType
)
ctypedef cpp_set[CPPLimitOrder] SingleTradingPairLimitOrders
ctypedef unordered_map[string, SingleTradingPairLimitOrders].iterator LimitOrdersIterator
ctypedef pair[string, SingleTradingPairLimitOrders] LimitOrdersPair
ctypedef unordered_map[string, SingleTradingPairLimitOrders] LimitOrders
ctypedef cpp_set[CPPLimitOrder].iterator SingleTradingPairLimitOrdersIterator
ctypedef cpp_set[CPPLimitOrder].reverse_iterator SingleTradingPairLimitOrdersRIterator
ctypedef cpp_set[CPPOrderExpirationEntry] LimitOrderExpirationSet
ctypedef cpp_set[CPPOrderExpirationEntry].iterator LimitOrderExpirationSetIterator


cdef class PaperTradeMarket(MarketBase):
    cdef:
        LimitOrders _bid_limit_orders
        LimitOrders _ask_limit_orders
        bint _paper_trade_market_initialized
        dict _trading_pairs
        object _config
        object _queued_orders
        dict _quantization_params
        object _order_book_trade_listener
        object _market_order_filled_listener
        LimitOrderExpirationSet _limit_order_expiration_set
        object _target_market

    cdef c_execute_buy(self, str order_id, str trading_pair, object amount)
    cdef c_execute_sell(self, str order_id, str trading_pair, object amount)
    cdef c_process_market_orders(self)
    cdef c_set_balance(self, str currency, object amount)
    cdef object c_get_fee(self,
                          str base_asset,
                          str quote_asset,
                          object order_type,
                          object order_side,
                          object amount,
                          object price)
    cdef c_delete_limit_order(self,
                              LimitOrders *limit_orders_map_ptr,
                              LimitOrdersIterator *map_it_ptr,
                              const SingleTradingPairLimitOrdersIterator orders_it)
    cdef c_process_limit_order(self,
                               bint is_buy,
                               LimitOrders *limit_orders_map_ptr,
                               LimitOrdersIterator *map_it_ptr,
                               SingleTradingPairLimitOrdersIterator orders_it)
    cdef c_process_limit_bid_order(self,
                                   LimitOrders *limit_orders_map_ptr,
                                   LimitOrdersIterator *map_it_ptr,
                                   SingleTradingPairLimitOrdersIterator orders_it)
    cdef c_process_limit_ask_order(self,
                                   LimitOrders *limit_orders_map_ptr,
                                   LimitOrdersIterator *map_it_ptr,
                                   SingleTradingPairLimitOrdersIterator orders_it)
    cdef c_process_crossed_limit_orders_for_trading_pair(self,
                                                         bint is_buy,
                                                         LimitOrders *limit_orders_map_ptr,
                                                         LimitOrdersIterator *map_it_ptr)
    cdef c_process_crossed_limit_orders(self)
    cdef c_match_trade_to_limit_orders(self, object order_book_trade_event)
    cdef object c_cancel_order_from_orders_map(self,
                                               LimitOrders *orders_map,
                                               str trading_pair_str,
                                               bint cancel_all=*,
                                               str client_order_id=*)
