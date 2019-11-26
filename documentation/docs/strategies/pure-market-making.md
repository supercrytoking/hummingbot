# Pure Market Making

## How it Works

In the *pure* market making strategy, Hummingbot continually posts limit bid and ask offers on a market and waits for other market participants ("takers") to fill their orders.

Users can specify how far away ("spreads") from the mid price the bid and asks are, the order quantity, and how often prices should be updated (order cancels + new orders posted).

!!! warning
    Please exercise caution while running this strategy and set appropriate kill switch rate. The current version of this strategy is intended to be a basic template that users can test and customize. Running the strategy with substantial capital without additional modifications may result in losses.

### Schematic

The diagram below illustrates how market making works. Hummingbot makes a market by placing buy and sell orders on a single exchange, specifying prices and sizes.

<small><center>***Figure 1: Hummingbot makes a market on an exchange***</center></small>

![Figure 1: Hummingbot makes a market on an exchange](/assets/img/pure-mm.png)

## Prerequisites: Inventory

1. You will need to hold sufficient inventory of quote and/or base currencies on the exchange to place orders of the exchange's minimum order size.
2. You will also need some Ethereum to pay gas for transactions on a DEX (if applicable).

### Placing Orders: Minimum Order Size

When placing orders, if the size of the order determined by the order price and quantity is below the exchange's minimum order size, then the orders will not be created.

> For example, if the `bid order amount * bid price` **<** `exchange's minimum order size` while `ask order amount * ask price` **>** `exchange's minimum order size`, a sell order would be created but no bid order would be created.

