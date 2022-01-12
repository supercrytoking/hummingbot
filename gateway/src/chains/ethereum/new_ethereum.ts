import abi from '../../services/ethereum.abi.json';
import axios from 'axios';
import { logger } from '../../services/logger';
import { Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from '../../services/ethereum-base';
import { EthereumConfig, getNewEthereumConfig } from './ethereum.config';
import { Provider } from '@ethersproject/abstract-provider';
import { UniswapConfig } from '../../connectors/uniswap/uniswap/uniswap.config';
import { Ethereumish } from '../../services/ethereumish.interface';

// MKR does not match the ERC20 perfectly so we need to use a separate ABI.
const MKR_ADDRESS = '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2';

export class NewEthereum extends EthereumBase implements Ethereumish {
  private static _instances: { [name: string]: NewEthereum };
  private _ethGasStationUrl: string;
  private _gasPrice: number;
  private _gasPriceLastUpdated: Date | null;
  private _nativeTokenSymbol: string;
  private _chain: string;
  private _requestCount: number;
  private _metricsLogInterval: number;

  private constructor(network: string) {
    const config = getNewEthereumConfig('ethereum', network);
    super(
      'ethereum',
      config.network.chainID,
      config.network.nodeURL + EthereumConfig.config.nodeAPIKey,
      config.network.tokenListSource,
      config.network.tokenListType,
      EthereumConfig.config.manualGasPrice
    );
    this._chain = network;
    this._nativeTokenSymbol = EthereumConfig.config.nativeCurrencySymbol;
    this._ethGasStationUrl =
      EthereumConfig.ethGasStationConfig.gasStationURL +
      EthereumConfig.ethGasStationConfig.APIKey;

    this._gasPrice = EthereumConfig.config.manualGasPrice;
    this._gasPriceLastUpdated = null;

    this.updateGasPrice();

    this._requestCount = 0;
    this._metricsLogInterval = 300000; // 5 minutes

    this.onDebugMessage(this.requestCounter.bind(this));
    setInterval(this.metricLogger.bind(this), this.metricsLogInterval);
  }

  public static getInstance(network: string): NewEthereum {
    if (NewEthereum._instances === undefined) {
      NewEthereum._instances = {};
    }
    if (!(network in NewEthereum._instances)) {
      NewEthereum._instances[network] = new NewEthereum(network);
    }

    return NewEthereum._instances[network];
  }

  // public static reload(): Ethereum {
  //   Ethereum._instance = new Ethereum();
  //   return Ethereum._instance;
  // }

  public requestCounter(msg: any): void {
    if (msg.action === 'request') this._requestCount += 1;
  }

  public metricLogger(): void {
    logger.info(
      this.requestCount +
        ' request(s) sent in last ' +
        this.metricsLogInterval / 1000 +
        ' seconds.'
    );
    this._requestCount = 0; // reset
  }

  // getters
  public get gasPrice(): number {
    return this._gasPrice;
  }

  public get chain(): string {
    return this._chain;
  }

  public get nativeTokenSymbol(): string {
    return this._nativeTokenSymbol;
  }

  public get gasPriceLastDated(): Date | null {
    return this._gasPriceLastUpdated;
  }

  public get requestCount(): number {
    return this._requestCount;
  }

  public get metricsLogInterval(): number {
    return this._metricsLogInterval;
  }

  // If ConfigManager.config.ETH_GAS_STATION_ENABLE is true this will
  // continually update the gas price.
  async updateGasPrice(): Promise<void> {
    if (EthereumConfig.ethGasStationConfig.enabled) {
      const { data } = await axios.get(this._ethGasStationUrl);

      // divide by 10 to convert it to Gwei
      this._gasPrice = data[EthereumConfig.ethGasStationConfig.gasLevel] / 10;
      this._gasPriceLastUpdated = new Date();

      setTimeout(
        this.updateGasPrice.bind(this),
        EthereumConfig.ethGasStationConfig.refreshTime * 1000
      );
    }
  }

  getContract(
    tokenAddress: string,
    signerOrProvider?: Wallet | Provider
  ): Contract {
    return tokenAddress === MKR_ADDRESS
      ? new Contract(tokenAddress, abi.MKRAbi, signerOrProvider)
      : new Contract(tokenAddress, abi.ERC20Abi, signerOrProvider);
  }

  getSpender(reqSpender: string): string {
    let spender: string;
    if (reqSpender === 'uniswap') {
      spender = UniswapConfig.config.uniswapV2RouterAddress;
    } else {
      spender = reqSpender;
    }
    return spender;
  }

  // cancel transaction
  async cancelTx(wallet: Wallet, nonce: number): Promise<Transaction> {
    logger.info(
      'Canceling any existing transaction(s) with nonce number ' + nonce + '.'
    );
    return super.cancelTx(wallet, nonce, this._gasPrice);
  }
}
