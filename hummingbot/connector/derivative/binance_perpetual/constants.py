from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

EXCHANGE_NAME = "binance_perpetual"

PERPETUAL_BASE_URL = "https://fapi.binance.com/fapi/"
TESTNET_BASE_URL = "https://testnet.binancefuture.com/fapi/"

PERPETUAL_WS_URL = "wss://fstream.binance.com/"
TESTNET_WS_URL = "wss://stream.binancefuture.com/"

PUBLIC_WS_ENDPOINT = "stream"
PRIVATE_WS_ENDPOINT = "ws"

API_VERSION = "v1"
API_VERSION_V2 = "v2"


# Public API v1 Endpoints
SNAPSHOT_REST_URL = "/depth"
TICKER_PRICE_URL = "/ticker/bookTicker"
TICKER_PRICE_CHANGE_URL = "/ticker/24hr"
EXCHANGE_INFO_URL = "/exchangeInfo"
RECENT_TRADES_URL = "/trades"
PING_URL = "/ping"

# Private API v1 Endpoints
ORDER_URL = "/order"
CANCEL_ALL_OPEN_ORDERS_URL = "/allOpenOrders"
ACCOUNT_TRADE_LIST_URL = "/userTrades"  # w=5
SET_LEVERAGE_URL = "/leverage"  # w=1
GET_INCOME_HISTORY_URL = "/income"  # w=30
CHANGE_POSITION_MODE_URL = "/positionSide/dual"  # GET w=30, POST w=1

POST_POSITION_MODE_LIMIT_ID = f"POST{CHANGE_POSITION_MODE_URL}"
GET_POSITION_MODE_LIMIT_ID = f"GET{CHANGE_POSITION_MODE_URL}"

# Private API v2 Endpoints
ACCOUNT_INFO_URL = "/account"  # w=5
POSITION_INFORMATION_URL = "/positionRisk"  # GET w=5


# Private API Endpoints
BINANCE_USER_STREAM_ENDPOINT = "/listenKey"

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS_1MIN = "ORDERS_1MIN"
ORDERS_1SEC = "ORDERS_1SEC"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 2400

RATE_LIMITS = [
    # Pool Limits
    RateLimit(limit_id=REQUEST_WEIGHT, limit=2400, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS_1MIN, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS_1SEC, limit=300, time_interval=10),
    # Weight Limits for individual endpoints
    RateLimit(limit_id=BINANCE_USER_STREAM_ENDPOINT, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=PING_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=ORDER_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1),
                             LinkedLimitWeightPair(ORDERS_1MIN, weight=1),
                             LinkedLimitWeightPair(ORDERS_1SEC, weight=1)]),
    RateLimit(limit_id=CANCEL_ALL_OPEN_ORDERS_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=ACCOUNT_TRADE_LIST_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=SET_LEVERAGE_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=GET_INCOME_HISTORY_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=30)]),
    RateLimit(limit_id=POST_POSITION_MODE_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=1)]),
    RateLimit(limit_id=GET_POSITION_MODE_LIMIT_ID, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=30)]),
    RateLimit(limit_id=ACCOUNT_INFO_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
    RateLimit(limit_id=POSITION_INFORMATION_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE, weight=5,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, weight=5)]),
]
