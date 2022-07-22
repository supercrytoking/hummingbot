from typing import List, Tuple

from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making import (
    CrossExchangeMarketMakingStrategy,
)
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_pair import CrossExchangeMarketPair
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


def start(self):
    c_map = self.strategy_config_map
    maker_market = c_map.maker_market.lower()
    taker_market = c_map.taker_market.lower()
    raw_maker_trading_pair = c_map.maker_market_trading_pair
    raw_taker_trading_pair = c_map.taker_market_trading_pair
    status_report_interval = self.client_config_map.strategy_report_interval

    try:
        maker_trading_pair: str = raw_maker_trading_pair
        taker_trading_pair: str = raw_taker_trading_pair
        maker_assets: Tuple[str, str] = self._initialize_market_assets(maker_market, [maker_trading_pair])[0]
        taker_assets: Tuple[str, str] = self._initialize_market_assets(taker_market, [taker_trading_pair])[0]
    except ValueError as e:
        self.notify(str(e))
        return

    market_names: List[Tuple[str, List[str]]] = [
        (maker_market, [maker_trading_pair]),
        (taker_market, [taker_trading_pair]),
    ]

    self._initialize_markets(market_names)
    maker_data = [self.markets[maker_market], maker_trading_pair] + list(maker_assets)
    taker_data = [self.markets[taker_market], taker_trading_pair] + list(taker_assets)
    maker_market_trading_pair_tuple = MarketTradingPairTuple(*maker_data)
    taker_market_trading_pair_tuple = MarketTradingPairTuple(*taker_data)
    self.market_trading_pair_tuples = [maker_market_trading_pair_tuple, taker_market_trading_pair_tuple]
    self.market_pair = CrossExchangeMarketPair(maker=maker_market_trading_pair_tuple, taker=taker_market_trading_pair_tuple)

    strategy_logging_options = (
        CrossExchangeMarketMakingStrategy.OPTION_LOG_CREATE_ORDER
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_ADJUST_ORDER
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_MAKER_ORDER_FILLED
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_REMOVING_ORDER
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_STATUS_REPORT
        | CrossExchangeMarketMakingStrategy.OPTION_LOG_MAKER_ORDER_HEDGED
    )
    self.strategy = CrossExchangeMarketMakingStrategy()
    self.strategy.init_params(
        config_map=c_map,
        market_pairs=[self.market_pair],
        status_report_interval=status_report_interval,
        logging_options=strategy_logging_options,
        hb_app_notification=True,
    )
