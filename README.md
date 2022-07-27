![Hummingbot](https://i.ibb.co/X5zNkKw/blacklogo-with-text.png)

----
[![License](https://img.shields.io/badge/License-Apache%202.0-informational.svg)](https://github.com/hummingbot/hummingbot/blob/master/LICENSE)
[![Twitter](https://img.shields.io/twitter/follow/hummingbot_io.svg?style=social&label=hummingbot)](https://twitter.com/hummingbot_io)
[![Discord](https://img.shields.io/discord/530578568154054663?logo=discord&logoColor=white&style=flat-square)](https://discord.gg/hummingbot/)
[![Discourse](https://img.shields.io/discourse/https/hummingbot.discourse.group/topics.svg?style=flat-square)](https://hummingbot.discourse.group)

Hummingbot is an open source client-side framework that helps you build, manage, and run automated trading strategies, or **bots**. This code is free and publicly available under the Apache 2.0 open source license!

### [Docs](https://hummingbot.org/docs/) · [Install](https://hummingbot.org/installation/) · [FAQ](https://hummingbot.org/faq/) ·  [Developers](https://hummingbot.org/developers/) · [CEX Connectors](#centralized-exchange-connectors) · [DEX Connectors](#decentralized-exchange-connectors)

## Why Hummingbot?

* **CEX and DEX connectors**: Hummingbot supports connectors to 30+ centralized exchanges and 7+ decentralized exchanges
* **Advanced market making strategies**: Hummingbot ships with 10+ customizable strategy templates like [Cross-Exchange Market Making](https://hummingbot.org/strategies/cross-exchange-market-making/), [Avellaneda Market Making](https://hummingbot.org/strategies/avellaneda-market-making/) (based on the classic [Avellaneda & Stoikov paper](https://people.orie.cornell.edu/sfs33/LimitOrderBook.pdf)), and [Spot Perpetual Arbitrage](https://hummingbot.org/strategies/spot-perpetual-arbitrage/)
* **Secure local client**: Hummingbot is a local client software that you install and run on your own devices or cloud virtual machines. It encrypts your API keys and private keys and never exposes them to any third parties.
* **Community-driven**: Inspired by Linux, Hummingbot is managed by a not-for-profit foundation that enables the community to govern how the codebase evolves, using the Hummingbot Governance Token (HBOT).

Help us **democratize high-frequency trading** and make powerful trading algorithms accessible to everyone in the world!

## Centralized Exchange Connectors

| logo | name | docs / market type    | signup |
|:----:|------|-----------------------|:------:|
| <img src="assets/altmarkets_logo1.png" alt="AltMarkets.io" width="90" /> | [AltMarkets.io](https://altmarkets.io/) | [spot](https://hummingbot.org/exchanges/altmarkets/) |
| <img src="assets/ascendex-logo.jpg" alt="AscendEx" width="90" /> | [AscendEx](https://ascendex.com/register?inviteCode=UEIXNXKW) | [spot](https://hummingbot.org/exchanges/ascend-ex/) | [![Sign up with AscendEX using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d10%25&color=orange)](https://ascendex.com/register?inviteCode=UEIXNXKW)
| <img src="assets/beaxy-logo.png" alt="Beaxy" width="90" /> | [Beaxy](https://beaxy.com/) | [spot](https://hummingbot.org/exchanges/beaxy/) | 
| <img src="assets/binance-logo.jpg" alt="Binance" width="90" /> | [Binance](https://www.binance.com/en/register?ref=FQQNNGCD) | [spot](https://hummingbot.org/exchanges/binance/) | [![Sign up with Binance using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d10%25&color=orange)](https://www.binance.com/en/register?ref=FQQNNGCD)
| <img src="assets/binance_futures-logo.jpg" alt="Binance Futures" width="90" /> | [Binance Futures](https://www.binance.com/en/futures/ref?code=hummingbot) | [perps](https://hummingbot.org/exchanges/binance-perpetual/) | [![Sign up with Binance Futures using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d10%25&color=orange)](https://www.binance.com/en/futures/ref?code=hummingbot)
| <img src="assets/binance_us-logo.jpg" alt="Binance US" width="90" /> | [Binance US](https://www.binance.com/) | [spot](https://hummingbot.org/exchanges/binance-us/)
| <img src="assets/bitfinex-logo.jpg" alt="Bitfinex" width="90" /> | [Bitfinex](https://bitfinex.com/?refcode=dxCUrjvc) | [spot](https://hummingbot.org/exchanges/bitfinex/) | [dxCUrjvc](https://bitfinex.com/?refcode=dxCUrjvc)
| <img src="assets/bitmart-logo.jpg" alt="BitMart" width="90" /> | [BitMart](https://www.bitmart.com/en?r=UM6fQV) | [spot](https://hummingbot.org/exchanges/bitmart/) | [UM6fQV](https://www.bitmart.com/en?r=UM6fQV)
| <img src="assets/bittrex_global-logo.jpg" alt="Bittrex Global" width="90" height="30" />| [Bittrex Global](https://global.bittrex.com/) | [spot](https://hummingbot.org/exchanges/bittrex/)
| <img src="assets/bitmex-logo.png" alt="Bitmex" width="90" /> | [Bitmex](https://www.bitmex.com/) | [spot](https://hummingbot.org/exchanges/bitmex/) / [perps](https://hummingbot.org/exchanges/bitmex-perpetual/)
| <img src="assets/blocktane-logo.jpg" alt="Blocktane" width="90" /> | [Blocktane](https://blocktane.io/) | [spot](https://hummingbot.org/exchanges/blocktane/)
| <img src="assets/bybit-logo.jpg" alt="Bybit" width="90" /> | [Bybit](https://www.bybit.com/) | [spot](https://hummingbot.org/exchanges/bybit/) / [perps](https://hummingbot.org/exchanges/bybit-perpetual/)
| <img src="assets/coinbase_pro-logo.jpg" alt="Coinbase Pro" width="90" /> | [Coinbase Pro](https://pro.coinbase.com/) | [spot](https://hummingbot.org/exchanges/coinbase/)
| <img src="assets/coinflex_logo.png" alt="CoinFLEX" width="90" /> | [CoinFLEX](https://coinflex.com/) | [spot](https://hummingbot.org/exchanges/coinflex/) / [perps](https://hummingbot.org/exchanges/coinflex-perpetual/)
| <img src="assets/coinzoom-logo.jpg" alt="CoinZoom" width="90" /> | [CoinZoom](https://trade.coinzoom.com) | [spot](https://hummingbot.org/exchanges/coinzoom/)
| <img src="assets/cryptocom-logo.jpg" alt="Crypto.com" width="90" /> | [Crypto.com](https://crypto.com/exchange) | [spot](https://hummingbot.org/exchanges/crypto-com/)
| <img src="assets/digifinex-logo.jpg" alt="Digifinex" width="90" /> | [Digifinex](https://www.digifinex.com/en-ww) | [spot](https://hummingbot.org/exchanges/digifinex/)
| <img src="assets/ftx-logo.jpg" alt="FTX" width="90" /> | [FTX](https://ftx.com/en) | [spot](https://hummingbot.org/exchanges/ftx/)
| <img src="assets/gate-io-logo.jpg" alt="Gate.io" width="90" /> | [Gate.io](https://www.gate.io/signup/5868285)  | [spot](https://hummingbot.org/exchanges/gate-io/) | [![Sign up with Gate.io using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d10%25&color=orange)](https://www.gate.io/signup/5868285)
| <img src="assets/hitbtc-logo.jpg" alt="HitBTC" width="90" /> | [HitBTC](https://hitbtc.com/) |  [spot](https://hummingbot.org/exchanges/hitbtc/)
| <img src="assets/huobi_global-logo.jpg" alt="Huobi Global" width="90" />| [Huobi Global](https://www.huobi.com/register/?invite_code=en9k2223) | [spot](https://hummingbot.org/exchanges/huobi/) | [en9k2223](https://www.huobi.com/register/?invite_code=en9k2223)
| <img src="assets/kraken-logo.jpg" alt="Kraken" width="90" /> | [Kraken](https://www.kraken.com/) | [spot](https://hummingbot.org/exchanges/kraken/)
| <img src="assets/kucoin-logo.jpg" alt="KuCoin" width="90" /> | [KuCoin](https://www.kucoin.com/ucenter/signup?rcode=272KvRf) | [spot](https://hummingbot.org/exchanges/kucoin/) | [![Sign up with Kucoin using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d10%25&color=orange)](https://www.kucoin.com/ucenter/signup?rcode=272KvRf)
| <img src="assets/latoken-logo.png" alt="Latoken" width="90" /> | [Latoken](https://latoken.com/) | [spot](https://hummingbot.org/exchanges/latoken/)
| <img src="assets/liquid-logo.jpg" alt="Liquid" width="90" /> | [Liquid](https://www.liquid.com/) | [spot](https://hummingbot.org/exchanges/liquid/) 
| <img src="assets/mexc.jpg" alt="MEXC" width="90" /> | [MEXC Global](https://www.mexc.com/) | [spot](https://hummingbot.org/exchanges/mexc/)
| <img src="assets/ndax-logo.jpg" alt="NDAX" width="90" /> | [NDAX](https://ndax.io/) | [spot](https://hummingbot.org/exchanges/ndax/)
| <img src="assets/okex-logo.jpg" alt="OKEx" width="90" /> | [OKX](https://www.okx.com/join/1931920) | [spot](https://hummingbot.org/exchanges/okx/) | [![Sign up with OKX using Hummingbot's referral link for a 10% discount!](https://img.shields.io/static/v1?label=Fee&message=%2d10%25&color=orange)](https://www.okx.com/join/1931920)
| <img src="assets/probit-logo.jpg" alt="Probit Global" width="90" /> | [Probit Global](https://www.probit.com/) | [spot](https://hummingbot.org/exchanges/probit/)
| <img src="assets/probit_kr-logo.jpg" alt="Probit Korea" width="90" /> | [Probit Korea](https://www.probit.kr/en-us/) | [spot](https://hummingbot.org/exchanges/probit-korea/) |
| <img src="assets/wazirX-logo.jpg" alt="Wazirx" width="90" /> | [WazirX](https://wazirx.com/) | [spot](https://hummingbot.org/exchanges/wazirx/) |

## Decentralized Exchange Connectors

| logo | name | docs / market type |
|:----:|------|-----------------------|
| <img src="assets/dydx-logo.jpg" alt="dYdX Perpetual" width="90" /> | [dYdX Perpetual](https://dydx.exchange/) | [perp clob](https://hummingbot.org/exchanges/dydx-perpetual/)
| <img src="assets/loopring-logo.jpg" alt="Loopring" width="90" /> | [Loopring](https://loopring.io/) | [spot clob](https://hummingbot.org/exchanges/loopring/)
| <img src="assets/pangolin-logo.jpg" alt="Pangolin" width="90" /> | [Pangolin](https://pangolin.exchange/) | [amm](https://hummingbot.org/gateway/exchanges/pangolin/)
| <img src="assets/quickswap-logo.png" alt="Quickswap" width="90" /> | [Quickswap](https://quickswap.exchange) | [amm](https://hummingbot.org/gateway/exchanges/quickswap/)
| <img src="assets/sushiswap-logo.jpg" alt="Sushiswap" width="90" /> | [Sushiswap](https://sushi.com/) | [amm](https://hummingbot.org/gateway/exchanges/sushiswap/)
| <img src="assets/traderjoe-logo.png" alt="Traderjoe" width="80" /> | [TraderJoe](https://traderjoexyz.com/) | [amm](https://hummingbot.org/gateway/exchanges/traderjoe/)
| <img src="assets/uniswap-logo.jpg" alt="Uniswap" width="90" /> | [Uniswap](https://uniswap.org/) | [concentrated liquidity amm](https://hummingbot.org/gateway/exchanges/uniswap/)

## Getting Started

- [Website](https://hummingbot.org)
- [Docs](https://hummingbot.org/docs)
- [FAQs](https://hummingbot.org/faq/)
- [Installation](https://hummingbot.org/installation/)
- [Developers](https://hummingbot.org/developers/)

### Community

- [Discord](https://discord.gg/hummingbot)
- [Youtube](https://www.youtube.com/c/hummingbot)
- [Twitter](https://twitter.com/hummingbot_io)
- [Reddit](https://www.reddit.com/r/Hummingbot/)
- [Forum](https://hummingbot.discourse.group/)

## Other Hummingbot Repos

- [Hummingbot Site](https://github.com/hummingbot/hummingbot-site): Official website and documentation for Hummingbot - we welcome contributions here too!
- [Hummingbot Project Management](https://github.com/hummingbot/pm): Agendas and recordings of regular Hummingbot developer and community calls
- [Awesome Hummingbot](https://github.com/hummingbot/awesome-hummingbot): All the Hummingbot links
- [Hummingbot StreamLit Apps](https://github.com/hummingbot/streamlit-apps): Hummingbot-related StreamLit data apps and dashboards

## Contributions

Hummingbot belongs to its community, so we welcome contributions! Please review these [guidelines](./CONTRIBUTING.md) first.

To have your pull request reviewed by the community, submit a [Pull Request Proposal](https://snapshot.org/#/hbot-prp.eth) on our Snapshot. Note that you will need 1 HBOT in your Ethereum wallet to submit a Pull Request Proposal. See https://www.coingecko.com/coins/hummingbot for markets where HBOT trades.

## Legal

- **License**: Hummingbot is licensed under [Apache 2.0](./LICENSE).
- **Data collection**: read important information regarding [Hummingbot Data Collection](./DATA_COLLECTION.md).
