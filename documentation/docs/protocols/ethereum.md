* [Website](https://ethereum.org/)
* [CoinMarketMap](https://coinmarketcap.com/currencies/ethereum/)
* [Block Explorer](https://etherscan.io/)

## Connect wallet

Run command `connect ethereum` to connect your Ethereum wallet with Hummingbot.

```
Enter your wallet private key >>>
```

There are two ways to connect your Hummingbot wallet from other wallets like Metamask and MyCrypto:

1. Importing the wallet's keyfile
2. Importing the wallet's private key

We recommend using the keyfile method over copying and pasting the private key. If your private key remains in your clipboard, there is a risk that a malicious website that you visit may utilize Javascript to access your clipboard and copy its contents.

### Keyfile

To import your wallet using its JSON keyfile:

1. Export the JSON keyfile from other wallets such as Metamask, MyCrypto, or MyEtherWallet
2. Save the file in the `/conf` directory
3. Rename the file to `key_file_[address].json`, where `[address]` is the public Ethereum address in the format `0xabc...def`.
4. Start Hummingbot
5. Run `connect` command to confirm if keys are confirmed and added for ethereum.

When you import a wallet with Hummingbot, a JSON file named `key_file_[address].json` is created in the `/conf` directory. This JSON keyfile contains the encrypted private key of your wallet and can be imported into other dApps.

#### Private key

1. In the Hummingbot client run command `connect ethereum`
2. Enter the private key associated with the wallet

Within the Hummingbot CLI, you can use the `export_private_key` command to display the private key associated with a wallet address. You can import your wallet to dApps like Metamask and MyCrypto using this private key as well.

### Connect node

Interacting with blockchain protocols requires access to a **node** through which you can send and receive data.

Run command `config ethereum_rpc_url` to use your Ethereum node with Hummingbot:

```
Which Ethereum node would you like your client to connect to? >>>
```

### Node providers

* [Infura](https://infura.io/)
* [Alchemy](https://alchemyapi.io/)