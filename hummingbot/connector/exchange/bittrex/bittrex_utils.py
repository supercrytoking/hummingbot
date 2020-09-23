from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import new_fee_config_var, using_exchange


CENTRALIZED = True

EXAMPLE_PAIR = "ZRX-ETH"

DEFAULT_FEES = [0.25, 0.25]

FEE_OVERRIDE_MAP = {
    "bittrex_maker_fee": new_fee_config_var("bittrex_maker_fee"),
    "bittrex_taker_fee": new_fee_config_var("bittrex_taker_fee")
}

KEYS = {
    "bittrex_api_key":
        ConfigVar(key="bittrex_api_key",
                  prompt="Enter your Bittrex API key >>> ",
                  required_if=using_exchange("bittrex"),
                  is_secure=True,
                  is_connect_key=True),
    "bittrex_secret_key":
        ConfigVar(key="bittrex_secret_key",
                  prompt="Enter your Bittrex secret key >>> ",
                  required_if=using_exchange("bittrex"),
                  is_secure=True,
                  is_connect_key=True),
}