When using the [multiple order mode](#multiple-order-configuration), this may result in some (or none) of the orders being placed on one side.

> For example, if the `bid order amount 1 * bid price 1` **<** `exchange's minimum order size` while `bid order amount 2 * bid price 2` **>** `exchange's minimum order size`, then only the 2nd bid order would be created.

## Configuration Walkthrough

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Autocomplete inputs during configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

| Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>` | Enter `pure_market_making`. |
| `Import previous configs or create a new config file? (import/create) >>>` | When running the bot for the first time, enter `create`. If you have previously initialized, enter `import`, which will then ask you to specify the config file name. |
| `Enter your maker exchange name >>>` | The exchange where the bot will place bid and ask orders.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `ddex`, `idex`, `bamboo_relay`, `huobi`, `bittrex`, `dolomite` *(case sensitive)* |
| `Enter the token symbol you would like to trade on [maker exchange name] >>>` | Enter the token symbol for the *maker exchange*.<br/>Example input: `ETH-USD`<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Options available are based on each exchange's methodology for labeling currency pairs. Ensure that the pair is a valid pair for the selected exchange.</td></tr></tbody></table> |
| `Enter quantity of bid/ask orders per side (single/multiple) >>> ` | `single` or `multiple`<br /><br />Specify if you would like a single order per side (i.e. one bid and one ask), or multiple orders each side.<br /><br />Multiple allows for different prices and sizes for each side. See [additional configuration for multiple orders](#multiple-order-configuration). |
| `How far away from the mid price do you want to place the first bid? (Enter 0.01 to indicate 1%) >>>` | This sets `bid_place_threshold` ([definition](#configuration-parameters)). |
| `How far away from the mid price do you want to place the first ask? (Enter 0.01 to indicate 1%) >>>` | This sets `ask_place_threshold` ([definition](#configuration-parameters)). |
| `How often do you want to cancel and replace bids and asks (in seconds)? (Default is 60 seconds) >>>` | This sets the `cancel_order_wait_time` ([definition](#configuration-parameters)). |
| `What is your preferred quantity per order? (Denominated in the base asset, default is 1) >>> ` | This sets `order_amount` ([definition](#configuration-parameters)). |
| `Would you like to enable inventory skew? (y/n) >>>` <br /><br /> `What is your target base asset inventory percentage? (Enter 0.01 to indicate 1%, default is 0.5 (50%)) >>>` | More information in [Inventory-Based Dynamic Order Sizing](#inventory-based-dynamic-order-sizing) section. |
| `How long do you want to wait before placing the next order if your order gets filled (in seconds)? (Default is 10 seconds) >>>` | More information in [Order Replenish Time](#order-replenish-time) section. |
| `Do you want to enable order_filled_stop_cancellation? If enabled, when orders are completely filled, the other side remains uncanceled. (Default is False) >>> ` | More information in ["Hanging Orders"](#hanging-orders) section. |
| `Do you want to enable jump_orders? If enabled, when the top bid price is lesser than your order price, buy order will jump to one tick above top bid price & vice versa for sell. (Default is False) >>>` <br /><br /> `How deep do you want to go into the order book for calculating the top bid and ask, ignoring dust orders on the top (expressed in base currency)? (Default is 0) >>>` | More information in [Penny Jumping Mode](#penny-jumping-mode) section. |
| `Do you want to add transaction costs automatically to order prices? (Default is True) >>> ` | More information in [Adding Transaction Costs to Prices](#adding-transaction-costs-to-prices) section. |


## Adding Transaction Costs to Prices

Transaction costs can now be added to the price calculation. `fee_pct` refers to the percentage maker fees per order (generally common in Centralized exchanges) while `fixed_fees` refers to the flat fees (generally common in Decentralized exchanges).

- The bid order price will be calculated as:

![Bid price with transaction cost](/assets/img/trans_cost_bid.PNG)

- The ask order price will be calculated as:

![Ask price with transaction cost](/assets/img/trans_cost_ask.PNG)

Adding the transaction cost will reduce the bid order price and increase the ask order price.

We currently display warnings if the adjusted price post adding the transaction costs is 10% away from the original price. This setting can be modified by changing `warning_report_threshold` in the `c_add_transaction_costs_to_pricing_proposal` function inside `hummingbot/strategy/pure_market_making/pure_market_making_v2.pyx`.

If the buy price with the transaction cost is zero or negative, it is not profitable to place orders and orders will not be placed.

| Prompt | Description |
|-----|-----|
| `Do you want to add transaction costs automatically to order prices? (Default is True) >>> ` | This sets `add_transaction_costs` ([definition](#configuration-parameters)). |

## Multiple Order Configuration

Multiple orders allow you to create multiple orders for each bid and ask side, e.g. multiple bid orders with different prices and different sizes.

 | Prompt | Description |
|-----|-----|
| `How many orders do you want to place on both sides? (Default is 1) >>> ` | This sets `number_of_orders` ([definition](#configuration-parameters)). |
| `What is the size of the first bid and ask order? (Default is 1) >>> ` | This sets `order_start_size` ([definition](#configuration-parameters)). |
| `How much do you want to increase the order size for each additional order? (Default is 0) >>> ` | This sets `order_step_size` ([definition](#configuration-parameters)). |
| `Enter the price increments (as percentage) for subsequent orders? (Enter 0.01 to indicate 1%) >>> ` | This sets `order_interval_percent` ([definition](#configuration-parameters)). <br/><table><tbody><tr><td bgcolor="#e5f8f6">**Warning**: If you set this to a very low number, multiple orders may be placed on the same price level. For example for an asset like SNM/BTC, if you set an order interval percent of 0.004 (~0.4%) because of low asset value the price of the next order will be rounded to the nearest price supported by the exchange, which in this case might lead to multiple orders being placed at the same price level.</td></tr></tbody></table> |

## Inventory-Based Dynamic Order Sizing

This function allows you to specify a target base to quote asset inventory ratio and adjust order sizes whenever the current portfolio ratio deviates from this target.

For example, if you are targeting a 50/50 base to quote asset ratio but the current value of your base asset accounts for more than 50% of the value of your inventory, then bid order amount (buy base asset) is decreased, while ask order amount (sell base asset) is increased.

 | Prompt | Description |
|-----|-----|
| `Would you like to enable inventory skew? (y/n) >>>` | This sets `inventory_skew_enabled` ([definition](#configuration-parameters)). |
| `What is your target base asset inventory percentage? (Enter 0.01 to indicate 1%) >>> ` | This sets `inventory_target_base_percent` ([definition](#configuration-parameters)). |

Here's an [inventory skew calculator](https://docs.google.com/spreadsheets/d/16oCExZyM8Wo8d0aRPmT_j7oXCzea3knQ5mmm0LlPGbU/edit#gid=690135600) that shows how it adjusts order sizes.

### Determining order size

The input `order_amount` is adjusted by the ratio of current base (or quote) percentage versus target percentage:

![Inventory skew calculations](/assets/img/inventory-skew-calculation.png)

## Order Adjustment Based on Filled Events

By default, Hummingbot places orders as soon as there are no active orders; i.e., Hummingbot immediately places a new order to replace a filled order. If there is a sustained movement in the market in any one direction for some time, there is a risk of continued trading in that direction: for example, continuing to buy and accumulate base tokens in the case of a prolonged downward move or continuing to sell in the case of a prolonged upward move.

### Order Replenish Time

The `filled_order_replenish_wait_time` parameter allows for a delay when placing a new order in the event of an order being filled, which will help mitigate the above scenarios.

> Example:
If you have a buy order that is filled at 1:00:00 and the delay is set as 10 seconds. The next orders placed wil be at 1:00:10. The sell order is also cancelled within this delay period and placed at 1:00:10 to ensure that both buy and sell orders stay in sync.

| Prompt | Description |
|-----|-----|
| `How long do you want to wait before placing the next order if your order gets filled (in seconds)? (Default is 10 seconds) >>> ` | This sets `filled_order_replenish_wait_time` ([definition](#configuration-parameters)). |

### "Hanging" Orders

Typically, orders are placed as pairs, e.g. 1 buy order + 1 sell order (or multiple of buy/sell, in multiple mode).  There is now an option using `enable_order_filled_stop_cancellation` to leave the orders on the other side hanging (not cancelled) whenever a one side (buy or sell) is filled.

> Example:
Assume you are running pure market making in single order mode, the order size is 1 and the mid price is 100. Then,
<ul><li> Based on bid and ask thresholds of 0.01, your bid/ask orders would be placed at 99 and 101, respectively.
<li> Your current bid at 99 is fully filled, i.e. someone takes your order and you buy 1.
<li> By default, after the `cancel_order_wait_time`, the ask order at 101 would be canceled
<li> With the `enable_order_filled_stop_cancellation` parameter:
<ul><li>the original 101 ask order stays outstanding
<li> After the `cancel_order_wait_time`, a new pair of bid and ask orders are created, resulting in a total of 1 bid order and 2 ask orders (original and new).  The original ask order stays outstanding until that is filled or manually cancelled.</ul></ul>

The `enable_order_filled_stop_cancellation` can be used if there is enough volatility such that the hanging order might eventually get filled. It should also be used with caution, as the user should monitor the bot regularly to manually cancel orders which don't get filled. It is recommended to disable inventory skew while running this feature.

!!! note "Hanging order feature: currently on `single` trading mode only"
    Since the "hanging orders" feature is experimental, it is currently only available in `single order mode` for testing and receiving further feedback from the community.

 | Prompt | Description |
|-----|-----|
| `How long do you want to wait before placing the next order if your order gets filled (in seconds)? (Default is 10 seconds) >>>` | This sets `filled_order_replenish_wait_time` ([definition](#configuration-parameters)). |
| `Do you want to enable order_filled_stop_cancellation? If enabled, when orders are completely filled, the other side remains uncanceled. (Default is False) >>>` | This sets `enable_order_filled_stop_cancellation` ([definition](#configuration-parameters)). |

## Penny Jumping mode

Users now have the option to automatically adjust the prices to just above top bid and just below top ask using `jump_orders_enabled`. The user can specify how deep to go into the orderbook for calculating the top bid and top ask price using `jump_orders_depth`. This is available in single order mode.

> Example:
Assume you are running pure market making in single order mode, the order size is 1 and the mid price is 100. Then if you set jump_order_depth to 0,
<ul><li> Based on bid and ask thresholds of 0.01, your bid/ask orders might originally have been placed at 99 and 101, respectively.
<li> If the current top bid in the market is 98, now the buy order is automatically adjusted to just above 98, say 98.001 and placed at this price.
<li> If the current top ask in the market is 102, now the sell order is automatically adjusted to just below 102, say 101.999 and placed at this price.

| Prompt | Description |
|-----|-----|
| `Do you want to enable jump_orders? If enabled, when the top bid price is lesser than your order price, buy order will jump to one tick above top bid price & vice versa for sell. (Default is False) >>>` | This sets `jump_orders_enabled` ([definition](#configuration-parameters)). |
| `How deep do you want to go into the order book for calculating the top bid and ask, ignoring dust orders on the top (expressed in base currency)? (Default is 0) >>>` | This sets `jump_orders_depth` ([definition](#configuration-parameters)). |


## Configuration Parameters

The following parameters are fields in Hummingbot configuration files located in the `/conf` folder (e.g. `conf/conf_pure_market_making_strategy_[#].yml`).

| Term | Definition |
|------|------------|
| **order_amount**<br /><small>(single order strategy)</small> | The order amount for the limit bid and ask orders. <br/> Ensure you have enough quote and base tokens to place the bid and ask orders. The strategy will not place orders if you do not have sufficient balance for both sides of the order. <br/>
| **cancel_order_wait_time** | An amount in seconds, which is the duration for the placed limit orders. _Default value: 60 seconds_. <br/><br/> The limit bid and ask orders are cancelled and new bids and asks are placed according to the current mid price and settings at this interval.
| **bid_place_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%). The strategy will place the buy (bid) order 1% away from the mid price if set to 0.01. <br/><br/>*Example: Assuming the following, Top bid : 99, Top ask: 101 ; mid price: 100 ( (99+ 101)/2 ). If you set bid_place_threshold to 0.1 which is 10%, it will place your buy order (bid) at 10% below mid price of 100 which is 90.*
| **ask_place_threshold** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%). The strategy will place the sell (ask) order 1% away from the mid price if set to 0.01. <br/><br/>*Example: Assuming the following, Top bid : 99, Top ask: 101 ; mid price: 100 ( (99+ 101)/2 ). If you set ask_place_threshold to 0.1 which is 10%, it will place your sell order (ask) at 10% above mid price of 100 which is 110.*
| **number_of_orders**<br /><small>(multiple order strategy)</small> | The number of orders to place for each side.<br /> <em>Example: Entering `3` places three bid **and** three ask orders.</em>
| **order_start_size**<br /><small>(multiple order strategy)</small> | The size of the `first` order, which is the order closest to the mid price (i.e. best bid and best ask).
| **order_step_size**<br /><small>(multiple order strategy)</small> | The magnitude of incremental size increases for orders subsequent orders from the first order.<br />*Example: Entering `1` when the first order size is `10` results in bid sizes of `11` and `12` for the second and third orders, respectively, for a `3` order strategy.*
| **order_interval_percent**<br /><small>(multiple order strategy only)</small> | The percentage amount increase in price for subsequent orders from the first order. <br /> <em>Example: For a mid price of 100, `ask_place_threshold` of 0.01, and `order_interval_percent` of 0.005,<br />the first, second, and third ask prices would be **101** (= 100 + 0.01 x 100), **101.5** (= 101 + 0.005 x 100), and **102**.</em>
| **inventory_skew_enabled** | When this is `true`, the bid and ask order sizes are adjusted based on the `inventory_target_base_percent`.
| **inventory_target_base_percent** | An amount expressed in decimals (i.e. input of `0.01` corresponds to 1%). The strategy will place bid and ask orders with adjusted sizes (based on `order_amount`, `order_start_size`) and try to maintain this base asset vs. total (base + quote) asset value.<br/><br/>*Example: You are market making ETH / USD with `order_amount: 1` and balances of 10 ETH and 1000 USD. Your current base asset value is ~67% and quote asset value is ~33%. If `inventory_target_base_percent: 0.5`, the order amount will be adjusted from 1 ETH bid, 1 ETH ask to 0.67 ETH bid, 1.33 ETH ask.*
| **filled_order_replenish_wait_time** | An amount in seconds, which specifies the delay before placing the next order for single order mode. _Default value: 10 seconds_. <br/>
| **enable_order_filled_stop_cancellation** | When this is `true`, the orders on the side opposite to the filled orders remains uncanceled. _Default value: False_. <br/>
| **jump_orders_enabled** | When this is `true`, the bid and ask order prices are adjusted based on the current top bid and ask prices in the market. _Default value: False_. <br/>
| **jump_orders_depth** | If jump_orders_enabled is `true`, this specifies how deep into the orderbook to go for calculating the top bid and ask prices including the user's active orders. _Default value: 0_. <br/>
| **add_transaction_costs** | Parameter to enable/disable adding transaction costs to order prices. _Default value: true_. <br/>


