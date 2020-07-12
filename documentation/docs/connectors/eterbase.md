# Eterbase Connector

## About Eterbase

ETERBASE is the first regulation-compliant European cryptocurrency exchange, offering fast, secure trading on a clean, powerful, user interface.

## Using the Connector

Eterbase is a centralized exchange, you will need to generate and provide your API key in order to trade using Hummingbot.

```
Enter your Eterbase Account >>>
Enter your Eterbase API key >>>
Enter your Eterbase secret key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip "Copying and pasting into Hummingbot"
    See [this page](/faq/troubleshooting/#i-cant-copy-and-paste-my-api-keys) for more instructions in our Support section.

### Creating Eterbase API Keys

1. Log into your account at  [https://eterbase.exchange](https://eterbase.exchange/), then click on your account name in top right corner of the screen and select **Api Keys** from the menu  (If you do not have an account, you will have to create one and verify your ID).

2. Click on  **API Keys**.<br />
[![eterbase1](/assets/img/eterbase1.png)](/assets/img/eterbase1.png)

3. Click on  **New Api Key**.<br />
[![eterbase2](/assets/img/eterbase2.png)](/assets/img/eterbase2.png)

4. Insert Api Key description and give permissions.<br />
Make sure you give permissions to **View** and **Trade**<br />
[![eterbase3](/assets/img/eterbase3.png)](/assets/img/eterbase3.png)

    !!! warning "API key permissions"
        We recommend using only  **"trade"** enabled API keys; enabling  **"withdraw", "transfer", or the equivalent is unnecessary**  for current Hummingbot strategies.

5. Now you have created an API key.<br />
Copy and paste **Account Id**, **Key** and **Secret** to Hummingbot<br />
[![eterbase4](/assets/img/eterbase4.png)](/assets/img/eterbase4.png)

Make sure you store your Secret Key somewhere secure, and do not share it with anyone. Your Secret Key will only be displayed once at the time when you create the API.

!!! tip
    If you lose your Secret Key, you can delete the API and create a new one. However, it will be impossible to reuse the same API.

## Miscellaneous Info

### Minimum Order Sizes

Minimum order size varies per market. All minimum trade quantities can be found in the following public API:

```
https://api.eterbase.exchange/api/markets
```

Rule with attributes values `Qty` and `Min` denotes the minimum order size for each market. For example, trading pair ETH-USDT minimum order size is 0.006 USDT.

```
{
  "id": 33,
  "symbol": "ETHUSDT",
  "base": "ETH",
  "quote": "USDT",
  "priceSigDigs": 5,
  "qtySigDigs": 8,
  "costSigDigs": 8,
  "verificationLevelUser": 0,
  "verificationLevelCorporate": 10,
  "group": "USDT",
  "tradingRules": [
    {
      "attribute": "Qty",
      "condition": "Min",
      "value": 0.006
    },
    {
      "attribute": "Qty",
      "condition": "Max",
      "value": 1000
    },
    {
      "attribute": "Cost",
      "condition": "Min",
      "value": 1
    },
    {
      "attribute": "Cost",
      "condition": "Max",
      "value": 210000
    }
  ],
  "allowedOrderTypes": [
    1,
    2,
    3,
    4
  ],
  "state": "Trading"
}
```

### Transaction Fees

Eterbase charges 0.35% in both maker and taker fees for basic tier. However, users with deposited XBASE tokens can trade at discounted rates. Refer to [Eterbase Trading Fees](https://www.eterbase.com/exchange/fees/) section for more details.

Users can override the default fees by editing [`conf_fee_overrides.yml`](https://docs.hummingbot.io/advanced/fee-overrides/).
