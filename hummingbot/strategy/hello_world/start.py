from typing import (
    List,
    Tuple,
)

from hummingbot.strategy.market_symbol_pair import MarketSymbolPair
from hummingbot.strategy.hello_world import (
    HelloWorldStrategy
)
from hummingbot.strategy.hello_world.hello_world_config_map import hello_world_config_map


def start(self):
    try:
        order_amount = hello_world_config_map.get("order_amount").value
        cancel_order_wait_time = hello_world_config_map.get("cancel_order_wait_time").value
        order_type = hello_world_config_map.get("order_type").value
        is_buy = hello_world_config_map.get("is_buy").value
        time_delay = hello_world_config_map.get("time_delay").value
        market = hello_world_config_map.get("market").value.lower()
        raw_market_symbol = hello_world_config_map.get("market_symbol_pair").value.upper()
        order_price = None

        if order_type == "limit":
            order_price = hello_world_config_map.get("order_price").value

        try:
            assets: Tuple[str, str] = self._initialize_market_assets(market, [raw_market_symbol])[0]
        except ValueError as e:
            self._notify(str(e))
            return

        market_names: List[Tuple[str, List[str]]] = [(market, [raw_market_symbol])]

        self._initialize_wallet(token_symbols=list(set(assets)))
        self._initialize_markets(market_names)
        self.assets = set(assets)

        maker_data = [self.markets[market], raw_market_symbol] + list(assets)
        self.market_symbol_pairs = [MarketSymbolPair(*maker_data)]

        strategy_logging_options = HelloWorldStrategy.OPTION_LOG_ALL

        self.strategy = HelloWorldStrategy(market_infos=[MarketSymbolPair(*maker_data)],
                                           order_type=order_type,
                                           order_price=order_price,
                                           cancel_order_wait_time=cancel_order_wait_time,
                                           is_buy=is_buy,
                                           time_delay=time_delay,
                                           order_amount=order_amount,
                                           logging_options=strategy_logging_options)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
