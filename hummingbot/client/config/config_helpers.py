import logging
import ruamel.yaml
from os.path import (
    join,
    isfile,
)
from collections import OrderedDict
import json
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
)
from os import listdir
import shutil

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.liquidity_bounty.liquidity_bounty_config_map import liquidity_bounty_config_map
from hummingbot.client.settings import (
    GLOBAL_CONFIG_PATH,
    TEMPLATE_PATH,
    CONF_FILE_PATH,
    CONF_POSTFIX,
    CONF_PREFIX,
    LIQUIDITY_BOUNTY_CONFIG_PATH,
    DEPRECATED_CONFIG_VALUES,
    TOKEN_ADDRESSES_FILE_PATH,
)

# Use ruamel.yaml to preserve order and comments in .yml file
yaml_parser = ruamel.yaml.YAML()


def parse_cvar_value(cvar: ConfigVar, value: Any) -> Any:
    if value is None:
        return None
    elif cvar.type == 'str':
        return str(value)
    elif cvar.type == 'list':
        if isinstance(value, str):
            if len(value) == 0:
                return []
            filtered: filter = filter(lambda x: x not in ['[', ']', '"', "'"], list(value))
            value = "".join(filtered).split(",")  # create csv and generate list
            return [s.strip() for s in value]  # remove leading and trailing whitespaces
        else:
            return value
    elif cvar.type == 'dict':
        if isinstance(value, str):
            value_json = value.replace("'", '"')  # replace single quotes with double quotes for valid JSON
            return json.loads(value_json)
        else:
            return value
    elif cvar.type == 'float':
        try:
            return float(value)
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not an integer.")
            return 0.0
    elif cvar.type == 'int':
        try:
            return int(value)
        except Exception:
            logging.getLogger().error(f"\"{value}\" is not an integer.")
            return 0
    elif cvar.type == 'bool':
        if isinstance(value, str) and value.lower() in ["true", "yes", "y"]:
            return True
        elif isinstance(value, str) and value.lower() in ["false", "no", "n"]:
            return False
        else:
            return bool(value)
    else:
        raise TypeError


async def copy_strategy_template(strategy: str) -> str:
    old_path = get_strategy_template_path(strategy)
    i = 0
    new_fname = f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml"
    new_path = join(CONF_FILE_PATH, new_fname)
    while isfile(new_path):
        new_fname = f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_{i}.yml"
        new_path = join(CONF_FILE_PATH, new_fname)
        i += 1
    shutil.copy(old_path, new_path)
    return new_fname


def get_strategy_template_path(strategy: str) -> str:
    return join(TEMPLATE_PATH, f"{CONF_PREFIX}{strategy}{CONF_POSTFIX}_TEMPLATE.yml")


def get_erc20_token_addresses(symbols: List[str]):
    with open(TOKEN_ADDRESSES_FILE_PATH) as f:
        try:
            data = json.load(f)
            addresses = [data[symbol] for symbol in symbols if symbol in data]
            return addresses
        except Exception as e:
            logging.getLogger().error(e, exc_info=True)


def _merge_dicts(*args: Dict[str, ConfigVar]) -> OrderedDict:
    result: OrderedDict[any] = OrderedDict()
    for d in args:
        result.update(d)
    return result


def get_strategy_config_map(strategy: str) -> Optional[Dict[str, ConfigVar]]:
    # Get the right config map from this file by its variable name
    if strategy is None:
        return None
    try:
        cm_key = f"{strategy}_config_map"
        strategy_module = __import__(f"hummingbot.strategy.{strategy}.{cm_key}",
                                     fromlist=[f"hummingbot.strategy.{strategy}"])
        return getattr(strategy_module, cm_key)
    except Exception as e:
        logging.getLogger().error(e, exc_info=True)


def get_strategy_starter_file(strategy: str) -> Callable:
    if strategy is None:
        return lambda: None
    try:
        strategy_module = __import__(f"hummingbot.strategy.{strategy}.start",
                                     fromlist=[f"hummingbot.strategy.{strategy}"])
        return getattr(strategy_module, "start")
    except Exception as e:
        logging.getLogger().error(e, exc_info=True)


