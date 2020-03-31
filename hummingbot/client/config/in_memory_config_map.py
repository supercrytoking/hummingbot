from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    is_path,
)
from hummingbot.client.settings import (
    CONF_POSTFIX,
    CONF_PREFIX,
)
from hummingbot.client.config.config_helpers import (
    read_configs_from_yml,
)


def get_default_strategy_config_yml_path(strategy: str) -> str:
    return f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_0.yml"


# Prompt generators
def default_strategy_conf_path_prompt():
    from hummingbot.client.config.global_config_map import global_config_map
    strategy = global_config_map.get("strategy").value
    return "Enter path to your strategy file (e.g. \"%s\") >>> " \
           % (get_default_strategy_config_yml_path(strategy),)


# These configs are never saved and prompted every time
in_memory_config_map = {
    # Always required
    "strategy_file_path":
        ConfigVar(key="strategy_file_path",
                  prompt=default_strategy_conf_path_prompt,
                  validator=is_path,
                  on_validated=read_configs_from_yml)
}
