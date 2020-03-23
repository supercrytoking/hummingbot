# Hanging Orders

This feature keeps orders "hanging" (or not cancelled and remaining on the order book) if a matching order has been filled on the other side of the order book.

## How It Works

Typically, orders are placed as pairs in single order mode (1 buy and 1 sell order). The parameter `enable_order_filled_stop_cancellation` allows Hummingbot to leave the order on the other side hanging (not cancelled) whenever one side is filled.

The hanging order will be cancelled in the following conditions:

1. The spread goes above the specified `cancel_hanging_order_pct` value
2. Sending `stop` or `exit` command


## Sample Configurations

Let's see how this configuration works in the scenario below:

```json
- filled_order_replenish_wait_time: 60.0
- enable_order_filled_stop_cancellation: true
- cancel_hanging_order_pct: 0.02
```

![](/assets/img/hanging_order1.png)

When the buy order `...1497` was completely filled, it will not cancel the sell order `...1840`. After 60 seconds, Hummingbot will create a new set of buy and sell orders. The `status` output will show all active orders while indicating which orders are hanging.

![](/assets/img/hanging_order2.png)

The hanging order will stay outstanding and will be cancelled if its spread goes above 2% as specified in our `cancel_hanging_order_pct`.

![](/assets/img/hanging_order3.png)


## Relevant Parameters

| Parameter | Prompt | Definition | Default Value |
|-----------|--------|------------|---------------|
| **enable_order_filled_stop_cancellation** | `Do you want to enable hanging orders? (Yes/No) >>>` | When value is set to `true`, the orders on the side opposite to the filled orders remains active. | `false` |
| **cancel_hanging_order_pct** | `At what spread percentage (from mid price) will hanging orders be canceled? (Enter 0.01 to indicate 1%) >>>` | Cancels the hanging orders when their spread goes above this value. | `0.1` |