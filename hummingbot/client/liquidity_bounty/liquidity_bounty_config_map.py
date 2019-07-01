from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import MIN_ETH_STAKED_REQUIREMENT


def liquidity_bounty_enabled():
    return liquidity_bounty_config_map.get("liquidity_bounty_enabled").value is True


liquidity_bounty_config_map = {
    "liquidity_bounty_enabled":         ConfigVar(key="liquidity_bounty_enabled",
                                                  prompt="Would you like to participate in the Liquidity Bounties "
                                                         "program (y/n) ? >>> ",
                                                  required_if=lambda: True,
                                                  type_str="bool",
                                                  default=False),
    "agree_to_terms":                   ConfigVar(key="agree_to_terms",
                                                  prompt="Do you confirm that you agree with the above Terms and "
                                                         "Conditions for the Liquidity Bounties program (y/n) ? >>> ",
                                                  required_if=liquidity_bounty_enabled,
                                                  type_str="bool",
                                                  default=False),
    "agree_to_data_collection":         ConfigVar(key="agree_to_data_collection",
                                                  prompt="Do you give permission for us to collect the above data? "
                                                         "We need this data to verify your trading volume and ensure "
                                                         "accurate, fair bounty payouts. (y/n) ? >>> ",
                                                  required_if=liquidity_bounty_enabled,
                                                  type_str="bool",
                                                  default=False),

    "eth_address":                      ConfigVar(key="eth_address",
                                                  prompt=f"Please enter your Ethereum wallet address (This is the "
                                                         f"wallet to which we will send the bounty payouts. Please "
                                                         f"also make sure you maintain a minimum balance "
                                                         f"of {MIN_ETH_STAKED_REQUIREMENT} ETH in your wallet in order to "
                                                         f"earn bounties. >>> ",
                                                  required_if=liquidity_bounty_enabled),
    "email":                            ConfigVar(key="email",
                                                  prompt="Please enter your email >>> ",
                                                  required_if=liquidity_bounty_enabled),
    "final_confirmation":               ConfigVar(key="final_confirmation",
                                                  prompt="Do you confirm all the information you have entered above is "
                                                         "correct? (y/n) >>> ",
                                                  type_str="bool",
                                                  required_if=liquidity_bounty_enabled),
    "liquidity_bounty_client_id":       ConfigVar(key="liquidity_bounty_client_id",
                                                  prompt="What is your liquidity bounty client ID? >>> ",
                                                  required_if=lambda: False),
}

