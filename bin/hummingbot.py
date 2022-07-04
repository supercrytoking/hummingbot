#!/usr/bin/env python

import asyncio
from typing import Coroutine, List
from weakref import ReferenceType, ref

import path_util  # noqa: F401

from bin.docker_connection import fork_and_start
from hummingbot import chdir_to_data_directory, init_logging
from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import (
    ClientConfigAdapter,
    create_yml_files_legacy,
    load_client_config_map_from_file,
    write_config_to_yml,
)
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.client.ui import login_prompt
from hummingbot.client.ui.style import load_style
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import HummingbotUIEvent
from hummingbot.core.gateway import start_existing_gateway_container
from hummingbot.core.utils import detect_available_port
from hummingbot.core.utils.async_utils import safe_gather


class UIStartListener(EventListener):
    def __init__(self, hummingbot_app: HummingbotApplication):
        super().__init__()
        self._hb_ref: ReferenceType = ref(hummingbot_app)

    def __call__(self, _):
        asyncio.create_task(self.ui_start_handler())

    @property
    def hummingbot_app(self) -> HummingbotApplication:
        return self._hb_ref()

    async def ui_start_handler(self):
        hb: HummingbotApplication = self.hummingbot_app
        if hb.strategy_config_map is not None:
            write_config_to_yml(hb.strategy_config_map, hb.strategy_file_name, hb.client_config_map)
            hb.start(self._hb_ref.client_config_map.log_level)


async def main_async(client_config_map: ClientConfigAdapter):
    await create_yml_files_legacy()

    # This init_logging() call is important, to skip over the missing config warnings.
    init_logging("hummingbot_logs.yml", client_config_map)

    AllConnectorSettings.initialize_paper_trade_settings(client_config_map.paper_trade.paper_trade_exchanges)

    hb = HummingbotApplication.main_application(client_config_map)

    # The listener needs to have a named variable for keeping reference, since the event listener system
    # uses weak references to remove unneeded listeners.
    start_listener: UIStartListener = UIStartListener(hb)
    hb.app.add_listener(HummingbotUIEvent.Start, start_listener)

    tasks: List[Coroutine] = [hb.run(), start_existing_gateway_container(client_config_map)]
    if client_config_map.debug_console:
        if not hasattr(__builtins__, "help"):
            import _sitebuiltins
            __builtins__.help = _sitebuiltins._Helper()

        from hummingbot.core.management.console import start_management_console
        management_port: int = detect_available_port(8211)
        tasks.append(start_management_console(locals(), host="localhost", port=management_port))
    await safe_gather(*tasks)


def main():
    chdir_to_data_directory()
    secrets_manager_cls = ETHKeyFileSecretManger
    ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    client_config_map = load_client_config_map_from_file()
    if login_prompt(secrets_manager_cls, style=load_style(client_config_map)):
        ev_loop.run_until_complete(main_async(client_config_map))


if __name__ == "__main__":
    fork_and_start(main)
