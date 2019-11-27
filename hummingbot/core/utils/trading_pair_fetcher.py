import aiohttp
from typing import (
    List,
    Dict,
    Any,
)

from hummingbot.core.utils.async_utils import safe_ensure_future


BINANCE_ENDPOINT = "https://api.binance.com/api/v1/exchangeInfo"
DDEX_ENDPOINT = "https://api.ddex.io/v3/markets"
RADAR_RELAY_ENDPOINT = "https://api.radarrelay.com/v2/markets"
BAMBOO_RELAY_ENDPOINT = "https://rest.bamboorelay.com/main/0x/markets"
COINBASE_PRO_ENDPOINT = "https://api.pro.coinbase.com/products/"
IDEX_REST_ENDPOINT = "https://api.idex.market/returnTicker"
HUOBI_ENDPOINT = "https://api.huobi.pro/v1/common/symbols"
BITTREX_ENDPOINT = "https://api.bittrex.com/v3/markets"
DOLOMITE_ENDPOINT = "https://exchange-api.dolomite.io/v1/markets"

API_CALL_TIMEOUT = 5


class TradingPairFetcher:
    _sf_shared_instance: "TradingPairFetcher" = None

    @classmethod
    def get_instance(cls) -> "TradingPairFetcher":
        if cls._sf_shared_instance is None:
            cls._sf_shared_instance = TradingPairFetcher()
        return cls._sf_shared_instance

    def __init__(self):
        self.ready = False
        self.trading_pairs: Dict[str, Any] = {}
        safe_ensure_future(self.fetch_all())

    @staticmethod
    async def fetch_binance_trading_pairs() -> List[str]:
        from hummingbot.market.binance.binance_market import BinanceMarket

        async with aiohttp.ClientSession() as client:
            async with client.get(BINANCE_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        trading_pair_structs = data.get("symbols")
                        raw_trading_pairs = list(map(lambda details: details.get("symbol"), trading_pair_structs))
                        # Binance API has an error where they have a symbol called 123456
                        # The symbol endpoint is
                        # https://api.binance.com/api/v1/exchangeInfo
                        if "123456" in raw_trading_pairs:
                            raw_trading_pairs.remove("123456")
                        return [BinanceMarket.convert_from_exchange_trading_pair(p) for p in raw_trading_pairs]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for binance trading pairs
                return []

    @staticmethod
    async def fetch_ddex_trading_pairs() -> List[str]:
        from hummingbot.market.ddex.ddex_market import DDEXMarket

        async with aiohttp.ClientSession() as client:
            async with client.get(DDEX_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        response = await response.json()
                        markets = response.get("data").get("markets")
                        raw_trading_pairs = list(map(lambda details: details.get('id'), markets))
                        return [DDEXMarket.convert_from_exchange_trading_pair(p) for p in raw_trading_pairs]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for ddex trading pairs
                return []

    @staticmethod
    async def fetch_radar_relay_trading_pairs() -> List[str]:
        from hummingbot.market.radar_relay.radar_relay_market import RadarRelayMarket

        trading_pairs = set()
        page_count = 1
        while True:
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{RADAR_RELAY_ENDPOINT}?perPage=100&page={page_count}", timeout=API_CALL_TIMEOUT) \
                        as response:
                    if response.status == 200:
                        try:
                            markets = await response.json()
                            new_trading_pairs = set(map(lambda details: details.get('id'), markets))
                            if len(new_trading_pairs) == 0:
                                break
                            else:
                                trading_pairs = trading_pairs.union(new_trading_pairs)
                            page_count += 1
                        except Exception:
                            # Do nothing if the request fails -- there will be no autocomplete for radar trading pairs
                            break
        return [RadarRelayMarket.convert_from_exchange_trading_pair(p) for p in trading_pairs]

    @staticmethod
    async def fetch_bamboo_relay_trading_pairs() -> List[str]:
        from hummingbot.market.bamboo_relay.bamboo_relay_market import BambooRelayMarket

        trading_pairs = set()
        page_count = 1
        while True:
            async with aiohttp.ClientSession() as client:
                async with client.get(f"{BAMBOO_RELAY_ENDPOINT}?perPage=1000&page={page_count}",
                                      timeout=API_CALL_TIMEOUT) as response:
                    if response.status == 200:
                        try:
                            markets = await response.json()
                            new_trading_pairs = set(map(lambda details: details.get('id'), markets))
                            if len(new_trading_pairs) == 0:
                                break
                            else:
                                trading_pairs = trading_pairs.union(new_trading_pairs)
                            page_count += 1
                        except Exception:
                            # Do nothing if the request fails -- there will be no autocomplete for bamboo trading pairs
                            break
        return [BambooRelayMarket.convert_from_exchange_trading_pair(p) for p in trading_pairs]

    @staticmethod
    async def fetch_coinbase_pro_trading_pairs() -> List[str]:
        from hummingbot.market.coinbase_pro.coinbase_pro_market import CoinbaseProMarket

        async with aiohttp.ClientSession() as client:
            async with client.get(COINBASE_PRO_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        markets = await response.json()
                        raw_trading_pairs: List[str] = list(map(lambda details: details.get('id'), markets))
                        return [CoinbaseProMarket.convert_from_exchange_trading_pair(p) for p in raw_trading_pairs]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for coinbase trading pairs
                return []

    @staticmethod
    async def fetch_idex_trading_pairs() -> List[str]:
        from hummingbot.market.idex.idex_market import IDEXMarket

        async with aiohttp.ClientSession() as client:
            async with client.get(IDEX_REST_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        market: Dict[Any] = await response.json()
                        raw_trading_pairs: List[str] = list(market.keys())
                        return [IDEXMarket.convert_from_exchange_trading_pair(p) for p in raw_trading_pairs]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for idex trading pairs
                return []

    @staticmethod
    async def fetch_huobi_trading_pairs() -> List[str]:
        from hummingbot.market.huobi.huobi_market import HuobiMarket

        async with aiohttp.ClientSession() as client:
            async with client.get(HUOBI_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        all_trading_pairs: Dict[str, any] = await response.json()
                        valid_trading_pairs: list = []
                        for item in all_trading_pairs["data"]:
                            if item["state"] == "online":
                                valid_trading_pairs.append(item["symbol"])
                        return [HuobiMarket.convert_from_exchange_trading_pair(p) for p in valid_trading_pairs]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for huobi trading pairs
                return []

    @staticmethod
    async def fetch_bittrex_trading_pairs() -> List[str]:
        async with aiohttp.ClientSession() as client:
            async with client.get(BITTREX_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        all_trading_pairs: List[Dict[str, any]] = await response.json()
                        return [item["symbol"]
                                for item in all_trading_pairs
                                if item["status"] == "ONLINE"]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for bittrex trading pairs
                return []

    @staticmethod
    async def fetch_dolomite_trading_pairs() -> List[str]:
        from hummingbot.market.dolomite.dolomite_market import DolomiteMarket

        async with aiohttp.ClientSession() as client:
            async with client.get(DOLOMITE_ENDPOINT, timeout=API_CALL_TIMEOUT) as response:
                if response.status == 200:
                    try:
                        all_trading_pairs: Dict[str, any] = await response.json()
                        valid_trading_pairs: list = []
                        for item in all_trading_pairs["data"]:
                            valid_trading_pairs.append(item["market"])
                        return [DolomiteMarket.convert_from_exchange_trading_pair(p) for p in valid_trading_pairs]
                    except Exception:
                        pass
                        # Do nothing if the request fails -- there will be no autocomplete for dolomite trading pairs
                return []

    async def fetch_all(self):
        binance_trading_pairs = await self.fetch_binance_trading_pairs()
        ddex_trading_pairs = await self.fetch_ddex_trading_pairs()
        radar_relay_trading_pairs = await self.fetch_radar_relay_trading_pairs()
        bamboo_relay_trading_pairs = await self.fetch_bamboo_relay_trading_pairs()
        coinbase_pro_trading_pairs = await self.fetch_coinbase_pro_trading_pairs()
        dolomite_trading_pairs = await self.fetch_dolomite_trading_pairs()
        huobi_trading_pairs = await self.fetch_huobi_trading_pairs()
        idex_trading_pairs = await self.fetch_idex_trading_pairs()
        bittrex_trading_pairs = await self.fetch_bittrex_trading_pairs()
        self.trading_pairs = {
            "binance": binance_trading_pairs,
            "dolomite": dolomite_trading_pairs,
            "idex": idex_trading_pairs,
            "ddex": ddex_trading_pairs,
            "radar_relay": radar_relay_trading_pairs,
            "bamboo_relay": bamboo_relay_trading_pairs,
            "coinbase_pro": coinbase_pro_trading_pairs,
            "huobi": huobi_trading_pairs,
            "bittrex": bittrex_trading_pairs,
        }
        self.ready = True
