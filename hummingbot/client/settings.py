from os.path import (
    realpath,
    join,
)
from typing import List

from hummingbot.core.utils.symbol_fetcher import SymbolFetcher

# Global variables
required_exchanges: List[str] = []
symbol_fetcher = SymbolFetcher.get_instance()

# Global static values
KEYFILE_PREFIX = "key_file_"
KEYFILE_POSTFIX = ".json"
GLOBAL_CONFIG_PATH = "conf/conf_global.yml"
TOKEN_ADDRESSES_FILE_PATH = realpath(join(__file__, "../../wallet/ethereum/erc20_tokens.json"))
DEFAULT_KEY_FILE_PATH = "conf/"
DEFAULT_LOG_FILE_PATH = "logs/"
DEFAULT_ETHEREUM_RPC_URL = "https://mainnet.coinalpha.com/hummingbot-test-node"
TEMPLATE_PATH = realpath(join(__file__, "../../templates/"))
CONF_FILE_PATH = "conf/"
CONF_PREFIX = "conf_"
CONF_POSTFIX = "_strategy"

EXCHANGES = {
    "binance",
    "ddex",
    "radar_relay",
    "bamboo_relay",
    "coinbase_pro"
}

DEXES = {
    "ddex",
    "radar_relay",
    "bamboo_relay",
}

STRATEGIES = {
    "cross_exchange_market_making",
    "arbitrage",
    "discovery",
    "pure_market_making",
}

EXAMPLE_PAIRS = {
    "binance": "ZRXETH",
    "ddex": "ZRX-WETH",
    "radar_relay": "ZRX-WETH",
    "bamboo_relay": "ZRX-WETH",
    "coinbase_pro": "ETH-USDC",
}

MAXIMUM_OUTPUT_PANE_LINE_COUNT = 1000
MAXIMUM_LOG_PANE_LINE_COUNT = 1000

