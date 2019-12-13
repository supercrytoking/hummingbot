# The Hummingbot Client

Hummingbot uses a command-line interface (CLI) that helps users configure and run the bot, as well as generate logs of the trades performed.

## Starting Hummingbot

### Installed from Docker

Creating a new instance of Hummingbot with `docker run` will automatically start the Hummingbot client (see Docker installation guides for [Windows](/installation/via-docker/windows), [Linux](/installation/via-docker/linux) and [MacOS](/installation/via-docker/macOS)).

To run a previously created, stopped container where $NAME is the name of your instance of Hummingbot:

```sh
docker start $NAME && docker attach $NAME
```

For additional information on useful commands, see the [cheatsheet](/cheatsheets/docker) to running Hummingbot on Docker.

### Installed from Source

!!! note
    Make sure that you activate the Anaconda environment with `conda activate hummingbot` prior to running Hummingbot.

Open a Terminal window and go to the root of the directory that contains Hummingbot. From there, run:
```
bin/hummingbot.py
```

### Trading Strategy Autostart

Hummingbot can automatically start the execution of a previously configured trading strategy upon launch without requiring the Hummingbot interface `config` and `start` commands.  Any parameters that are required for `config` can be passed into the Hummingbot launch command. Note, config-password (or wallet-password) is the password used for decrypting encrypted configuration and key files and must be supplied. 

**Launch command from docker**

```bash tab="Docker command"
docker run -it \
-e STRATEGY=${STRATEGY} \
-e CONFIG_FILE_NAME=${CONFIG_FILENAME} \
-e CONFIG_PASSWORD=${CONFIG_PASSWORD} \
-e WALLET=${WALLET} \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

```bash tab="Sample entry"
docker run -it \
-e STRATEGY=discovery \
-e CONFIG_FILE_NAME=conf_discovery_strategy_1.yml \
-e CONFIG_PASSWORD=<INSERT_CONFIG_PASSWORD> \
-e WALLET=<INSERT_WALLET_ADDRESS> \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
coinalpha/hummingbot:latest
```

**Other Docker options:**
```bash
# start Hummingbot after system reboot
docker run -it --restart=always \...
# start Hummingbot on background
docker run -it -d \...
```

**Launch command from source**

```bash tab="Installed from source"
bin/hummingbot_quickstart.py \
--strategy ${STRATEGY} \
--config-file-name ${CONFIG_FILENAME} \
--config-password ${CONFIG-PASSWORD}
--wallet ${WALLET} \
```

```bash tab="Sample entry"
bin/hummingbot_quickstart.py \
--strategy discovery \
--config-file-name conf_discovery_strategy_0.yml \
--config-password <INSERT_CONFIG_PASSWORD>
--wallet <INSERT_WALLET_ADDRESS> \
```


## User Interface

### Client Layout
![Hummingbot CLI](/assets/img/hummingbot-cli.png)

The CLI is divided into three panes:

* **Input pane (lower left)**: where users enter commands
* **Output pane (upper left)**: prints the output of the user's commands
* **Log pane (right)**: log messages


| Command | Function |
|---------|----------|
| `bounty` | Participate in Hummingbot's liquidity bounty program or get bounty status.
| `config` | Configures or, if a bot is already running, re-configures the bot.
| `exit`| Cancels all orders, saves the log, and exits Hummingbot.
| `exit -f`| Force quit without cancelling orders.
| `export_private_key` | Print your Ethereum wallet private key.
| `export_trades` | Export your trades to a csv file.
| `get_balance` | Get the balance of an exchange or wallet, or get the balance of a specific currency in an exchange or wallet.<br/><br/>*Example usage: `get_balance [-c WETH -w|-c ETH -e binance]` to show available WETH balance in the Ethereum wallet and ETH balance in Binance, respectively*.
| `help` | Prints a list of available commands. Adding a command after `help` will display available positional and optional arguments.<br/><br/>*Example: `help bounty` will show how to use the `bounty` command.
| `history`| Print bot's past trades and performance analytics. For an explanation of how Hummingbot calculates profitability, see our blog [here](https://hummingbot.io/blog/2019-07-measure-performance-crypto-trading/#tldr).
| `list` | List wallets, exchanges, configs, and completed trades.<br/><br/>*Example usage: `list [wallets|exchanges|configs|trades]`*
| `paper_trade` | Enable or disable [paper trade mode](/utilities/paper-trade).
| `start` | Starts the bot. If any configuration settings are missing, it will automatically prompt you for them.
| `status` | Get a status report about the current bot status.
| `stop` | Cancels all outstanding orders and stops the bot.


## Bounty-Related Commands

| Command | Description |
|-------- | ----------- |
| `bounty --register` | Register to participate in for liquidity bounties.
| `bounty --list` | See a list of active bounties.
| `bounty --restore-id` | If you lost your configuration file, this is the command to restore it.
| `bounty --status` | See your accumulated rewards.
| `bounty --terms` | See the terms & conditions.

## Keyboard shortcuts
| Keyboard Combo | Command | Description |
|-------- | ----------- | ----------- |
| `Double CTRL + C` | Exit | Press `CTRL + C` twice to exit the bot.
| `CTRL + S` | Status | Show bot status.
| `CTRL + F` | *Search / Hide Search | Toggle search in log pane.
| `CTRL + A` | Select All | Select all text in input pane [used for text edit in Input pane only].
| `CTRL + Z` | Undo | Undo action in input pane [used for text edit in Input pane only].
| `Single CTRL + C` | Copy | Copy text [used for text edit in Input pane only].
| `CTRL + V` | Paste | Paste text [used for text edit in Input pane only].

***Note about search:***

1. Press `CTRL + F` to trigger display the search field

2. Enter your search keyword (not case sensitive)

3. Hit `Enter` to jump to the next matching keyword (incremental search)

4. When you are done. Press `CTRL + F` again to go back to reset.
