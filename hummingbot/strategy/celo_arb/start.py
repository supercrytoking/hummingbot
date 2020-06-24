from typing import (
    List,
    Tuple,
)
from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.celo_arb.celo_arb import CeloArbStrategy
from hummingbot.strategy.celo_arb.celo_arb_config_map import celo_arb_config_map


def start(self):
    secondary_exchange = celo_arb_config_map.get("secondary_exchange").value.lower()
    secondary_market = celo_arb_config_map.get("secondary_market").value
    order_amount = celo_arb_config_map.get("order_amount").value
    min_profitability = celo_arb_config_map.get("min_profitability").value / Decimal("100")
    celo_slippage_buffer = celo_arb_config_map.get("celo_slippage_buffer").value / Decimal("100")
    try:
        secondary_trading_pair: str = self._convert_to_exchange_trading_pair(secondary_exchange, [secondary_market])[0]
        secondary_assets: Tuple[str, str] = self._initialize_market_assets(secondary_exchange,
                                                                           [secondary_trading_pair])[0]
    except ValueError as e:
        self._notify(str(e))
        return

    market_names: List[Tuple[str, List[str]]] = [(secondary_exchange, [secondary_trading_pair])]
    self._initialize_wallet(token_trading_pairs=list(secondary_assets))
    self._initialize_markets(market_names)
    self.assets = set(secondary_assets)

    secondary_data = [self.markets[secondary_exchange], secondary_trading_pair] + list(secondary_assets)
    market_info = MarketTradingPairTuple(*secondary_data)
    self.market_trading_pair_tuples = [market_info]
    self.strategy = CeloArbStrategy(market_info, min_profitability, order_amount, celo_slippage_buffer)
