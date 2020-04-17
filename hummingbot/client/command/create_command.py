import os
import shutil
from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.config_helpers import (
    get_strategy_config_map,
    parse_cvar_value,
    default_strategy_file_path,
    save_to_yml,
    get_strategy_template_path,
    missing_required_configs,
    format_config_file_name,
    parse_config_default_to_text
)
from hummingbot.client.settings import CONF_FILE_PATH
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.security import Security
from hummingbot.client.config.config_validators import validate_strategy, validate_bool
from hummingbot.user.user_balances import UserBalances
from hummingbot.client.ui.completer import load_completer
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class CreateCommand:
    def create(self,  # type: HummingbotApplication
               file_name):
        if file_name is not None:
            file_name = format_config_file_name(file_name)
            if os.path.exists(os.path.join(CONF_FILE_PATH, file_name)):
                self._notify(f"{file_name} already exists.")
                return

        safe_ensure_future(self.prompt_for_configuration(file_name))

    async def prompt_for_configuration(self,  # type: HummingbotApplication
                                       file_name):
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True
        strategy_config = ConfigVar(key="strategy",
                                    prompt="What is your market making strategy? >>> ",
                                    validator=validate_strategy)
        await self.prompt_a_config(strategy_config)
        strategy = strategy_config.value
        config_map = get_strategy_config_map(strategy)
        self._notify(f"Please see https://docs.hummingbot.io/strategies/{strategy.replace('_', '-')}/ "
                     f"while setting up these below configuration.")
        # assign default values and reset those not required
        for config in config_map.values():
            if config.required:
                config.value = config.default
            else:
                config.value = None
        for config in config_map.values():
            if config.prompt_on_new:
                await self.prompt_a_config(config)
            else:
                config.value = config.default
        if strategy == "pure_market_making" and not global_config_map.get("paper_trade_enabled").value:
            await self.asset_ratio_maintenance_prompt(config_map)
        if file_name is None:
            file_name = await self.prompt_new_file_name(strategy)
        strategy_path = os.path.join(CONF_FILE_PATH, file_name)
        template = get_strategy_template_path(strategy)
        shutil.copy(template, strategy_path)
        save_to_yml(strategy_path, config_map)
        self.strategy_file_name = file_name
        self.strategy_name = strategy
        # Reload completer here otherwise the new file will not appear
        self.app.input_field.completer = load_completer(self)
        self._notify(f"A new config file {self.strategy_file_name} created.")
        if not await self.notify_missing_configs():
            self._notify("Enter \"start\" to start market making.")
            self.app.set_text("start")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

    async def prompt_a_config(self,  # type: HummingbotApplication
                              config: ConfigVar,
                              input_value=None,
                              assign_default=True):
        if input_value is None:
            if assign_default:
                self.app.set_text(parse_config_default_to_text(config))
            input_value = await self.app.prompt(prompt=config.prompt, is_password=config.is_secure)
        err_msg = config.validate(input_value)
        if err_msg is not None:
            self._notify(err_msg)
            await self.prompt_a_config(config)
        else:
            config.value = parse_cvar_value(config, input_value)

    async def prompt_new_file_name(self,  # type: HummingbotApplication
                                   strategy):
        file_name = default_strategy_file_path(strategy)
        self.app.set_text(file_name)
        input = await self.app.prompt(prompt="Enter a new file name for your configuration >>> ")
        input = format_config_file_name(input)
        file_path = os.path.join(CONF_FILE_PATH, input)
        if input is None or input == "":
            self._notify(f"Value is required.")
            return await self.prompt_new_file_name(strategy)
        elif os.path.exists(file_path):
            self._notify(f"{input} file already exists, please enter a new name.")
            return await self.prompt_new_file_name(strategy)
        else:
            return input

    async def update_all_secure_configs(self  # type: HummingbotApplication
                                        ):
        await Security.wait_til_decryption_done()
        Security.update_config_map(global_config_map)
        if self.strategy_config_map is not None:
            Security.update_config_map(self.strategy_config_map)

    async def notify_missing_configs(self,  # type: HummingbotApplication
                                     ):
        await self.update_all_secure_configs()
        missing_globals = missing_required_configs(global_config_map)
        if missing_globals:
            self._notify("\nIncomplete global configuration (conf_global.yml). The following values are missing.\n")
            for config in missing_globals:
                self._notify(config.key)
        missing_configs = missing_required_configs(get_strategy_config_map(self.strategy_name))
        if missing_configs:
            self._notify(f"\nIncomplete strategy configuration ({self.strategy_file_name}). "
                         f"The following values are missing.\n")
            for config in missing_configs:
                self._notify(config.key)
        any_missing = missing_globals or missing_configs
        if any_missing:
            self._notify(f"\nPlease run config config_name (e.g. config kill_switch) "
                         f"to update the missing config values.")
        return any_missing

    async def asset_ratio_maintenance_prompt(self,  # type: HummingbotApplication
                                             config_map):
        exchange = config_map['exchange'].value
        market = config_map["market"].value
        base, quote = market.split("-")
        balances = await UserBalances.instance().balances(exchange, base, quote)
        if balances is None:
            return
        base_ratio = UserBalances.base_amount_ratio(market, balances)
        base_ratio = round(base_ratio, 3)
        quote_ratio = 1 - base_ratio
        base, quote = config_map["market"].value.split("-")
        cvar = ConfigVar(key="temp_config",
                         prompt=f"On {exchange}, you have {balances.get(base, 0):.4f} {base} and "
                                f"{balances.get(quote, 0):.4f} {quote}. By market value, "
                                f"your current inventory split is {base_ratio:.1%} {base} "
                                f"and {quote_ratio:.1%} {quote}."
                                f" Would you like to keep this ratio? (Yes/No) >>> ",
                         required_if=lambda: True,
                         type_str="bool",
                         validator=validate_bool)
        await self.prompt_a_config(cvar)
        if cvar.value:
            config_map['inventory_target_base_pct'].value = round(base_ratio * Decimal('100'), 1)
        else:
            await self.prompt_a_config(config_map["inventory_target_base_pct"])
