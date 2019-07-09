# The Hummingbot Client

Hummingbot uses a command-line interface (CLI) that helps users configure and run the bot, as well as generate logs of the trades performed.

## Starting Hummingbot

### Installed from Docker

Creating a new instance of Hummingbot with `docker run` will automatically start the Hummingbot client (see Docker installation guides for [Windows](/installation/docker_windows) and [MacOS](/installation/docker_macOS)).

To run a previously created, stopped container where $NAME is the name of your instance of Hummingbot:

```sh
docker start $NAME && docker attach $NAME
```

For additional information on useful commands, see [our guide](/installation/docker) to running Hummingbot on Docker.

### Installed from Source

!!! note
    Make sure that you activate the Anaconda environment with `conda activate hummingbot` prior to running Hummingbot.

Open a Terminal window and go to the root of the directory that contains Hummingbot. From there, run:
```
bin/hummingbot.py
```

## User Interface

### Client Layout
![Hummingbot CLI](/assets/img/hummingbot-cli.png)

The CLI is divided into three panes:

* **Input pane (lower left)**: where users enter commands
* **Output pane (upper left)**: prints the output of the user's commands
* **Log pane (right)**: log messages

### Client Commands

| Command | Function |
|---------|----------|
| `help` | Prints a list of available commands.
| `start` | Starts the bot. If any configuration settings are missing, it will automatically prompt you for them.
| `config` | Configure the bot.  When running for the first time, initializes the bot.  If the bot has already been initialized, unlocks the Ethereum wallet.
| `status` | Get a status report about price differential between the two exchanges, as well as current orders.
| `list` | List wallets, exchanges, configs, and completed trades.<br/><br/>*Example usage: `list [wallets|exchanges|configs|trades]`*
| `describe` | Get detailed information about wallets, exchanges, and orders.<br/><br/>*Example usage: `describe [-w|-e binance|-e ddex]` to show details of wallets, binance positions, wallet balances (available for DDEX), respectively*.
| `get_balance` | Get the balance of an exchange or wallet, or get the balance of a specific currency in an exchange or wallet.<br/><br/>*Example usage: `get_balance [-c WETH -w|-c ETH -e binance]` to show available WETH balance in the Ethereum wallet and ETH balance in Binance, respectively*.
| `exit` \| `CTRL + C` | Cancels all orders, saves the log, and exits Hummingbot.
|`exit -f`| Force quit without cancelling orders.
| `stop` | Cancels all outstanding orders and stops the bot.
|`export_private_key`| Print your ethereum wallet private key.
|`history`| Print bot's past trades and performance analytics. For an explanation of how Hummingbot calculates profitability, see our blog [here](https://hummingbot.io/blog/2019-07-measure-performance-crypto-trading/#tldr).
|`export_trades`| Export your trades to a csv file.
