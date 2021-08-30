import sys

from hummingbot.core.api_throttler.data_types import RateLimit

# REST endpoints
BASE_PATH_URL = "https://api.kucoin.com"
PUBLIC_WS_DATA_PATH_URL = "/api/v1/bullet-public"
PRIVATE_WS_DATA_PATH_URL = "/api/v1/bullet-private"
TICKER_PRICE_CHANGE_PATH_URL = "/api/v1/market/allTickers"
EXCHANGE_INFO_PATH_URL = "/api/v1/symbols"
SNAPSHOT_PATH_URL = "/api/v3/market/orderbook/level2"
SNAPSHOT_NO_AUTH_PATH_URL = "/api/v1/market/orderbook/level2_100"
ACCOUNTS_PATH_URL = "/api/v1/accounts"
SERVER_TIME_PATH_URL = "/api/v1/timestamp"
SYMBOLS_PATH_URL = "/api/v1/symbols"
ORDERS_PATH_URL = "/api/v1/orders"

WS_CONNECTION_LIMIT_ID = "WSConnection"
WS_REQUEST_LIMIT_ID = "WSRequest"
GET_ORDER_LIMIT_ID = "GetOrders"
POST_ORDER_LIMIT_ID = "PostOrder"
DELETE_ORDER_LIMIT_ID = "DeleteOrder"

NO_LIMIT = sys.maxsize
RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=30, time_interval=60),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=100, time_interval=10),
    RateLimit(limit_id=PUBLIC_WS_DATA_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SNAPSHOT_NO_AUTH_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=GET_ORDER_LIMIT_ID, limit=NO_LIMIT, time_interval=1),
    RateLimit(limit_id=POST_ORDER_LIMIT_ID, limit=3, time_interval=3),
    RateLimit(limit_id=DELETE_ORDER_LIMIT_ID, limit=60, time_interval=3),
]
