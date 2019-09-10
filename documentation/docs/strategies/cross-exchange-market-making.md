# Cross Exchange Market Making

## How it Works

Cross exchange market making is described in [Strategies](/strategies/), with a further discussion in the Hummingbot [white paper](https://hummingbot.io/whitepaper.pdf).

### Schematic

The diagrams below illustrate how cross exchange market making works.  The transaction involves two exchanges, a **taker exchange** and a **maker exchange**.  Hummingbot uses the market levels available on the taker exchange to create bid and ask orders (act as a market maker) on the maker exchange (*Figure 1*).

<small><center>***Figure 1: Hummingbot acts as market maker on maker exchange***</center></small>

![Figure 1: Hummingbot acts as market maker on maker exchange](/assets/img/xemm-1.png)

**Buy order**: Hummingbot can sell the asset on the taker exchange for 99 (the best bid available); therefore, it places a buy order on the maker exchange at a lower value of 98.

**Sell order**: Hummingbot can buy the asset on the taker exchange for 101 (the best ask available), and therefore makes a sell order on the maker exchange for a higher price of 102.

<small><center>***Figure 2: Hummingbot fills an order on the maker exchanges and hedges on the taker exchange***</center></small>

![Figure 2: Hummingbot fills an order on the maker exchanges and hedges on the taker exchange](/assets/img/xemm-2.png)

If a buyer (*Buyer D*) fills Hummingbot's sell order on the maker exchange (*Figure 2* ❶), Hummingbot immediately buys the asset on the taker exchange (*Figure 2* ❷).

The end result: Hummingbot has sold the same asset at \$102 (❶) and purchased it for $101 (❷), for a profit of $1.

## Prerequisites: Inventory

1. For cross-exchange market making, you will need to hold inventory on two exchanges, one where the bot will make a market (the **maker exchange**) and another where the bot will source liquidity and hedge any filled orders (the **taker exchange**). See [Inventory Requirements](/operation/running-bots/#inventory-requirements).

2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

Initially, we assume that the maker exchange is an Ethereum-based decentralized exchange and that the taker exchange is Binance.

### Adjusting Orders

Assume the following,

Order amount: 1 ETH
Sell price on Taker: 100 USDT (on a volume weighted average basis)
Min profitablity: 0.05
Top Bid price on Maker: 90 USDT

Adjust Orders Enabled:
The bid price according to min profitability is 95 (100*(1-0.05)). However as top bid price is 90, you will place just above the top at 90.01 USDT

Adjust Orders Disabled:
The bid price according to min profitability is 95 (100*(1-0.05)). Here the strategy will place the bid at 95.

## Configuration Walkthrough

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

| Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>`: | Enter `cross_exchange_market_making`.<br/><br/>Currently available options: `arbitrage` or `cross_exchange_market_making` or `pure_market_making` or `discovery` or `simple_trade` *(case sensitive)* |
| `Import previous configs or create a new config file? (import/create) >>>`: | When running the bot for the first time, enter `create`.<br/>If you have previously initialized, enter `import`, which will then ask you to specify the config file location. |
| `Enter your maker exchange name >>>`: | In the cross-exchange market making strategy, the *maker exchange* is the exchange where the bot will place maker orders.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `ddex`, `idex`, or `bamboo_relay` *(case sensitive)* |
| `Enter your taker exchange name >>>`: | In the cross-exchange market making strategy, the *taker exchange* is the exchange where the bot will place taker orders.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `ddex`, `idex`, or `bamboo_relay` *(case sensitive)*|
| `Enter the token symbol you would like to trade on [maker exchange name] >>>`: | Enter the token symbol for the *maker exchange*.<br/>Example input: `ZRX-WETH`<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: ensure that the pair is a valid pair for the exchange, for example, use `WETH` instead of `ETH`.</td></tr></tbody></table> |
| `Enter the token symbol you would like to trade on [taker exchange name] >>>`: | Enter the token symbol for the *taker exchange*.<br/>Example input: `ZRX-ETH`<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: ensure that (1) the pair corresponds with the token symbol entered for the maker exchange, and that (2) is a valid pair for the exchange.  *Note in the example, the use of `ETH` instead of `WETH`*.</td></tr></tbody></table>|
| `What is the minimum profitability for your to make a trade? (Enter 0.01 to indicate 1%) >>>`: | This sets `min_profitability` (see [definition](/strategies/cross-exchange-market-making/#configuration-parameters)). |
| `Do you want to adjust the prices to be above top bid/ask instead of the expected price, if profitable ? (Default is True) >>>`: | This sets `adjust_order_enabled` (see [definition](/strategies/cross-exchange-market-making/#configuration-parameters)). |
| `Do you want to actively adjust/cancel orders (Default True) >>>`: | This sets `active_order_canceling` (see [definition](/strategies/cross-exchange-market-making/#configuration-parameters)). |
| `What is the minimum profitability to actively cancel orders? (Default to 0.0, only specify when active_order_cancelling is disabled, value can be negative) >>>`: | This sets the `cancel_order_threshold` (see [definition](/strategies/cross-exchange-market-making/#configuration-parameters)). |
| `What is your preferred trade size? (denominated in " "the base asset) >>>`: | This sets the `order_amount` (see [definition](/strategies/cross-exchange-market-making/#configuration-parameters)). |
| `What is the minimum limit order expiration in seconds? (Default to 130 seconds) >>>`: | This sets the `limit_order_min_expiration` (see [definition](/strategies/cross-exchange-market-making/#configuration-parameters)). |
| `What is the amount in base currency, you want to use, for the top depth tolerance ?. Default is 0. >>> `: | This sets `top_depth_tolerance` (see [definition](/strategies/cross-exchange-market-making/#configuration-parameters)). |
| `Enter your Binance API key >>>`:<br/><br/>`Enter your Binance API secret >>>`: | You must [create a Binance API key](https://docs.hummingbot.io/connectors/binance/) key with trading enabled ("Enable Trading" selected).<br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: You can use Ctrl + R or ⌘ + V to paste from the clipboard.</td></tr></tbody></table> |
| `Would you like to import an existing wallet or create a new wallet? (import / create) >>>`: | Import or create an Ethereum wallet which will be used for trading on DDEX.<br/><br/>Enter a valid input:<ol><li>`import`: imports a wallet from an input private key.</li><ul><li>If you select import, you will then be asked to enter your private key as well as a password to lock/unlock that wallet for use with Hummingbot</li><li>`Your wallet private key >>>`</li><li>`A password to protect your wallet key >>>`</li></ul><li>`create`: creates a new wallet with new private key.</li><ul><li>If you select create, you will only be asked for a password to protect your newly created wallet</li><li>`A password to protect your wallet key >>>`</li></ul></ol><br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: using a wallet that is available in your Metamask (i.e. importing a wallet from Metamask) allows you to view orders created and trades filled by Hummingbot on the decentralized exchange's website.</td></tr></tbody></table> |
| `Which Ethereum node would you like your client to connect to? >>>`: | Enter an Ethereum node URL for Hummingbot to use when it trades on Ethereum-based decentralized exchanges.<br /><br />For more information, see: Setting up your Ethereum Node](/installation/node/node).<table><tbody><tr><td bgcolor="#ecf3ff">**Tip**: if you are using an Infura endpoint, ensure that you append `https://` before the URL.</td></tr></tbody></table> |

## Configuration Parameters

The following parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/conf_cross_exchange_market_making_strategy_[#].yml`).

| Term | Definition |
|------|------------|
| **min_profitability** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%).<br/>Minimum required profitability in order for Hummingbot to place an order on the maker exchange. <br/><br/>*Example: assuming a minimum profitability threshold of `0.01` and a token symbol that has a bid price of 100 on the taker exchange (binance), Hummingbot will place a bid order on the maker exchange (ddex) of 99 (or lower) to ensure a 1% (or better) profit; Hummingbot only places this order if that order is the best bid on the maker exchange.*
| **order_amount** | An amount expressed in base currency of maximum allowable order size.  If not set, the default value is 1/6 of the aggregate value of quote and base currency balances across the maker and taker exchanges as determined by the order_size_portfolio_ratio_limit.<br/><br/>*Example: assuming an order amount of `1` and a token symbol of ETH/DAI, the maximum allowable order size is one that has a value of 1 ETH.*
| **adjust_order_enabled** | `True` or `False`<br/>If enabled (parameter set to `True`), the strategy will place the order on top of the top bid and ask if its more profitable to place it there. If this is set to `False`, strategy will ignore the top of the maker order book for price calculations and only place the order based on taker price and min_profitability. Refer to Adjusting orders section above. _Default value: True_
| **active_order_canceling** | `True` or `False`<br/>If enabled (parameter set to `True`), Hummingbot will cancel that become unprofitable based on the `min_profitability` threshold.  If this is set to `False`, Hummingbot will allow any outstanding orders to expire, unless `cancel_order_threshold` is reached.
| **cancel_order_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%), which can be 0 or negative.<br/>When active order canceling is set to `False`, if the profitability of an order falls below this threshold, Hummingbot will cancel an existing order and place a new one, if possible.  This allows the bot to cancel orders when paying gas to cancel (if applicable) is a better than incurring the potential loss of the trade.
| **limit_order_min_expiration** | An amount in seconds, which is the minimum duration for any placed limit orders. _Default value: 130 seconds_.
| **top_depth_tolerance** | An amount expressed in base currency which is used for getting the top bid and ask, ignoring dust orders on top of the order book. <br/><br/>*Example: If you have a top depth tolerance of `0.01 ETH`, then while calculating the top bid, you exclude orders starting from the top until the sum of orders excluded reaches `0.01 ETH`.*  _Default value: 0_.
| **anti_hysteresis_duration** | An amount in seconds, which is the minimum amount of time interval between adjusting limit order prices. _Default value: 60 seconds_.
| **order_size_taker_volume_factor** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%), which is the maximum size limit of new limit orders, in terms of ratio of hedge-able volume on taker side. _Default value: 0.25_.
| **order_size_taker_balance_factor** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%), which is the maximum size limit of new limit orders, in terms of ratio of asset balance available for hedging trade on taker side. _Default value: 0.995_.
| **order_size_portfolio_ratio_limit** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%), which is the maximum size limit of new limit orders, in terms of ratio of total portfolio value on both maker and taker markets. _Default value: 0.1667_.