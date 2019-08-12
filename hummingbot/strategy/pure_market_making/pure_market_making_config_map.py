from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    is_exchange,
    is_valid_market_symbol,
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)


def maker_symbol_prompt():
    maker_market = pure_market_making_config_map.get("maker_market").value
    example = EXAMPLE_PAIRS.get(maker_market)
    return "Enter the token symbol you would like to trade on %s%s >>> " \
           % (maker_market, f" (e.g. {example})" if example else "")


# strategy specific validators
def is_valid_maker_market_symbol(value: str) -> bool:
    maker_market = pure_market_making_config_map.get("maker_market").value
    return is_valid_market_symbol(maker_market, value)


pure_market_making_config_map = {
    "maker_market":                     ConfigVar(key="maker_market",
                                                  prompt="Enter your maker exchange name >>> ",
                                                  validator=is_exchange,
                                                  on_validated=lambda value: required_exchanges.append(value)),
    "maker_market_symbol":              ConfigVar(key="primary_market_symbol",
                                                  prompt=maker_symbol_prompt,
                                                  validator=is_valid_maker_market_symbol),
    "mode":                             ConfigVar(key="mode",
                                                  prompt="Enter quantity of orders per side [bid/ask] "
                                                         "(single/multiple) default is single >>> ",
                                                  type_str="str",
                                                  validator=lambda v: v in {"single", "multiple"},
                                                  default="single"),
    "bid_place_threshold":              ConfigVar(key="bid_place_threshold",
                                                  prompt="How far away from the mid price do you want to place the "
                                                         "first bid order (Enter 0.01 to indicate 1%)? >>> ",
                                                  type_str="float",
                                                  default=0.01),
    "ask_place_threshold":              ConfigVar(key="ask_place_threshold",
                                                  prompt="How far away from the mid price do you want to place the "
                                                         "first ask order (Enter 0.01 to indicate 1%)? >>> ",
                                                  type_str="float",
                                                  default=0.01),
    "cancel_order_wait_time":           ConfigVar(key="cancel_order_wait_time",
                                                  prompt="How often do you want to cancel and replace bids and asks "
                                                         "(in seconds). (Default is 60 seconds) ? >>> ",
                                                  type_str="float",
                                                  default=60),
    "order_amount":                     ConfigVar(key="order_amount",
                                                  prompt="What is your preferred quantity per order (denominated in "
                                                         "the base asset, default is 1) ? >>> ",
                                                  default=1.0,
                                                  required_if=
                                                  lambda: pure_market_making_config_map.get("mode").value == "single",
                                                  type_str="float"),
    "number_of_orders":                 ConfigVar(key="number_of_orders",
                                                  prompt="How many orders do you want to place on both sides,"
                                                         " (default is 1) ? >>> ",
                                                  required_if=
                                                  lambda: pure_market_making_config_map.get("mode").value == "multiple",
                                                  type_str="int",
                                                  default=1),
    "order_start_size":                 ConfigVar(key="order_start_size",
                                                  prompt="What is the size of the first bid and ask order"
                                                  " (default is 1) ? >>> ",
                                                  required_if=
                                                  lambda: pure_market_making_config_map.get("mode").value == "multiple",
                                                  type_str="float",
                                                  default=1),
    "order_step_size":                  ConfigVar(key="order_step_size",
                                                  prompt="How much do you want to increase the order size for each "
                                                         "additional order (default is 0) ? >>> ",
                                                  required_if=
                                                  lambda: pure_market_making_config_map.get("mode").value == "multiple",
                                                  type_str="float",
                                                  default=0),
    "order_interval_percent":           ConfigVar(key="order_interval_percent",
                                                  prompt="Enter the price increments (as percentage) for subsequent "
                                                         "orders (Enter 0.01 to indicate 1%)? >>> ",
                                                  required_if=
                                                  lambda: pure_market_making_config_map.get("mode").value == "multiple",
                                                  type_str="float",
                                                  default=0.01),
    "inventory_skew_enabled":           ConfigVar(key="inventory_skew_enabled",
                                                  prompt="Would you like to enable inventory skew? (y/n) >>> ",
                                                  type_str="bool",
                                                  default=False),
    "inventory_target_base_percent":    ConfigVar(key="inventory_target_base_percent",
                                                  prompt="What is your target base asset inventory percentage "
                                                         "(Enter 0.01 to indicate 1%)? >>> ",
                                                  required_if=
                                                  lambda: pure_market_making_config_map.get("inventory_skew_enabled").value,
                                                  type_str="float",
                                                  default=0.01),
}
