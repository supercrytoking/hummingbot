# A single source of truth for constant variables related to the exchange
from typing import Dict, List
from hummingbot.core.api_throttler.data_types import RateLimit

EXCHANGE_NAME = "ascend_ex"
REST_URL = "https://ascendex.com/api/pro/v1"
WS_URL = "wss://ascendex.com/0/api/pro/v1/stream"
PONG_PAYLOAD = {"op": "pong"}

# AscendEx has multiple pools for API request limits
# Any call increases call rate in ALL pool, so e.g. a cash/order call will contribute to both ALL and cash/order pools.
REQUEST_CALL_LIMITS: Dict[str, RateLimit] = {
    "all_endpoints": RateLimit(limit_id="all_endpoints", limit=100, time_interval=1),
    "cash/order": RateLimit(limit_id="cash/order", limit=50, time_interval=1),
    "order/hist": RateLimit(limit_id="order/hist", limit=60, time_interval=60)
}

API_LIMITS: List[RateLimit] = [
    RateLimit(limit_id="ALL", limit=100, time_interval=1),
    RateLimit(limit_id="cash/order", limit=50, time_interval=1, linked_limits=["ALL"]),
    RateLimit(limit_id="order/hist", limit=60, time_interval=60, linked_limits=["ALL"])
]
