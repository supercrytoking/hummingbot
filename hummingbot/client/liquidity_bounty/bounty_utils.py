#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../")))

import aiohttp
import asyncio
import logging
import pandas as pd
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from sqlalchemy import (
    and_,
    or_,
)
from sqlalchemy.orm import (
    Session,
    Query,
)
from sqlalchemy.sql.elements import BooleanClauseList
from hummingbot.client.liquidity_bounty.liquidity_bounty_config_map import liquidity_bounty_config_map
from hummingbot.core.network_base import NetworkBase, NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.model.trade_fill import TradeFill


class LiquidityBounty(NetworkBase):
    lb_logger: Optional[HummingbotLogger] = None
    _lb_shared_instance: Optional["LiquidityBounty"] = None
    LIQUIDITY_BOUNTY_REST_API = "https://api.hummingbot.io/bounty"

    @classmethod
    def get_instance(cls) -> "LiquidityBounty":
        if cls._lb_shared_instance is None:
            cls._lb_shared_instance = LiquidityBounty()
        return cls._lb_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls.lb_logger is None:
            cls.lb_logger = logging.getLogger(__name__)
        return cls.lb_logger

    def __init__(self, update_interval: int = 60):
        super().__init__()
        self._update_interval = update_interval
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client: Optional[aiohttp.ClientSession] = None
        self._status: Dict[str, Any] = {}
        self._active_bounties: List[Dict[str, Any]] = []
        # timestamp = -1 when when no data has been fetched / timestamp = 0 when no trades have ever been submitted
        self._last_submitted_trade_timestamp: int = -1
        self._last_timestamp_fetched_event = asyncio.Event()
        self._active_bounties_fetched_event = asyncio.Event()

        self.fetch_active_bounties_task: Optional[asyncio.Task] = None
        self.status_polling_task: Optional[asyncio.Task] = None
        self.submit_trades_task: Optional[asyncio.Task] = None

    def status(self) -> Dict[str, Any]:
        return self._status

    def formatted_status(self) -> str:
        df: pd.DataFrame = pd.DataFrame(self._status.items())
        lines = ["", "  Client Status:"] + ["    " + line for line in df.to_string(index=False, header=False).split("\n")]
        return "\n".join(lines)

    def active_bounties(self) -> List[Dict[str, Any]]:
        return self._active_bounties

    def formatted_bounties(self) -> str:
        rows = [[
            bounty["market"],
            bounty["base_asset"],
            datetime.fromtimestamp(bounty["start_timestamp"] / 1e3).strftime("%m/%d/%Y %H:%M") if bounty["start_timestamp"] > 0 else "TBA",
            datetime.fromtimestamp(bounty["end_timestamp"] / 1e3).strftime("%m/%d/%Y %H:%M") if bounty["end_timestamp"] > 0 else "TBA",
            bounty["link"]
        ] for bounty in self._active_bounties]
        df: pd.DataFrame = pd.DataFrame(
            rows,
            columns=["Market", "Asset", "Start (MM/DD/YYYY)", "End (MM/DD/YYYY)", "More Info"]
        )
        lines = ["", "  Bounties:"] + ["    " + line for line in df.to_string(index=False).split("\n")]
        return "\n".join(lines)

    @staticmethod
    def format_volume_metrics(volume_metrics: List[Dict[str, Any]]) -> str:
        rows = [[
            vm["market"],
            vm["base_asset"],
            vm["total_filled_volume"],
            vm["total_filled_volume_in_session"],
            vm["trades_submitted_count"]
        ] for vm in volume_metrics]
        df: pd.DataFrame = pd.DataFrame(
            rows,
            columns=["Market", "Asset", "Filled Volume", "Filled volume in current session", "Total trades submitted"]
        )
        lines = ["", "  Volume Metrics:"] + ["    " + line for line in df.to_string(index=False).split("\n")]
        return "\n".join(lines)

    async def _wait_till_ready(self):
        if not self._last_timestamp_fetched_event.is_set():
            await self._last_timestamp_fetched_event.wait()
        if not self._active_bounties_fetched_event.is_set():
            await self._active_bounties_fetched_event.wait()

    async def get_unsubmitted_trades(self) -> List[TradeFill]:
        """ Get locally saved trades that have not been submitted to liquidity bounties """
        await self._wait_till_ready()
        session: Session = SQLConnectionManager.get_trade_fills_instance().get_shared_session()

        try:
            and_conditions: BooleanClauseList = [and_(
                TradeFill.base_asset == ab["base_asset"],
                TradeFill.market == ab["market"],
                TradeFill.timestamp >= ab["start_timestamp"], # does not matter if start_timestamp == -1
                TradeFill.timestamp <= (ab["end_timestamp"] if ab["end_timestamp"] > 0 else 1e14)
            ) for ab in self._active_bounties]

            query: Query = (session
                            .query(TradeFill)
                            .filter(TradeFill.timestamp > self._last_submitted_trade_timestamp)
                            .filter(or_(*and_conditions))
                            .order_by(TradeFill.timestamp))

            new_trades: List[TradeFill] = query.all()
            return new_trades
        except Exception as e:
            self.logger().error(f"Failed to query for unsubmitted trades: {str(e)}", exc_info=True)

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def fetch_active_bounties(self):
        """ fetch a list of active bounties from server. Only executed once. """
        try:
            client: aiohttp.ClientSession = await self._http_client()
            async with client.request("GET", f"{self.LIQUIDITY_BOUNTY_REST_API}/list") as resp:
                if resp.status not in {200, 400}:
                    raise Exception(f"Liquidity bounty server error. Server responded with status {resp.status}")
                results = await resp.json()
                self.logger().debug(results)
                self._active_bounties = results.get("bounties", [])
                self._active_bounties_fetched_event.set()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Failed to fetch active bounties: {str(e)}")

    async def register(self, email: Optional[str] = None, eth_address: Optional[str] = None) -> Dict[str, Any]:
        if email is None or eth_address is None:
            bounty_config: Dict[str, Any] = {key: cvar.value for key, cvar in liquidity_bounty_config_map.items()}
            assert bounty_config["liquidity_bounty_enabled"]
            assert bounty_config["agree_to_terms"]
            assert bounty_config["agree_to_data_collection"]
            assert bounty_config["final_confirmation"]

            email = bounty_config["email"]
            eth_address = bounty_config["eth_address"]

        try:
            client = await self._http_client()
            data = {"email": email, "eth_address": eth_address}
            async with client.request("POST", f"{self.LIQUIDITY_BOUNTY_REST_API}/client", json=data) as resp:
                # registration_status = "success" or <reason_for_failure>
                if resp.status not in {200, 400}:
                    raise Exception(f"Liquidity bounty server error. Server responded with status {resp.status}")

                results = await resp.json()
                if results["registration_status"] != "success":
                    raise Exception(f"Failed to register for liquidity bounty: {results['registration_status']}")
                return results
        except AssertionError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def authenticated_request(self, request_method: str, url: str, **kwargs) -> Dict[str, Any]:
        try:
            client = await self._http_client()
            client_id = liquidity_bounty_config_map.get("liquidity_bounty_client_id").value
            assert client_id is not None
            headers = {"Client-ID": client_id}

            async with client.request(request_method, url, headers=headers, **kwargs) as resp:
                results = await resp.json()
                if "error" in results:
                    raise Exception(results.get("error"))
                if resp.status == 500:
                    raise Exception(f"Server side error when submitting to {url}")
                if results.get("status", "") == "Unknown client id":
                    raise Exception("User not registered")
                return results
        except Exception as e:
            self.logger().network(f"Error in authenticated request: {str(e)}", exc_info=True)
            raise

    async def fetch_client_status(self):
        try:
            self._status = await self.authenticated_request("GET", f"{self.LIQUIDITY_BOUNTY_REST_API}/client")
        except Exception:
            raise

    async def fetch_last_timestamp(self):
        try:
            url = f"{self.LIQUIDITY_BOUNTY_REST_API}/trade/last_recorded_timestamp"
            results = await self.authenticated_request("GET", url)
            self._last_submitted_trade_timestamp = int(results.get("last_recorded_timestamp", -1))
            self._last_timestamp_fetched_event.set()
        except Exception:
            raise

    async def status_polling_loop(self):
        while True:
            try:
                await asyncio.gather([
                    await self.fetch_client_status(),
                    await self.fetch_last_timestamp(),
                ], loop=self._ev_loop)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if "User not registered" in str(e):
                    self.logger().warning("User not registered. Aborting fetch_client_status_loop.")
                    break
            await asyncio.sleep(self._update_interval)

    async def fetch_filled_volume_metrics(self, start_time: int) -> List[Dict[str, Any]]:
        try:
            url = f"{self.LIQUIDITY_BOUNTY_REST_API}/metrics"
            data = {"start_time": start_time}
            results: Dict[str, Any] = await self.authenticated_request("GET", url, json=data)
            if results["status"] != "success":
                raise Exception(str(results))
            return results["metrics"]
        except Exception as e:
            if "User not registered" in str(e):
                self.logger().warning("User not registered. Aborting fetch_filled_volume_metrics.")
            else:
                self.logger().error(f"Error fetching filled volume metrics: {str(e)}", exc_info=True)

    async def submit_trades(self):
        try:
            trades: List[TradeFill] = await self.get_unsubmitted_trades()
            formatted_trades: List[Dict[str, Any]] = [TradeFill.to_bounty_api_json(trade) for trade in trades]

            if self._last_submitted_trade_timestamp >= 0 and len(formatted_trades) > 0:
                url = f"{self.LIQUIDITY_BOUNTY_REST_API}/trade"
                results = await self.authenticated_request("POST", url, json={"trades": formatted_trades})
                self.logger().info(results)
                num_submitted = results.get("trades_submitted", 0)
                num_recorded = results.get("trades_recorded", 0)
                if num_submitted != num_recorded:
                    self.logger().warning(f"Failed to submit {num_submitted - num_recorded} trade(s)")
                if num_recorded > 0:
                    self.logger().info(f"Successfully sent {num_recorded} trade(s) to claim bounty")
        except Exception:
            raise

    async def submit_trades_loop(self):
        await self._wait_till_ready()
        while True:
            try:
                await self.submit_trades()
            except asyncio.CancelledError:
                    raise
            except asyncio.TimeoutError:
                    continue
            except Exception as e:
                if "User not registered" in str(e):
                    self.logger().warning("User not registered. Aborting submit_trades_loop.")
                    break
                else:
                    self.logger().error(f"Error submitting trades: {str(e)}", exc_info=True)
            await asyncio.sleep(self._update_interval)

    async def start_network(self):
        await self.stop_network()
        self.fetch_active_bounties_task = asyncio.ensure_future(self.fetch_active_bounties())
        self.status_polling_task = asyncio.ensure_future(self.status_polling_loop())
        self.submit_trades_task = asyncio.ensure_future(self.submit_trades_loop())

    async def stop_network(self):
        if self.fetch_active_bounties_task is not None:
            self.fetch_active_bounties_task.cancel()
            self.fetch_active_bounties_task = None
        if self.status_polling_task is not None:
            self.status_polling_task.cancel()
            self.status_polling_task = None
        if self.submit_trades_task is not None:
            self.submit_trades_task.cancel()
            self.submit_trades_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            client = await self._http_client()
            async with client.request("GET", f"{self.LIQUIDITY_BOUNTY_REST_API}/") as resp:
                if resp.status != 200:
                    raise Exception(f"Liquidity bounty server is down.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def start(self):
        NetworkBase.start(self)

    def stop(self):
        NetworkBase.stop(self)
