from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    is_exchange,
    is_valid_market_trading_pair,
    is_valid_percent,
    is_valid_expiration,
    is_valid_bool,
    is_valid_decimal
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)
from hummingbot.client.config.global_config_map import (
    using_bamboo_coordinator_mode,
    using_exchange
)
from hummingbot.client.config.config_helpers import (
    parse_cvar_value,
    minimum_order_amount
)
from hummingbot.data_feed.exchange_price_manager import ExchangePriceManager


def maker_trading_pair_prompt():
    maker_market = pure_market_making_config_map.get("maker_market").value
    example = EXAMPLE_PAIRS.get(maker_market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (maker_market, f" (e.g. {example})" if example else "")


def assign_values_advanced_mode_switch(advanced_mode):
    advanced_mode = parse_cvar_value(pure_market_making_config_map["advanced_mode"], advanced_mode)
    found_advanced_section = False
    for cvar in pure_market_making_config_map.values():
        if found_advanced_section:
            if advanced_mode and cvar.value is not None and cvar.default is not None:
                cvar.value = None
            if not advanced_mode and cvar.value is None and cvar.default is not None:
                cvar.value = cvar.default
        elif cvar == pure_market_making_config_map["advanced_mode"]:
            found_advanced_section = True


# strategy specific validators
def is_valid_maker_market_trading_pair(value: str) -> bool:
    maker_market = pure_market_making_config_map.get("maker_market").value
    return is_valid_market_trading_pair(maker_market, value)


def order_amount_prompt() -> str:
    trading_pair = pure_market_making_config_map["maker_market_trading_pair"].value
    base_asset, quote_asset = trading_pair.split("-")
    min_amount = minimum_order_amount(trading_pair)
    return f"What is the amount of {base_asset} per order? (minimum {min_amount}) >>> "


def order_start_size_prompt() -> str:
    trading_pair = pure_market_making_config_map["maker_market_trading_pair"].value
    min_amount = minimum_order_amount(trading_pair)
    return f"What is the size of the first bid and ask order? (minimum {min_amount}) >>> "


def is_valid_order_amount(value: str) -> bool:
    try:
        trading_pair = pure_market_making_config_map["maker_market_trading_pair"].value
        return Decimal(value) >= minimum_order_amount(trading_pair)
    except Exception:
        return False


def external_market_trading_pair_prompt():
    external_market = pure_market_making_config_map.get("external_price_source_exchange").value
    return f'Enter the token trading pair on {external_market} >>> '


def is_valid_external_market_trading_pair(value: str) -> bool:
    market = pure_market_making_config_map.get("external_price_source_exchange").value
    return is_valid_market_trading_pair(market, value)


def maker_market_on_validated(value: str):
    required_exchanges.append(value)
    ExchangePriceManager.set_exchanges_to_feed([value])
    ExchangePriceManager.start()


pure_market_making_config_map = {
    "maker_market":
        ConfigVar(key="maker_market",
                  prompt="Enter your maker exchange name >>> ",
                  validator=is_exchange,
                  on_validated=maker_market_on_validated),
    "maker_market_trading_pair":
        ConfigVar(key="primary_market_trading_pair",
                  prompt=maker_trading_pair_prompt,
                  validator=is_valid_maker_market_trading_pair),
    "bid_place_threshold":
        ConfigVar(key="bid_place_threshold",
                  prompt="How far away from the mid price do you want to place the "
                         "first bid order? (Enter 0.01 to indicate 1%) >>> ",
                  type_str="decimal",
                  validator=is_valid_percent),
    "ask_place_threshold":
        ConfigVar(key="ask_place_threshold",
                  prompt="How far away from the mid price do you want to place the "
                         "first ask order? (Enter 0.01 to indicate 1%) >>> ",
                  type_str="decimal",
                  validator=is_valid_percent),
    "cancel_order_wait_time":
        ConfigVar(key="cancel_order_wait_time",
                  prompt="How often do you want to cancel and replace bids and asks "
                         "(in seconds)? >>> ",
                  default=30.0,
                  required_if=lambda: not (using_exchange("radar_relay")() or
                                           (using_exchange("bamboo_relay")() and not using_bamboo_coordinator_mode())),
                  type_str="float"),
    "order_amount":
        ConfigVar(key="order_amount",
                  prompt=order_amount_prompt,
                  type_str="decimal",
                  validator=is_valid_order_amount),
    "advanced_mode":
        ConfigVar(key="advanced_mode",
                  prompt="Would you like to proceed with advanced configuration? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  on_validated=assign_values_advanced_mode_switch,
                  migration_default=True,
                  validator=is_valid_bool),
    "expiration_seconds":
        ConfigVar(key="expiration_seconds",
                  prompt="How long should your limit orders remain valid until they "
                         "expire and are replaced? (Minimum / Default is 130 seconds) >>> ",
                  default=130.0,
                  required_if=lambda: using_exchange("radar_relay")() or (using_exchange("bamboo_relay")() and
                                                                          not using_bamboo_coordinator_mode()),
                  type_str="float",
                  validator=is_valid_expiration),
    "mode":
        ConfigVar(key="mode",
                  prompt="Enter quantity of bid/ask orders per side (single/multiple) >>> ",
                  type_str="str",
                  validator=lambda v: v in {"single", "multiple"},
                  default="single"),
    "number_of_orders":
        ConfigVar(key="number_of_orders",
                  prompt="How many orders do you want to place on both sides? >>> ",
                  required_if=lambda: pure_market_making_config_map.get("mode").value == "multiple",
                  type_str="int",
                  default=2),
    "order_start_size":
        ConfigVar(key="order_start_size",
                  prompt=order_start_size_prompt,
                  required_if=lambda: pure_market_making_config_map.get("mode").value == "multiple",
                  type_str="decimal",
                  validator=is_valid_order_amount),
    "order_step_size":
        ConfigVar(key="order_step_size",
                  prompt="How much do you want to increase the order size for each "
                         "additional order? >>> ",
                  required_if=lambda: pure_market_making_config_map.get("mode").value == "multiple",
                  type_str="decimal",
                  default=0),
    "order_interval_percent":
        ConfigVar(key="order_interval_percent",
                  prompt="Enter the price increments (as percentage) for subsequent "
                         "orders? (Enter 0.01 to indicate 1%) >>> ",
                  required_if=lambda: pure_market_making_config_map.get("mode").value == "multiple",
                  type_str="decimal",
                  validator=is_valid_percent,
                  default=0.01),
    "inventory_skew_enabled":
        ConfigVar(key="inventory_skew_enabled",
                  prompt="Would you like to enable inventory skew? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=is_valid_bool),
    "inventory_target_base_percent":
        ConfigVar(key="inventory_target_base_percent",
                  prompt="What is your target base asset percentage? Enter 50 for 50% >>> ",
                  required_if=lambda: pure_market_making_config_map.get("inventory_skew_enabled").value,
                  type_str="decimal",
                  validator=lambda v: is_valid_decimal(v, 0, 100),
                  default=50),
    "inventory_range_multiplier":
        ConfigVar(key="inventory_range_multiplier",
                  prompt="What is your tolerable range of inventory around the target, "
                         "expressed in multiples of your total order size? ",
                  required_if=lambda: pure_market_making_config_map.get("inventory_skew_enabled").value,
                  type_str="decimal",
                  default=1.0),
    "filled_order_replenish_wait_time":
        ConfigVar(key="filled_order_replenish_wait_time",
                  prompt="How long do you want to wait before placing the next order "
                         "if your order gets filled (in seconds)? >>> ",
                  type_str="float",
                  default=60),
    "enable_order_filled_stop_cancellation":
        ConfigVar(key="enable_order_filled_stop_cancellation",
                  prompt="Do you want to enable hanging orders? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=is_valid_bool),
    "cancel_hanging_order_pct":
        ConfigVar(key="cancel_hanging_order_pct",
                  prompt="At what spread percentage (from mid price) will hanging orders be canceled? "
                         "(Enter 0.01 to indicate 1%) >>> ",
                  required_if=lambda: pure_market_making_config_map.get("enable_order_filled_stop_cancellation").value,
                  type_str="decimal",
                  default=0.1,
                  validator=is_valid_percent,
                  migration_default=0.1),
    "best_bid_ask_jump_mode":
        ConfigVar(key="best_bid_ask_jump_mode",
                  prompt="Do you want to enable best bid ask jumping? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=is_valid_bool),
    "best_bid_ask_jump_orders_depth":
        ConfigVar(key="best_bid_ask_jump_orders_depth",
                  prompt="How deep do you want to go into the order book for calculating "
                         "the top bid and ask, ignoring dust orders on the top "
                         "(expressed in base asset amount)? >>> ",
                  required_if=lambda: pure_market_making_config_map.get("best_bid_ask_jump_mode").value,
                  type_str="decimal",
                  default=0),
    "add_transaction_costs":
        ConfigVar(key="add_transaction_costs",
                  prompt="Do you want to add transaction costs automatically to order prices? (Yes/No) >>> ",
                  type_str="bool",
                  default=False,
                  validator=is_valid_bool),
    "external_pricing_source": ConfigVar(key="external_pricing_source",
                                         prompt="Would you like to use an external pricing source for mid-market "
                                                "price? (Yes/No) >>> ",
                                         type_str="bool",
                                         default=False,
                                         validator=is_valid_bool),
    "external_price_source_type": ConfigVar(key="external_price_source_type",
                                            prompt="Which type of external price source to use? "
                                                   "(exchange/feed/custom_api) >>> ",
                                            required_if=lambda: pure_market_making_config_map.get(
                                                "external_pricing_source").value,
                                            type_str="str",
                                            validator=lambda s: s in {"exchange", "feed", "custom_api"}),
    "external_price_source_exchange": ConfigVar(key="external_price_source_exchange",
                                                prompt="Enter exchange name >>> ",
                                                required_if=lambda: pure_market_making_config_map.get(
                                                    "external_price_source_type").value == "exchange",
                                                type_str="str",
                                                validator=lambda s: s != pure_market_making_config_map.get(
                                                    "maker_market").value and is_exchange(s)),
    "external_price_source_exchange_trading_pair": ConfigVar(key="external_price_source_exchange_trading_pair",
                                                             prompt=external_market_trading_pair_prompt,
                                                             required_if=lambda: pure_market_making_config_map.get(
                                                                 "external_price_source_type").value == "exchange",
                                                             type_str="str",
                                                             validator=is_valid_external_market_trading_pair),
    "external_price_source_feed_base_asset": ConfigVar(key="external_price_source_feed_base_asset",
                                                       prompt="Reference base asset from data feed? (e.g. ETH) >>> ",
                                                       required_if=lambda: pure_market_making_config_map.get(
                                                           "external_price_source_type").value == "feed",
                                                       type_str="str"),
    "external_price_source_feed_quote_asset": ConfigVar(key="external_price_source_feed_quote_asset",
                                                        prompt="Reference quote asset from data feed? (e.g. USD) >>> ",
                                                        required_if=lambda: pure_market_making_config_map.get(
                                                            "external_price_source_type").value == "feed",
                                                        type_str="str"),
    "external_price_source_custom_api": ConfigVar(key="external_price_source_custom_api",
                                                  prompt="Enter pricing API URL >>> ",
                                                  required_if=lambda: pure_market_making_config_map.get(
                                                      "external_price_source_type").value == "custom_api",
                                                  type_str="str")
}