def load_required_configs(*args) -> OrderedDict:
    from hummingbot.client.config.in_memory_config_map import in_memory_config_map
    current_strategy = in_memory_config_map.get("strategy").value
    current_strategy_file_path = in_memory_config_map.get("strategy_file_path").value
    if current_strategy is None or current_strategy_file_path is None:
        return _merge_dicts(in_memory_config_map)
    else:
        strategy_config_map = get_strategy_config_map(current_strategy)
        # create an ordered dict where `strategy` is inserted first
        # so that strategy-specific configs are prompted first and populate required_exchanges
        return _merge_dicts(in_memory_config_map, strategy_config_map, global_config_map)


def read_configs_from_yml(strategy_file_path: str = None):
    """
    Read global config and selected strategy yml files and save the values to corresponding config map
    """
    from hummingbot.client.config.in_memory_config_map import in_memory_config_map
    current_strategy = in_memory_config_map.get("strategy").value
    strategy_config_map = get_strategy_config_map(current_strategy)

    def load_yml_into_cm(yml_path: str, cm: Dict[str, ConfigVar]):
        try:
            with open(yml_path) as stream:
                data = yaml_parser.load(stream) or {}
                for key in data:
                    if current_strategy == "cross_exchange_market_making" and key == "trade_size_override":
                        logging.getLogger(__name__).error("Cross Exchange Strategy cannot be run with old config "
                                                          "file due to changes in strategy. "
                                                          "Please create a new config file.")
                    if key == "wallet":
                        continue
                    if key in DEPRECATED_CONFIG_VALUES:
                        continue
                    cvar = cm.get(key)
                    val_in_file = data.get(key)
                    if cvar is None:
                        logging.getLogger().warning(f"Cannot find corresponding config to key {key}.")
                        continue
                    cvar.value = val_in_file
                    if val_in_file is not None and not cvar.validate(val_in_file):
                        raise ValueError("Invalid value %s for config variable %s" % (val_in_file, cvar.key))
        except Exception as e:
            logging.getLogger().error("Error loading configs. Your config file may be corrupt. %s" % (e,),
                                      exc_info=True)

    load_yml_into_cm(GLOBAL_CONFIG_PATH, global_config_map)
    load_yml_into_cm(LIQUIDITY_BOUNTY_CONFIG_PATH, liquidity_bounty_config_map)
    if strategy_file_path:
        load_yml_into_cm(join(CONF_FILE_PATH, strategy_file_path), strategy_config_map)


async def save_to_yml(yml_path: str, cm: Dict[str, ConfigVar]):
    try:
        with open(yml_path) as stream:
            data = yaml_parser.load(stream) or {}
            for key in cm:
                cvar = cm.get(key)
                data[key] = cvar.value
            with open(yml_path, "w+") as outfile:
                yaml_parser.dump(data, outfile)
    except Exception as e:
        logging.getLogger().error("Error writing configs: %s" % (str(e),), exc_info=True)


async def write_config_to_yml():
    """
    Write current config saved in config maps into each corresponding yml file
    """
    from hummingbot.client.config.in_memory_config_map import in_memory_config_map
    current_strategy = in_memory_config_map.get("strategy").value
    strategy_file_path = in_memory_config_map.get("strategy_file_path").value

    if current_strategy is not None and strategy_file_path is not None:
        strategy_config_map = get_strategy_config_map(current_strategy)
        strategy_file_path = join(CONF_FILE_PATH, strategy_file_path)
        await save_to_yml(strategy_file_path, strategy_config_map)

    await save_to_yml(GLOBAL_CONFIG_PATH, global_config_map)


async def create_yml_files():
    for fname in listdir(TEMPLATE_PATH):
        # Only copy `hummingbot_logs.yml` and `conf_global.yml` on start up
        if "_TEMPLATE" in fname and CONF_POSTFIX not in fname:
            stripped_fname = fname.replace("_TEMPLATE", "")
            template_path = join(TEMPLATE_PATH, fname)
            conf_path = join(CONF_FILE_PATH, stripped_fname)
            if not isfile(conf_path):
                shutil.copy(template_path, conf_path)
            with open(template_path, "r") as template_fd:
                template_data = yaml_parser.load(template_fd)
                template_version = template_data.get("template_version", 0)
            with open(conf_path, "r") as conf_fd:
                conf_version = 0
                try:
                    conf_data = yaml_parser.load(conf_fd)
                    conf_version = conf_data.get("template_version", 0)
                except Exception:
                    pass
            if conf_version < template_version:
                shutil.copy(template_path, conf_path)