## Risks and Trading Mechanics

!!! warning
    Not financial or investment advice.  Below are descriptions of some risks associated with the pure market making strategy.  There may be additional risks not described below.

### Ideal case

Pure market making strategies works best when you have a market that's relatively calm, but with sufficient trading activity. What that means for a pure market makers is, he would be able to get both of his bid and ask offers traded regularly; the price of his inventory doesn't change by a lot so there's no risk of him ending up on the wrong side of a trend. Thus he would be able to repeatedly capture small profits via the bid/ask spread over time.

![Figure 2: A clam market with regular trading activity](/assets/img/pure-mm-calm.png)

In the figure above, the period between 25 Feb and 12 Mar would be an example of the ideal case. The price of the asset stayed within a relatively small range, and there was sufficient trading activity for a market maker's offers to be taken regularly.

The only thing a market maker needs to worry about in this scenario is he must make sure the trading spread he sets is larger than the trading fees given to the exchange.

### Low trading activity

Markets with low trading activity higher risk for pure market making strategies. Here's an example:

![Figure 3: A market with low trading activity](/assets/img/pure-mm-low-volume.png)

In any market with low trading activity, there's a risk where the market maker may need to hold onto inventory for a long time without a chance to trade it back. During that time, the prices of the traded assets may rise or drop dramatically despite seeing no or little trading activity on the exchange. This exposes the market maker to inventory risk, even after mitigating some of this risk by using wider bid spreads.

