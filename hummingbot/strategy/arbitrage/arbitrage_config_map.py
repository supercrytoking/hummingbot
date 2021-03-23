from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_decimal,
    validate_bool
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)
import hummingbot.client.settings as settings
from decimal import Decimal
from typing import Optional


def validate_primary_market_trading_pair(value: str) -> Optional[str]:
    primary_market = arbitrage_config_map.get("primary_market").value
    return validate_market_trading_pair(primary_market, value)


def validate_secondary_market_trading_pair(value: str) -> Optional[str]:
    secondary_market = arbitrage_config_map.get("secondary_market").value
    return validate_market_trading_pair(secondary_market, value)


def primary_trading_pair_prompt():
    primary_market = arbitrage_config_map.get("primary_market").value
    example = EXAMPLE_PAIRS.get(primary_market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (primary_market, f" (e.g. {example})" if example else "")


def secondary_trading_pair_prompt():
    secondary_market = arbitrage_config_map.get("secondary_market").value
    example = EXAMPLE_PAIRS.get(secondary_market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (secondary_market, f" (e.g. {example})" if example else "")


def secondary_market_on_validated(value: str):
    required_exchanges.append(value)


def use_oracle_conversion_rate_on_validated(value: bool):
    # global required_rate_oracle, rate_oracle_pairs
    first_base, first_quote = arbitrage_config_map["primary_market_trading_pair"].value.split("-")
    second_base, second_quote = arbitrage_config_map["secondary_market_trading_pair"].value.split("-")
    if value and (first_base != second_base or first_quote != second_quote):
        settings.required_rate_oracle = True
        settings.rate_oracle_pairs = []
        if first_base != second_base:
            settings.rate_oracle_pairs.append(f"{second_base}-{first_base}")
        if first_quote != second_quote:
            settings.rate_oracle_pairs.append(f"{second_quote}-{first_quote}")


arbitrage_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="arbitrage"),
    "primary_market": ConfigVar(
        key="primary_market",
        prompt="Enter your primary spot connector >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=lambda value: required_exchanges.append(value)),
    "secondary_market": ConfigVar(
        key="secondary_market",
        prompt="Enter your secondary spot connector >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=secondary_market_on_validated),
    "primary_market_trading_pair": ConfigVar(
        key="primary_market_trading_pair",
        prompt=primary_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_primary_market_trading_pair),
    "secondary_market_trading_pair": ConfigVar(
        key="secondary_market_trading_pair",
        prompt=secondary_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_secondary_market_trading_pair),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("0.3"),
        validator=lambda v: validate_decimal(v, Decimal(-100), Decimal("100"), inclusive=True),
        type_str="decimal"),
    "use_oracle_conversion_rate": ConfigVar(
        key="use_oracle_conversion_rate",
        type_str="bool",
        prompt="Do you want to use rate oracle on unmatched trading pairs? >>> ",
        prompt_on_new=True,
        default=True,
        validator=lambda v: validate_bool(v),
        on_validated=use_oracle_conversion_rate_on_validated),
    "secondary_to_primary_base_conversion_rate": ConfigVar(
        key="secondary_to_primary_base_conversion_rate",
        prompt="Enter conversion rate for secondary base asset value to primary base asset value, e.g. "
               "if primary base asset is USD, secondary is DAI and 1 USD is worth 1.25 DAI, "
               "the conversion rate is 0.8 (1 / 1.25) >>> ",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal("100"), inclusive=False),
        type_str="decimal"),
    "secondary_to_primary_quote_conversion_rate": ConfigVar(
        key="secondary_to_primary_quote_conversion_rate",
        prompt="Enter conversion rate for secondary quote asset value to primary quote asset value, e.g. "
               "if primary quote asset is USD, secondary is DAI and 1 USD is worth 1.25 DAI, "
               "the conversion rate is 0.8 (1 / 1.25) >>> ",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal("100"), inclusive=False),
        type_str="decimal"),
}
