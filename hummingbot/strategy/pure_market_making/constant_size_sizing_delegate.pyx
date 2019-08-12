from decimal import Decimal
import logging

from hummingbot.market.market_base cimport MarketBase
from hummingbot.market.market_base import MarketBase
from hummingbot.core.event.events import (
    TradeType,
    OrderType
)
from hummingbot.logger import HummingbotLogger

from .data_types import SizingProposal
from .pure_market_making_v2 cimport PureMarketMakingStrategyV2

s_logger = None
s_decimal_0 = Decimal(0)

cdef class ConstantSizeSizingDelegate(OrderSizingDelegate):

    def __init__(self, order_size: float):
        super().__init__()
        self._order_size = order_size
        self._log_warning_order_size = True
        self._log_warning_balance = True

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    @property
    def order_size(self) -> float:
        return self._order_size

    cdef object c_get_order_size_proposal(self,
                                          PureMarketMakingStrategyV2 strategy,
                                          object market_info,
                                          list active_orders,
                                          object pricing_proposal):
        cdef:
            MarketBase market = market_info.market
            object buy_fees
            double base_asset_balance = market.c_get_available_balance(market_info.base_asset)
            double quote_asset_balance = market.c_get_available_balance(market_info.quote_asset)
            object bid_order_size = self._order_size
            object ask_order_size = self._order_size
            object quantized_bid_order_size
            object quantized_ask_order_size
            bint has_active_bid = False
            bint has_active_ask = False
            double required_quote_asset_balance

        for active_order in active_orders:
            if active_order.is_buy:
                has_active_bid = True
                quote_asset_balance += float(active_order.quantity) * float(active_order.price)
            else:
                has_active_ask = True
                base_asset_balance += float(active_order.quantity)

        if market.name == "binance":
            quantized_bid_order_size = market.c_quantize_order_amount(market_info.trading_pair,
                                                                      float(bid_order_size),
                                                                      pricing_proposal.buy_order_prices[0])
            quantized_ask_order_size = market.c_quantize_order_amount(market_info.trading_pair,
                                                                      float(ask_order_size),
                                                                      pricing_proposal.sell_order_prices[0])
            required_quote_asset_balance = float(pricing_proposal.buy_order_prices[0]) * float(quantized_bid_order_size)

        else:
            quantized_bid_order_size = market.c_quantize_order_amount(market_info.trading_pair,
                                                                      float(bid_order_size))
            quantized_ask_order_size = market.c_quantize_order_amount(market_info.trading_pair,
                                                                      float(ask_order_size))

            buy_fees = market.c_get_fee(market_info.base_asset, market_info.quote_asset,
                                        OrderType.MARKET, TradeType.BUY,
                                        quantized_bid_order_size, pricing_proposal.buy_order_prices[0])

            required_quote_asset_balance = (float(pricing_proposal.buy_order_prices[0]) *
                                            (1.0 + float(buy_fees.percent)) *
                                            float(quantized_bid_order_size))

        if self._log_warning_order_size:
            if quantized_bid_order_size == s_decimal_0:
                self.logger().network(f"Buy(bid) order size is less than minimum order size. Buy order will not be placed",
                                      f"The order size is too small for the market for buy order. Check order size in configuration.")
                # After warning once, set warning flag to False
                self._log_warning_order_size = False

            if quantized_ask_order_size == s_decimal_0:
                 self.logger().network(f"Sell(ask) order size is less than minimum order size. Sell order will not be placed",
                                       f"The order size is too small for the market for sell order. Check order size in configuration.")
                 # After warning once, set warning flag to False
                 self._log_warning_order_size = False

        if self._log_warning_balance:
            if quote_asset_balance < required_quote_asset_balance:
                self.logger().network(f"Buy(bid) order is not placed because there is not enough Quote asset. "
                                      f"Quote Asset: {quote_asset_balance}, Price: {pricing_proposal.buy_order_prices[0]},"
                                      f"Size: {quantized_bid_order_size}",
                                      f"Not enough asset to place the required buy(bid) order. Check balances.")
                # After warning once, set warning flag to False
                self._log_warning_balance = False

            if base_asset_balance < quantized_ask_order_size:
                self.logger().network(f"Sell(ask) order is not placed because there is not enough Base asset. "
                                      f"Base Asset: {base_asset_balance}, Size: {quantized_ask_order_size}",
                                      f"Not enough asset to place the required sell(ask) order. Check balances.")
                # After warning once, set warning flag to False
                self._log_warning_balance = False


        # Reset warning flag for balances if there is enough balance to place orders
        if (quote_asset_balance >= required_quote_asset_balance) and \
                (base_asset_balance >= quantized_ask_order_size):
            self._log_warning_balance = True

        # Reset warning flag for order size if both order sizes are greater than zero
        if quantized_bid_order_size > 0 and quantized_ask_order_size > 0:
            self._log_warning_order_size = True

        return SizingProposal(
            ([quantized_bid_order_size]
             if quote_asset_balance >= required_quote_asset_balance and not has_active_bid
             else [s_decimal_0]),
            ([quantized_ask_order_size]
             if base_asset_balance >= quantized_ask_order_size and not has_active_ask else
             [s_decimal_0])
        )
