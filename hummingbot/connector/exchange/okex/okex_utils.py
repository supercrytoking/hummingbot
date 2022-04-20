from decimal import Decimal
import zlib

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.0015"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

KEYS = {
    "okex_api_key":
        ConfigVar(key="okex_api_key",
                  prompt="Enter your OKEx API key >>> ",
                  required_if=using_exchange("okex"),
                  is_secure=True,
                  is_connect_key=True),
    "okex_secret_key":
        ConfigVar(key="okex_secret_key",
                  prompt="Enter your OKEx secret key >>> ",
                  required_if=using_exchange("okex"),
                  is_secure=True,
                  is_connect_key=True),
    "okex_passphrase":
        ConfigVar(key="okex_passphrase",
                  prompt="Enter your OKEx passphrase key >>> ",
                  required_if=using_exchange("okex"),
                  is_secure=True,
                  is_connect_key=True),
}


def inflate(data):
    """decrypts the OKEx data.
    Copied from OKEx SDK: https://github.com/okex/V3-Open-API-SDK/blob/d8becc67af047726c66d9a9b29d99e99c595c4f7/okex-python-sdk-api/websocket_example.py#L46"""
    decompress = zlib.decompressobj(-zlib.MAX_WBITS)
    inflated = decompress.decompress(data)
    inflated += decompress._flush()
    return inflated.decode('utf-8')
