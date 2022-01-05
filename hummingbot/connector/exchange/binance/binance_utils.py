from typing import Dict, Any

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar


CENTRALIZED = True
EXAMPLE_PAIR = "ZRX-ETH"
DEFAULT_FEES = [0.1, 0.1]


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    return exchange_info.get("status", None) == "TRADING" and "SPOT" in exchange_info.get("permissions", list())


def public_rest_url(path_url: str, domain: str = "com") -> str:
    return CONSTANTS.REST_URL.format(domain) + CONSTANTS.PUBLIC_API_VERSION + path_url


def private_rest_url(path_url: str, domain: str = "com") -> str:
    return CONSTANTS.REST_URL.format(domain) + CONSTANTS.PRIVATE_API_VERSION + path_url


KEYS = {
    "binance_api_key":
        ConfigVar(key="binance_api_key",
                  prompt="Enter your Binance API key >>> ",
                  required_if=using_exchange("binance"),
                  is_secure=True,
                  is_connect_key=True),
    "binance_api_secret":
        ConfigVar(key="binance_api_secret",
                  prompt="Enter your Binance API secret >>> ",
                  required_if=using_exchange("binance"),
                  is_secure=True,
                  is_connect_key=True),
}

OTHER_DOMAINS = ["binance_us"]
OTHER_DOMAINS_PARAMETER = {"binance_us": "us"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"binance_us": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"binance_us": [0.1, 0.1]}
OTHER_DOMAINS_KEYS = {"binance_us": {
    "binance_us_api_key":
        ConfigVar(key="binance_us_api_key",
                  prompt="Enter your Binance US API key >>> ",
                  required_if=using_exchange("binance_us"),
                  is_secure=True,
                  is_connect_key=True),
    "binance_us_api_secret":
        ConfigVar(key="binance_us_api_secret",
                  prompt="Enter your Binance US API secret >>> ",
                  required_if=using_exchange("binance_us"),
                  is_secure=True,
                  is_connect_key=True),
}}
