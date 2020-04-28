from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.pure_market_making import (
    PureMarketMakingStrategyV2,
    ConstantSpreadPricingDelegate,
    ConstantMultipleSpreadPricingDelegate,
    ConstantSizeSizingDelegate,
    StaggeredMultipleSizeSizingDelegate,
    InventorySkewSingleSizeSizingDelegate,
    InventorySkewMultipleSizeSizingDelegate,
    PassThroughFilterDelegate,
    OrderBookAssetPriceDelegate,
    APIAssetPriceDelegate
)
from hummingbot.strategy.pure_market_making.pure_market_making_config_map import pure_market_making_config_map as c_map
from hummingbot.market.paper_trade import create_paper_trade_market
from hummingbot.market.market_base import MarketBase
from decimal import Decimal


def start(self):
    try:
        order_amount = c_map.get("order_amount").value
        order_refresh_time = c_map.get("order_refresh_time").value
        bid_spread = c_map.get("bid_spread").value / Decimal('100')
        ask_spread = c_map.get("ask_spread").value / Decimal('100')
        order_expiration_time = c_map.get("order_expiration_time").value
        order_levels = c_map.get("order_levels").value
        order_level_amount = c_map.get("order_level_amount").value
        order_level_spread = c_map.get("order_level_spread").value / Decimal('100')
        exchange = c_map.get("exchange").value.lower()
        raw_trading_pair = c_map.get("market").value
        inventory_skew_enabled = c_map.get("inventory_skew_enabled").value
        inventory_target_base_pct = 0 if c_map.get("inventory_target_base_pct").value is None else \
            c_map.get("inventory_target_base_pct").value / Decimal('100')
        inventory_range_multiplier = c_map.get("inventory_range_multiplier").value
        filled_order_delay = c_map.get("filled_order_delay").value
        hanging_orders_enabled = c_map.get("hanging_orders_enabled").value
        hanging_orders_cancel_pct = c_map.get("hanging_orders_cancel_pct").value / Decimal('100')
        order_optimization_enabled = c_map.get("order_optimization_enabled").value
        order_optimization_depth = c_map.get("order_optimization_depth").value
        add_transaction_costs_to_orders = c_map.get("add_transaction_costs").value
        price_source_enabled = c_map.get("price_source_enabled").value
        price_source_type = c_map.get("price_source_type").value
        price_source_exchange = c_map.get("price_source_exchange").value
        price_source_market = c_map.get("price_source_market").value
        price_source_custom = c_map.get("price_source_custom").value
        order_refresh_tolerance_enabled = c_map.get("order_refresh_tolerance_enabled").value
        order_refresh_tolerance_spread = -1.0 if not order_refresh_tolerance_enabled else \
            c_map.get("order_refresh_tolerance_spread").value / Decimal('100')

        pricing_delegate = None
        sizing_delegate = None
        filter_delegate = PassThroughFilterDelegate()

        if order_levels > 1:
            pricing_delegate = ConstantMultipleSpreadPricingDelegate(bid_spread,
                                                                     ask_spread,
                                                                     order_level_spread,
                                                                     order_levels)
            if inventory_skew_enabled:
                sizing_delegate = InventorySkewMultipleSizeSizingDelegate(order_amount,
                                                                          order_level_amount,
                                                                          order_levels,
                                                                          inventory_target_base_pct,
                                                                          inventory_range_multiplier)
            else:
                sizing_delegate = StaggeredMultipleSizeSizingDelegate(order_amount,
                                                                      order_level_amount,
                                                                      order_levels)
        else:  # mode == "single"
            pricing_delegate = ConstantSpreadPricingDelegate(bid_spread,
                                                             ask_spread)
            if inventory_skew_enabled:
                sizing_delegate = InventorySkewSingleSizeSizingDelegate(order_amount,
                                                                        inventory_target_base_pct,
                                                                        inventory_range_multiplier)
            else:
                sizing_delegate = ConstantSizeSizingDelegate(order_amount)
        try:
            trading_pair: str = self._convert_to_exchange_trading_pair(exchange, [raw_trading_pair])[0]
            maker_assets: Tuple[str, str] = self._initialize_market_assets(exchange, [trading_pair])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(exchange, [trading_pair])]
        self._initialize_wallet(token_trading_pairs=list(set(maker_assets)))
        self._initialize_markets(market_names)
        self.assets = set(maker_assets)
        maker_data = [self.markets[exchange], trading_pair] + list(maker_assets)
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]
        asset_price_delegate = None
        if price_source_enabled:
            if price_source_type == "exchange":
                asset_trading_pair: str = self._convert_to_exchange_trading_pair(
                    price_source_exchange, [price_source_market])[0]
                ext_market = create_paper_trade_market(price_source_exchange, [asset_trading_pair])
                self.markets[price_source_exchange]: MarketBase = ext_market
                asset_price_delegate = OrderBookAssetPriceDelegate(ext_market, asset_trading_pair)
            elif price_source_type == "custom_api":
                asset_price_delegate = APIAssetPriceDelegate(price_source_custom)
        else:
            asset_price_delegate = None

        strategy_logging_options = PureMarketMakingStrategyV2.OPTION_LOG_ALL

        self.strategy = PureMarketMakingStrategyV2(market_infos=[MarketTradingPairTuple(*maker_data)],
                                                   pricing_delegate=pricing_delegate,
                                                   filter_delegate=filter_delegate,
                                                   sizing_delegate=sizing_delegate,
                                                   filled_order_delay=filled_order_delay,
                                                   hanging_orders_enabled=hanging_orders_enabled,
                                                   order_refresh_time=order_refresh_time,
                                                   order_optimization_enabled=order_optimization_enabled,
                                                   order_optimization_depth=order_optimization_depth,
                                                   add_transaction_costs_to_orders=add_transaction_costs_to_orders,
                                                   logging_options=strategy_logging_options,
                                                   asset_price_delegate=asset_price_delegate,
                                                   expiration_seconds=order_expiration_time,
                                                   hanging_orders_cancel_pct=hanging_orders_cancel_pct,
                                                   order_refresh_tolerance_spread=order_refresh_tolerance_spread)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
