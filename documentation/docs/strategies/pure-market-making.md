# Pure Market Making

## How it Works

In the pure market making strategy, Hummingbot continually posts limit bid and ask offers on a market and waits for other market participants ("takers") to fill their orders.

Users can specify how far away ("spreads") from the mid price the bid and asks are, the order quantity, and how often prices should be updated (order cancels + new orders posted).

!!! warning
    Please exercise caution while running this strategy and set appropriate [kill switch](/advanced/kill-switch/) rate. The current version of this strategy is intended to be a basic template that users can test and customize. Running the strategy with substantial capital without additional modifications may result in losses.

### Schematic

The diagram below illustrates how market making works. Hummingbot makes a market by placing buy and sell orders on a single exchange, specifying prices and sizes.

<small><center>***Figure 1: Hummingbot makes a market on an exchange***</center></small>

![Figure 1: Hummingbot makes a market on an exchange](/assets/img/pure-mm.png)

## Prerequisites

### Inventory

1. You will need to hold sufficient inventory of quote and/or base currencies on the exchange to place orders of the exchange's minimum order size.
2. You will also need some ETH to pay gas for transactions on a decentralized exchange (if applicable).

### Minimum Order Size

When placing orders, if the size of the order determined by the order price and quantity is below the exchange's minimum order size, then the orders will not be created.

**Example:**

`bid order amount * bid price` < `exchange's minimum order size`<br/>
`ask order amount * ask price` > `exchange's minimum order size`

Only a sell order will be created but no buy order.


## Basic and Advanced Configuration

We aim to teach new users the basics of market making, while enabling experienced users to exercise more control over how their bots behave. By default, when you run `create` we ask you to enter the basic parameters needed for a market making bot.

See [Advanced Market Making](/strategies/advanced-mm) for more information about the advanced parameters and how to use them.


## Basic Configuration Parameters and Walkthrough

The following parameters are fields in Hummingbot configuration files located in the `/conf` folder (e.g. `conf_pure_mm_[#].yml`).

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **exchange** | `Enter your maker exchange name` | The exchange where the bot will place bid and ask orders. |
| **market** | `Enter the token trading pair you would like to trade on [exchange]` | Token trading pair symbol you would like to trade on the exchange. |
| **bid_spread** | `How far away from the mid price do you want to place the first bid order?` | The strategy will place the buy (bid) order on a certain % away from the mid price. |
| **ask_spread** | `How far away from the mid price do you want to place the first ask order?` | The strategy will place the sell (ask) order on a certain % away from the mid price. |
| **minimum_spread**| `At what distance/spread from the mid price do you want the orders to be cancelled?` | The strategy will check every tick and cancel the active orders if an order's spread is less than the minimum spread parameter. |
| **order_refresh_time** | `How often do you want to cancel and replace bids and asks (in seconds)?` | An amount in seconds, which is the duration for the placed limit orders. <br/><br/> The limit bid and ask orders are cancelled and new orders are placed according to the current mid price and spreads at this interval. |
| **order_amount** | `What is the amount of [base_asset] per order? (minimum [min_amount])` | The order amount for the limit bid and ask orders. <br/><br/> Ensure you have enough quote and base tokens to place the bid and ask orders. The strategy will not place any orders if you do not have sufficient balance on either sides of the order. <br/>
| **ping_pong_enabled** | `Would you like to use the ping pong feature and alternate between buy and sell orders after fills?` | Whether to alternate between buys and sells. |

!!! tip "Tip: Autocomplete inputs during configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.