# External Pricing Source Configuration

**Updated as of `v0.28.0`**

By default, Hummingbot uses the order book you're trading in to generate the **mid price** (between the top bid and the top ask) as a starting price to calculate maker order prices.

With this feature, you can now use a different order book for the starting mid price, such as an external **exchange** or a **custom API**.

##How It Works

In a situation where the calculation of maker order prices from external sources would result in the order matching any existing orders on the order book, such order will be ignored.

Type `config price_source_enabled` to start the configuration process.

First, set `price_source_type`: choose whether you want to use another exchange (`exchange`) or a custom API (`custom`). Based on your answer, you can set the exchange order book or enter an API endpoint.

!!! note
    Currently, the external price source cannot be the same as the maker exchange (i.e. if the bot is trading on Binance, the `price_source_exchange` cannot be Binance).

### When to use an external price source
External price source is valuable when your bot is market making for a relatively illiquid trading pair, but a more liquid pair with the same underlying exposure is available on a different exchange.

Suppose we are market making for the `ETH-USDT` trading pair. The exchange we are trading on, denoted as **Exchange A**, has the top bid order at $198 and the top ask order at $202, so the mid price is $200.

Let's suppose there is **Exchange B** with an `ETH-USD` trading pair. That pair has a top bid order at $200 while the top ask order is $202, so the mid price is $201. These discrepancies often happens between different exchanges as market conditions change. Some exchanges may react more slowly or quickly to market changes due to differences in the trading pair, liquidity, geography.

If you believe that `ETH-USD` on Exchange B is more liquid and responds more quickly to market information than `ETH-USDT` on Exchange A, you may want to market make on Exchange A but use `ETH-USD` on Exchange B as the price source. This helps you position your orders based on where the market might go in the future. 


## Sample Configurations
```json
- market: XRP-USD
- bid_spread: 1
- ask_spread: 1
- order_amount: 56
```
###No External Pricing Source Configuration
![No External Pricing Source Configuration](/assets/img/price_source_None_config.PNG)

###Exchange External Price Source Configuration
![Exchange External Price Source Configuration](/assets/img/price_source_exchange_config.PNG)

###Custom API Pricing Source Configuration
![Custom API Pricing Source Configuration](/assets/img/price_source_custom_api_config.PNG)

**Custom API Output Required Parameters**

The API GET request should return a decimal number corresponding to a market price for the asset pair you are trading on.


*Sample API Output:*
```json
207.8
```


## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **price_source_enabled** | `Would you like to use an external pricing source for mid-market price? (Yes/No)` | When enabled, allows users to use an external pricing source for the mid price. |
| **price_source_type** | `Which type of external price source to use? (exchange/custom_api)` | The type of external pricing source. |
| **price_source_exchange** | `Enter external price source exchange name` | Name of exchange to be used for external pricing source. |
| **price_source_market** | `Enter the token pair on [price_source_exchange]` | The trading pair for the price source exchange. |
| **price_source_custom** | `Enter pricing API URL` | An external API that returns price. |