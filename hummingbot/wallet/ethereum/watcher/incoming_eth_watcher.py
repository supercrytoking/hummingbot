#!/usr/bin/env python

import asyncio
import cytoolz
from typing import (
    List,
    Set,
    Iterable,
    Dict
)
from web3 import Web3
from web3.datastructures import AttributeDict

import hummingbot
from hummingbot.core.event.events import (
    NewBlocksWatcherEvent,
    IncomingEthWatcherEvent,
    WalletReceivedAssetEvent
)
from hummingbot.core.event.event_forwarder import EventForwarder
from .base_watcher import BaseWatcher
from .new_blocks_watcher import NewBlocksWatcher


class IncomingEthWatcher(BaseWatcher):
    def __init__(self,
                 w3: Web3,
                 blocks_watcher: NewBlocksWatcher,
                 watch_addresses: Iterable[str]):
        super().__init__(w3)
        self._watch_addresses: Set[str] = set(watch_addresses)
        self._blocks_watcher: NewBlocksWatcher = blocks_watcher
        self._event_forwarder: EventForwarder = EventForwarder(self.did_receive_new_blocks)

    async def start_network(self):
        self._blocks_watcher.add_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)

    async def stop_network(self):
        self._blocks_watcher.remove_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)

    def did_receive_new_blocks(self, new_blocks: List[AttributeDict]):
        asyncio.ensure_future(self.check_incoming_eth(new_blocks))

    async def check_incoming_eth(self, new_blocks: List[AttributeDict]):
        watch_addresses: Set[str] = self._watch_addresses
        filtered_blocks: List[AttributeDict] = [block for block in new_blocks if block is not None]
        block_to_timestamp: Dict[str, float] = dict((block.hash, float(block.timestamp))
                                                    for block in filtered_blocks)
        transactions: List[AttributeDict] = list(cytoolz.concat(b.transactions for b in filtered_blocks))
        incoming_eth_transactions: List[AttributeDict] = [t for t in transactions
                                                          if ((t.get("to") in watch_addresses) and
                                                              (t.get("value", 0) > 0))]

        get_receipt_tasks: List[asyncio.Task] = [
            self._ev_loop.run_in_executor(
                hummingbot.get_executor(),
                self._w3.eth.getTransactionReceipt,
                t.hash
            )
            for t in incoming_eth_transactions
        ]
        transaction_receipts: List[AttributeDict] = await asyncio.gather(*get_receipt_tasks)

        for incoming_transaction, receipt in zip(incoming_eth_transactions, transaction_receipts):
            # Filter out failed transactions.
            if receipt.status != 1:
                continue

            # Emit event.
            raw_eth_value: int = incoming_transaction.get("value")
            eth_value: float = raw_eth_value * 1e-18
            from_address: str = incoming_transaction.get("from")
            to_address: str = incoming_transaction.get("to")
            timestamp: float = block_to_timestamp[incoming_transaction.get("blockHash")]
            self.trigger_event(IncomingEthWatcherEvent.ReceivedEther,
                               WalletReceivedAssetEvent(timestamp, incoming_transaction.hash.hex(),
                                                        from_address, to_address, "ETH", eth_value, raw_eth_value))
