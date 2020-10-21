from hummingbot.client.config.security import Security
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.user.user_balances import UserBalances
from hummingbot.client.config.config_helpers import save_to_yml
import hummingbot.client.settings as settings
from hummingbot.market.celo.celo_cli import CeloCLI
import pandas as pd
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication

DERIVATIVES = settings.DERIVATIVES
OPTIONS = settings.CEXES.union({"ethereum", "celo"}).union(DERIVATIVES)


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
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True
        paper_trade = "testnet" if global_config_map.get("paper_trade_enabled").value else None
        if exchange == "kraken":
            self._notify("Reminder: Please ensure your Kraken API Key Nonce Window is at least 10.")
        if paper_trade and exchange in DERIVATIVES:
            self._notify("\nTo connect or change mainnet keys, turn off paper mode.")
            exchange_configs = [c for c in global_config_map.values() if exchange in c.key and c.is_connect_key and paper_trade in c.key]
        else:
            self._notify("\nTo connect or change testnet keys, turn on paper mode.")
            exchange_configs = [c for c in global_config_map.values() if exchange in c.key and c.is_connect_key]
        to_connect = True
        if Security.encrypted_file_exists(exchange_configs[0].key):
            await Security.wait_til_decryption_done()

            api_key_config = [c for c in exchange_configs if "api_key" in c.key][0]
            api_key = Security.decrypted_value(api_key_config.key)
            answer = await self.app.prompt(prompt=f"Would you like to replace your existing {exchange} {paper_trade} API key "
                                                  f"{api_key} (Yes/No)? >>> ")
            if self.app.to_stop_config:
                self.app.to_stop_config = False
                return
            if answer.lower() not in ("yes", "y"):
                to_connect = False
        if to_connect:
            api_keys = {}
            for config in exchange_configs:
                await self.prompt_a_config(config)
                if self.app.to_stop_config:
                    self.app.to_stop_config = False
                    return
                Security.update_secure_config(config.key, config.value)
                api_keys[config.key] = config.value
            err_msg = await UserBalances.instance().add_exchange(exchange, **api_keys)
            if err_msg is None:
                self._notify(f"\nYou are now connected to {exchange} {paper_trade}.")
            else:
                self._notify(f"\n{paper_trade.capitalize()} Error: {err_msg}")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

    async def show_connections(self  # type: HummingbotApplication
                               ):
        self._notify("\nTesting connections, please wait...")
        await Security.wait_til_decryption_done()
        df, failed_msgs = await self.connection_df()
        lines = ["    " + line for line in df.to_string(index=False).split("\n")]
        if failed_msgs:
            lines.append("\nFailed connections:")
            lines.extend(["    " + k + ": " + v for k, v in failed_msgs.items()])
        self._notify("\n".join(lines))

    async def connection_df(self  # type: HummingbotApplication
                            ):
        columns = ["Exchange", "  Keys Added", "  Keys Confirmed"]
        data = []
        failed_msgs = {}
        err_msgs = await UserBalances.instance().update_exchanges(reconnect=True)
        for option in sorted(OPTIONS):
            keys_added = "No"
            keys_confirmed = 'No'
            if option == "ethereum":
                eth_address = global_config_map["ethereum_wallet"].value
                if eth_address is not None and eth_address in Security.private_keys():
                    keys_added = "Yes"
                    err_msg = UserBalances.validate_ethereum_wallet()
                    if err_msg is not None:
                        failed_msgs[option] = err_msg
                    else:
                        keys_confirmed = 'Yes'
                data.append([option, keys_added, keys_confirmed])
            elif option == "celo":
                celo_address = global_config_map["celo_address"].value
                if celo_address is not None and Security.encrypted_file_exists("celo_password"):
                    keys_added = "Yes"
                    err_msg = await self.validate_n_connect_celo(True)
                    if err_msg is not None:
                        failed_msgs[option] = err_msg
                    else:
                        keys_confirmed = 'Yes'
                data.append([option, keys_added, keys_confirmed])
            elif option in DERIVATIVES:
                # check keys for main and testnet derivative keys_added
                api_keys = (await Security.api_keys(option)).keys()
                testnet_checked = False
                mainet_checked = False
                for api_key in api_keys:
                    if "testnet" in api_key and testnet_checked is False:
                        testnet_checked = True
                        keys_added = "Yes"
                        err_msg = err_msgs.get(option + "testnet")
                        if err_msg is not None:
                            failed_msgs[option] = err_msg
                        else:
                            keys_confirmed = 'Yes'
                        data.append([option + "(testnet)", keys_added, keys_confirmed])
                    elif "testnet" not in api_key and mainet_checked is False:
                        mainet_checked = True
                        keys_added = "Yes"
                        err_msg = err_msgs.get(option)
                        if err_msg is not None:
                            failed_msgs[option] = err_msg
                        else:
                            keys_confirmed = 'Yes'
                        data.append([option + "(mainnet)", keys_added, keys_confirmed])
            else:
                api_keys = (await Security.api_keys(option)).values()
                if len(api_keys) > 0:
                    keys_added = "Yes"
                    err_msg = err_msgs.get(option)
                    if err_msg is not None:
                        failed_msgs[option] = err_msg
                    else:
                        keys_confirmed = 'Yes'
                data.append([option, keys_added, keys_confirmed])
        return pd.DataFrame(data=data, columns=columns), failed_msgs

    async def connect_ethereum(self,  # type: HummingbotApplication
                               ):
        self.placeholder_mode = True
        self.app.hide_input = True
        ether_wallet = global_config_map["ethereum_wallet"].value
        to_connect = True
        if ether_wallet is not None:
            answer = await self.app.prompt(prompt=f"Would you like to replace your existing Ethereum wallet "
                                                  f"{ether_wallet} (Yes/No)? >>> ")
            if self.app.to_stop_config:
                self.app.to_stop_config = False
                return
            if answer.lower() not in ("yes", "y"):
                to_connect = False
        if to_connect:
            private_key = await self.app.prompt(prompt="Enter your wallet private key >>> ", is_password=True)
            public_address = Security.add_private_key(private_key)
            global_config_map["ethereum_wallet"].value = public_address
            if global_config_map["ethereum_rpc_url"].value is None:
                await self.prompt_a_config(global_config_map["ethereum_rpc_url"])
            if global_config_map["ethereum_rpc_ws_url"].value is None:
                await self.prompt_a_config(global_config_map["ethereum_rpc_ws_url"])
            if self.app.to_stop_config:
                self.app.to_stop_config = False
                return
            save_to_yml(settings.GLOBAL_CONFIG_PATH, global_config_map)
            err_msg = UserBalances.validate_ethereum_wallet()
            if err_msg is None:
                self._notify(f"Wallet {public_address} connected to hummingbot.")
            else:
                self._notify(f"\nError: {err_msg}")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

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
            save_to_yml(settings.GLOBAL_CONFIG_PATH, global_config_map)

            err_msg = await self.validate_n_connect_celo(True,
                                                         global_config_map["celo_address"].value,
                                                         global_config_map["celo_password"].value)
            if err_msg is None:
                self._notify("You are now connected to Celo network.")
            else:
                self._notify(err_msg)
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
