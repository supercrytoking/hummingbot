import sys

from hummingbot.core.api_throttler.data_types import RateLimit

MAX_ORDER_ID_LEN = 40

DEFAULT_DOMAIN = "main"
HB_PARTNER_ID = "Hummingbot"
HB_PARTNER_KEY = "8fb50686-81a8-408a-901c-07c5ac5bd758"

# REST endpoints
BASE_PATH_URL = {
    "main": "https://api.kucoin.com",
    "testnet": "https://openapi-sandbox.kucoin.com",
}
PUBLIC_WS_DATA_PATH_URL = "/api/v1/bullet-public"
PRIVATE_WS_DATA_PATH_URL = "/api/v1/bullet-private"
TICKER_PRICE_CHANGE_PATH_URL = "/api/v1/market/orderbook/level1"
SNAPSHOT_NO_AUTH_PATH_URL = "/api/v1/market/orderbook/level2_100"
ACCOUNTS_PATH_URL = "/api/v1/accounts"
SERVER_TIME_PATH_URL = "/api/v1/timestamp"
SYMBOLS_PATH_URL = "/api/v1/symbols"
ORDERS_PATH_URL = "/api/v1/orders"
FEE_PATH_URL = "/api/v1/trade-fees"

WS_CONNECTION_LIMIT_ID = "WSConnection"
WS_CONNECTION_LIMIT = 30
WS_CONNECTION_TIME_INTERVAL = 60
WS_REQUEST_LIMIT_ID = "WSRequest"
GET_ORDER_LIMIT_ID = "GetOrders"
POST_ORDER_LIMIT_ID = "PostOrder"
DELETE_ORDER_LIMIT_ID = "DeleteOrder"
WS_PING_HEARTBEAT = 10

DIFF_EVENT_TYPE = "trade.l2update"
TRADE_EVENT_TYPE = "trade.l3match"
ORDER_CHANGE_EVENT_TYPE = "orderChange"
BALANCE_EVENT_TYPE = "account.balance"

NO_LIMIT = sys.maxsize
RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=WS_CONNECTION_LIMIT, time_interval=WS_CONNECTION_TIME_INTERVAL),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=100, time_interval=10),
    RateLimit(limit_id=PUBLIC_WS_DATA_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=PRIVATE_WS_DATA_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SYMBOLS_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SNAPSHOT_NO_AUTH_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=GET_ORDER_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=FEE_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=POST_ORDER_LIMIT_ID, limit=45, time_interval=3),
    RateLimit(limit_id=DELETE_ORDER_LIMIT_ID, limit=60, time_interval=3),
]
