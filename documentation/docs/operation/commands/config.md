
Display the current bot's configuration.

```
>>>  config

Global Configurations:
                     Key   Value
     kill_switch_enabled   False
        kill_switch_rate    -0.1
        telegram_enabled   False
          telegram_token    None
        telegram_chat_id    None
         send_error_logs    True

Strategy Configurations:
                            Key               Value
                       strategy  pure_market_making
                       exchange             binance
                         market             ETH-BTC
                     bid_spread                 1.0
                     ask_spread                 1.0
             order_refresh_time                  30
                   order_amount                 1.0
          order_expiration_time                 130
                   order_levels                   1
             order_level_amount                   0
             order_level_spread                 1.0
         inventory_skew_enabled                True
      inventory_target_base_pct                None
     inventory_range_multiplier                 1.0
             filled_order_delay                  60
         hanging_orders_enabled               False
      hanging_orders_cancel_pct                10.0
     order_optimization_enabled               False
       order_optimization_depth                   0
          add_transaction_costs               False
           price_source_enabled               False
              price_source_type                None
          price_source_exchange                None
            price_source_market                None
            price_source_custom                None
```

## config [ key ]

Reconfigure a parameter value.

```
>>>  config order_refresh_time

How often do you want to cancel and replace bids and asks (in seconds)? >>>
```

## config [ key ] [ value ]

Reconfigure a parameter value without going through the prompts. These can be reconfigured without stopping the bot however, it will only take effect after restarting the strategy.

```
>>>  config order_refresh_time 30

New configuration saved:
order_refresh_time: 30.0
```

## Configure spreads on the fly

The parameters `bid_spread` and `ask_spread` can be reconfigured without stopping the bot. The changes to spread will take effect in the next order refresh.

```
>>>  config bid_spread 0.001
Please follow the prompt to complete configurations:

New configuration saved:
bid_spread: 0.001

The current pure_market_making strategy has been updated to reflect the new configuration.

>>>  config ask_spread 0.001
Please follow the prompt to complete configurations:

New configuration saved:
ask_spread: 0.001

The current pure_market_making strategy has been updated to reflect the new configuration.
```