from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    is_exchange,
    is_valid_market_symbol,
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)


def symbol_prompt():
    market = simple_trade_config_map.get("market").value
    example = EXAMPLE_PAIRS.get(market)
    return "Enter the token symbol you would like to trade on %s%s >>> " \
           % (market, f" (e.g. {example})" if example else "")


def str2bool(value: str):
    return str(value).lower() in ("yes", "true", "t", "1")


# checks if the symbol pair is valid
def is_valid_market_symbol_pair(value: str) -> bool:
    market = simple_trade_config_map.get("market").value
    return is_valid_market_symbol(market, value)


simple_trade_config_map = {
    "market":                           ConfigVar(key="market",
                                                  prompt="Enter the name of the exchange >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "market_symbol_pair":               ConfigVar(key="market_symbol_pair",
                                                  prompt=symbol_prompt,
                                                  validator=is_valid_market_symbol_pair),
    "order_type":                       ConfigVar(key="order_type",
                                                  prompt="Enter type of order "
                                                         "(limit/market) default is market >>> ",
                                                  type_str="str",
                                                  validator=lambda v: v in {"limit", "market", ""},
                                                  default="market"),
    "order_amount":                     ConfigVar(key="order_amount",
                                                  prompt="What is your preferred quantity per order (denominated in "
                                                         "the base asset, default is 1) ? >>> ",
                                                  default=1.0,
                                                  type_str="float"),
    "is_buy":                           ConfigVar(key="is_buy",
                                                  prompt="Enter True for Buy order and False for Sell order "
                                                         "(default is Buy Order) >>> ",
                                                  type_str="bool",
                                                  default=True),
    "time_delay":                       ConfigVar(key="time_delay",
                                                  prompt="How much do you want to wait to place the "
                                                         "order (Enter 10 to indicate 10 seconds. Default is 0)? >>> ",
                                                  type_str="float",
                                                  default=0),
    "order_price":                      ConfigVar(key="order_price",
                                                  prompt="What is the price of the limit order ? >>> ",
                                                  required_if=lambda: simple_trade_config_map.get(
                                                                      "order_type").value == "limit",
                                                  type_str="float"),
    "cancel_order_wait_time":                ConfigVar(key="cancel_order_wait_time",
                                                  prompt="How long do you want to wait before cancelling your limit "
                                                         "order (in seconds). (Default is 60 seconds) ? >>> ",
                                                  required_if=lambda: simple_trade_config_map.get(
                                                                      "order_type").value == "limit",
                                                  type_str="float",
                                                  default=60),

}