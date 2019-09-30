from decimal import Decimal

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import MarketBase
from .data_types import PricingProposal
from .pure_market_making_v2 cimport PureMarketMakingStrategyV2


cdef class ConstantSpreadPricingDelegate(OrderPricingDelegate):
    def __init__(self, bid_spread: Decimal, ask_spread: Decimal):
        super().__init__()
        self._bid_spread = bid_spread
        self._ask_spread = ask_spread

    @property
    def bid_spread(self) -> Decimal:
        return self._bid_spread

    @property
    def ask_spread(self) -> Decimal:
        return self._ask_spread

    cdef object c_get_order_price_proposal(self,
                                           PureMarketMakingStrategyV2 strategy,
                                           object market_info,
                                           list active_orders):
        cdef:
            MarketBase maker_market = market_info.market
            object top_bid_price = market_info.get_price(False)
            object top_ask_price = market_info.get_price(True)
            str market_name = maker_market.name
            object mid_price = (top_bid_price + top_ask_price) * Decimal("0.5")
            object bid_price = mid_price * (1 - self._bid_spread)
            object ask_price = mid_price * (1 + self._ask_spread)

        return PricingProposal([maker_market.c_quantize_order_price(market_info.trading_pair, bid_price)],
                               [maker_market.c_quantize_order_price(market_info.trading_pair, ask_price)])