Other strategies may be more suitable from a risk perspective in this type of market, e.g. [cross-exchange market making](/strategies/cross-exchange-market-making).

### Volatile or trending markets

Another common risk that market makers need to be aware of is trending markets. Here's one example:

![Figure 4: A trending market](/assets/img/pure-mm-trending.png)

If a pure market maker set his spreads naively in such a market, e.g. equidistant bid/ask spread, there's a risk of the market maker's bid consistently being filled as prices trend down, while at the same time the market continues to move away from the market maker's ask, decreasing the probability of sells.  This would result in an accumulation of inventory at exactly the time where this would reduce inventory inventory value, which is "wrong-way" risk.

However, it is still possible to improve the probability of generating profits in this kind of market by skewing bid asks, i.e. setting a wider bid spread (e.g. -4%) than ask spread (e.g. +0.5%).  In this way, the market maker is trying to catch price spikes in the direction of the trend and buy additional inventory only in the event of a larger moves, but sell more quickly when there is an opportunity so as to minimize the duration the inventory is held.  This approach also has a mean reversion bias, i.e. buy only when there is a larger move downwards, in the hopes of stabilization or recovery after such a large move.

Market making in volatile or trending markets is more advanced and risky for new traders. It's recommended that a trader looking to market make in this kind of environment to get mentally familiar with it (e.g. via paper trading) before committing meaningful capital to the strategy.

### Technology / infrastructure risk

There are many moving parts when operating a market making bot that all have to work together in order to properly function:

- Hummingbot code
- Exchange APIs
- Ethereum blockchain and node
- Network connectivity
- Hummingbot host computer

A fault in any component may result in bot errors, which can range from minor and inconsequential to major.

It is essential for any market making bot to be able to regularly refresh its bid and ask offers on the market in order to adjust to changing market conditions.  If a market making bot is disconnected from the exchange for an extended period of time, then the bid/ask offers it previously made would be left on the market and subject to price fluctuations of the market. Those orders may be filled at a loss as market prices move, while the market maker is offline.  It is very important for any market maker to make sure technical infrastructure is secure and reliable.
