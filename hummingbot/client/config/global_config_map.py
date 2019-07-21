import random
from typing import Callable
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import (
    required_exchanges,
    DEXES,
    DEFAULT_KEY_FILE_PATH,
    DEFAULT_LOG_FILE_PATH,
)


def generate_client_id() -> str:
    vals = [random.choice(range(0, 256)) for i in range(0, 20)]
    return "".join([f"{val:02x}" for val in vals])


# Required conditions
def using_strategy(strategy: str) -> Callable:
    return lambda: global_config_map.get("strategy").value == strategy


def using_exchange(exchange: str) -> Callable:
    return lambda: exchange in required_exchanges


def using_wallet() -> bool:
    return any([e in DEXES for e in required_exchanges])


# Main global config store
global_config_map = {
    # The variables below are usually not prompted during setup process
    "client_id":                        ConfigVar(key="client_id",
                                                  prompt=None,
                                                  required_if=lambda: False,
                                                  default=generate_client_id()),
    "log_level":                        ConfigVar(key="log_level",
                                                  prompt=None,
                                                  required_if=lambda: False,
                                                  default="INFO"),
    "debug_console":                    ConfigVar(key="debug_console",
                                                  prompt=None,
                                                  type_str="bool",
                                                  required_if=lambda: False,
                                                  default=False),
    "strategy_report_interval":         ConfigVar(key="strategy_report_interval",
                                                  prompt=None,
                                                  type_str="float",
                                                  required_if=lambda: False,
                                                  default=900),
    "reporting_aggregation_interval":   ConfigVar(key="reporting_aggregation_interval",
                                                  prompt=None,
                                                  default=60.0,
                                                  required_if=lambda: False,
                                                  type_str="float"),
    "reporting_log_interval":           ConfigVar(key="reporting_log_interval",
                                                  prompt=None,
                                                  default=60.0,
                                                  required_if=lambda: False,
                                                  type_str="float"),
    "logger_override_whitelist":        ConfigVar(key="logger_override_whitelist",
                                                  prompt=None,
                                                  required_if=lambda: False,
                                                  default=["hummingbot.strategy",
                                                           "hummingbot.market",
                                                           "hummingbot.wallet",
                                                           "conf"
                                                           ],
                                                  type_str="list"),
    "key_file_path":                    ConfigVar(key="key_file_path",
                                                  prompt="Where would you like to save your private key file? (default "
                                                         "'%s') >>> " % (DEFAULT_KEY_FILE_PATH,),
                                                  required_if=lambda: False,
                                                  default=DEFAULT_KEY_FILE_PATH),
    "log_file_path":                    ConfigVar(key="log_file_path",
                                                  prompt="Where would you like to save your logs? (default '%s') >>> "
                                                         % (DEFAULT_LOG_FILE_PATH,),
                                                  required_if=lambda: False,
                                                  default=DEFAULT_LOG_FILE_PATH),

    # Required by chosen CEXes or DEXes
    "binance_api_key":                  ConfigVar(key="binance_api_key",
                                                  prompt="Enter your Binance API key >>> ",
                                                  required_if=using_exchange("binance"),
                                                  is_secure=True),
    "binance_api_secret":               ConfigVar(key="binance_api_secret",
                                                  prompt="Enter your Binance API secret >>> ",
                                                  required_if=using_exchange("binance"),
                                                  is_secure=True),
    "coinbase_pro_api_key":             ConfigVar(key="coinbase_pro_api_key",
                                                  prompt="Enter your Coinbase API key >>> ",
                                                  required_if=using_exchange("coinbase_pro"),
                                                  is_secure=True),
    "coinbase_pro_secret_key":          ConfigVar(key="coinbase_pro_secret_key",
                                                  prompt="Enter your Coinbase secret key >>> ",
                                                  required_if=using_exchange("coinbase_pro"),
                                                  is_secure=True),
    "coinbase_pro_passphrase":          ConfigVar(key="coinbase_pro_passphrase",
                                                  prompt="Enter your Coinbase passphrase >>> ",
                                                  required_if=using_exchange("coinbase_pro"),
                                                  is_secure=True),
    "bamboo_relay_use_coordinator":     ConfigVar(key="bamboo_relay_use_coordinator",
                                                  prompt="Would you like to use the Bamboo Relay Coordinator (y/n) >>> ",
                                                  required_if=using_exchange("bamboo_relay"),
                                                  type_str="bool",
                                                  default=True),
    "bamboo_relay_pre_emptive_soft_cancels":      ConfigVar(key="bamboo_relay_pre_emptive_soft_cancels",
                                                            prompt="Would you like to pre-emptively soft cancel orders (y/n) >>> ",
                                                            required_if=using_exchange("bamboo_relay"),
                                                            type_str="bool",
                                                            default=True),
    "wallet":                           ConfigVar(key="wallet",
                                                  prompt="Would you like to import an existing wallet or create a new"
                                                         " wallet? (import/create) >>> ",
                                                  required_if=using_wallet,
                                                  is_secure=True),
    "ethereum_rpc_url":                 ConfigVar(key="ethereum_rpc_url",
                                                  prompt="Which Ethereum node would you like your client to connect "
                                                         "to? >>> ",
                                                  required_if=using_wallet),
    # Whether or not to invoke cancel_all on exit if marketing making on a open order book DEX (e.g. Radar Relay)
    "on_chain_cancel_on_exit":          ConfigVar(key="on_chain_cancel_on_exit",
                                                  prompt="Would you like to cancel transactions on chain if using an "
                                                         "open order books exchanges? >>> ",
                                                  required_if=lambda: False,
                                                  type_str="bool",
                                                  default=False),
    "exchange_rate_conversion":         ConfigVar(key="exchange_rate_conversion",
                                                  prompt="Enter your custom exchange rate conversion settings >>> ",
                                                  required_if=lambda: False,
                                                  type_str="list",
                                                  default=[["USD", 1.0, "manual"],
                                                           ["DAI", 1.0, "coin_gecko_api"],
                                                           ["USDT", 1.0, "coin_gecko_api"],
                                                           ["USDC", 1.0, "coin_gecko_api"],
                                                           ["TUSD", 1.0, "coin_gecko_api"]]),
    "exchange_rate_fetcher":            ConfigVar(key="exchange_rate_fetcher",
                                                  prompt="Enter your custom exchange rate fetcher settings >>> ",
                                                  required_if=lambda: False,
                                                  type_str="list",
                                                  default=[["ETH", "coin_gecko_api"],
                                                           ["DAI", "coin_gecko_api"]]),

    "kill_switch_enabled":              ConfigVar(key="kill_switch_enabled",
                                                  prompt="Would you like to enable the kill switch? (y/n) >>> ",
                                                  type_str="bool",
                                                  default=False),
    "kill_switch_rate":                 ConfigVar(key="kill_switch_rate",
                                                  prompt="At what profit/loss rate would you like the bot to "
                                                         "stop? (e.g. -0.05 equals 5 percent loss) >>> ",
                                                  type_str="float",
                                                  default=-1,
                                                  required_if=lambda: global_config_map["kill_switch_enabled"].value),

    "telegram_enabled":                 ConfigVar(key="telegram_enabled",
                                                  prompt="Would you like to enable telegram? >>> ",
                                                  type_str="bool",
                                                  default=False,
                                                  required_if=lambda: False),
    "telegram_token":                   ConfigVar(key="telegram_token",
                                                  prompt="What is your telegram token? >>> ",
                                                  required_if=lambda: False),
    "telegram_chat_id":                 ConfigVar(key="telegram_chat_id",
                                                  prompt="What is your telegram chat id? >>> ",
                                                  required_if=lambda: False),
}
