import asyncio
from typing import TYPE_CHECKING, Optional

import pandas as pd

from hummingbot.client.config.config_helpers import save_to_yml
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.security import Security
from hummingbot.client.settings import GLOBAL_CONFIG_PATH, AllConnectorSettings
from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.connector_status import get_connector_status
from hummingbot.connector.other.celo.celo_cli import CeloCLI
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.user.user_balances import UserBalances

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

OPTIONS = {cs.name for cs in AllConnectorSettings.get_connector_settings().values()
           if not cs.use_ethereum_wallet and not cs.uses_gateway_generic_connector()}.union({"celo"})


class ConnectCommand:
    def connect(self,  # type: HummingbotApplication
                option: str):
        if option is None:
            safe_ensure_future(self.show_connections())
        elif option == "ethereum":
            safe_ensure_future(self.connect_ethereum())
        elif option == "celo":
            safe_ensure_future(self.connect_celo())
        else:
            safe_ensure_future(self.connect_exchange(option))

    async def connect_exchange(self,  # type: HummingbotApplication
                               exchange):
        # instruct users to use gateway connect if connector is a gateway connector
        if AllConnectorSettings.get_connector_settings()[exchange].uses_gateway_generic_connector():
            self.notify("This is a gateway connector. Use `gateway connect` command instead.")
            return

        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True
        if exchange == "kraken":
            self.notify("Reminder: Please ensure your Kraken API Key Nonce Window is at least 10.")
        exchange_configs = [c for c in global_config_map.values()
                            if c.key in AllConnectorSettings.get_connector_settings()[exchange].config_keys and c.is_connect_key]

        to_connect = True
        if Security.encrypted_file_exists(exchange_configs[0].key):
            await Security.wait_til_decryption_done()
            api_key_config = [c for c in exchange_configs if "api_key" in c.key]
            if api_key_config:
                api_key_config = api_key_config[0]
                api_key = Security.decrypted_value(api_key_config.key)
                prompt = f"Would you like to replace your existing {exchange} API key {api_key} (Yes/No)? >>> "
            else:
                prompt = f"Would you like to replace your existing {exchange_configs[0].key} (Yes/No)? >>> "
            answer = await self.app.prompt(prompt=prompt)
            if self.app.to_stop_config:
                self.app.to_stop_config = False
                return
            if answer.lower() not in ("yes", "y"):
                to_connect = False
        if to_connect:
            for config in exchange_configs:
                await self.prompt_a_config(config)
                if self.app.to_stop_config:
                    self.app.to_stop_config = False
                    return
                Security.update_secure_config(config.key, config.value)
            api_keys = await Security.api_keys(exchange)
            network_timeout = float(global_config_map["other_commands_timeout"].value)
            try:
                err_msg = await asyncio.wait_for(
                    UserBalances.instance().add_exchange(exchange, **api_keys), network_timeout
                )
            except asyncio.TimeoutError:
                self.notify("\nA network error prevented the connection to complete. See logs for more details.")
                self.placeholder_mode = False
                self.app.hide_input = False
                self.app.change_prompt(prompt=">>> ")
                raise
            if err_msg is None:
                self.notify(f"\nYou are now connected to {exchange}.")
            else:
                self.notify(f"\nError: {err_msg}")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

    async def show_connections(self  # type: HummingbotApplication
                               ):
        self.notify("\nTesting connections, please wait...")
        await Security.wait_til_decryption_done()
        df, failed_msgs = await self.connection_df()
        lines = ["    " + line for line in format_df_for_printout(df).split("\n")]
        if failed_msgs:
            lines.append("\nFailed connections:")
            lines.extend(["    " + k + ": " + v for k, v in failed_msgs.items()])
        self.notify("\n".join(lines))

    async def connection_df(self  # type: HummingbotApplication
                            ):
        columns = ["Exchange", "  Keys Added", "  Keys Confirmed", "  Status"]
        data = []
        failed_msgs = {}
        network_timeout = float(global_config_map["other_commands_timeout"].value)
        try:
            err_msgs = await asyncio.wait_for(
                UserBalances.instance().update_exchanges(reconnect=True), network_timeout
            )
        except asyncio.TimeoutError:
            self.notify("\nA network error prevented the connection table to populate. See logs for more details.")
            raise
        for option in sorted(OPTIONS):
            keys_added = "No"
            keys_confirmed = 'No'
            status = get_connector_status(option)
            if option == "celo":
                celo_address = global_config_map["celo_address"].value
                if celo_address is not None and Security.encrypted_file_exists("celo_password"):
                    keys_added = "Yes"
                    err_msg = await self.validate_n_connect_celo(True)
                    if err_msg is not None:
                        failed_msgs[option] = err_msg
                    else:
                        keys_confirmed = 'Yes'
            else:
                api_keys = (await Security.api_keys(option)).values()
                if len(api_keys) > 0:
                    keys_added = "Yes"
                    err_msg = err_msgs.get(option)
                    if err_msg is not None:
                        failed_msgs[option] = err_msg
                    else:
                        keys_confirmed = 'Yes'
            data.append([option, keys_added, keys_confirmed, status])
        return pd.DataFrame(data=data, columns=columns), failed_msgs

    async def connect_ethereum(self,  # type: HummingbotApplication
                               ):
        self.notify("\nError: Feature deprecated. Use 'gateway connect' instead.")

    async def connect_celo(self,  # type: HummingbotApplication
                           ):
        self.placeholder_mode = True
        self.app.hide_input = True
        celo_address = global_config_map["celo_address"].value
        to_connect = True
        if celo_address is not None:
            answer = await self.app.prompt(prompt=f"Would you like to replace your existing Celo account address "
                                                  f"{celo_address} (Yes/No)? >>> ")
            if answer.lower() not in ("yes", "y"):
                to_connect = False
        if to_connect:
            await self.prompt_a_config(global_config_map["celo_address"])
            await self.prompt_a_config(global_config_map["celo_password"])
            save_to_yml(GLOBAL_CONFIG_PATH, global_config_map)

            err_msg = await self.validate_n_connect_celo(True,
                                                         global_config_map["celo_address"].value,
                                                         global_config_map["celo_password"].value)
            if err_msg is None:
                self.notify("You are now connected to Celo network.")
            else:
                self.notify(err_msg)
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

    async def validate_n_connect_celo(self, to_reconnect: bool = False, celo_address: str = None,
                                      celo_password: str = None) -> Optional[str]:
        if celo_address is None:
            celo_address = global_config_map["celo_address"].value
        if celo_password is None:
            await Security.wait_til_decryption_done()
            celo_password = Security.decrypted_value("celo_password")
        if celo_address is None or celo_password is None:
            return "Celo address and/or password have not been added."
        if CeloCLI.unlocked and not to_reconnect:
            return None
        err_msg = CeloCLI.validate_node_synced()
        if err_msg is not None:
            return err_msg
        err_msg = CeloCLI.unlock_account(celo_address, celo_password)
        return err_msg
