# Setting up your Ethereum node

## Do I need an Ethereum node?

You need an Ethereum node for strategies that trade on Ethereum-based decentralized exchanges, such as 0x open order book relayers such as Radar Relay, as well as DDEX.

## Option 1. Run your own local node

The best and most reliable way, not to mention in the spirit of decentralization, is to run your own Ethereum node!

Running your own node may require dedicated storage and compute, as well as some technical skills. These are the two most widely used Ethereum clients:
- [go-ethereum (geth)](https://github.com/ethereum/go-ethereum/wiki/Building-Ethereum)
- [parity](https://github.com/paritytech/parity-ethereum)

!!! note
    These may require several hours to days to sync and may require some troubleshooting when first running.

## Option 2. Third-party providers
1. [Alchemy Insights](https://alchemyinsights.io/) provides professional grade Ethereum nodes. We have partnered with Alchemy to provide a free trial for Hummingbot users - please contact us for more information.
2. [Quiknode](https://quiknode.io)
3. [Infura](https://infura.io/) provides free and the most widely used Ethereum nodes.

!!! warning
    Third party providers may have limited functionality; the Hummingbot team continues to evaluate and test node providers.

## Option 3. Dedicated blockchain hardware
Get dedicated hardware for your Ethereum node.  Ethereum nodes are meant to run constantly 24/7 and use up a material amount of computational resources (CPU, RAM, and storage).  For more serious users, it may make sense to use dedicated hardware.

### Software
- [DAppNode](https://dappnode.io/) is software that automates the installation and operation of Ethereum (as well as other blockchains) on dedicated hardware.it easier to start and operate an Ethereum node and can run other blockchains.

### Hardware
- [IntelⓇ NUC mini PC](https://www.intel.com/content/www/us/en/products/boards-kits/nuc.html): DIY, customize and configure your own hardware.
- [Avado](https://ava.do/): purpose built hardware that is pre-loaded with DAppNode.
