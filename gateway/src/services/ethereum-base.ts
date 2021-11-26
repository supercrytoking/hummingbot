import {
  BigNumber,
  Contract,
  logger,
  providers,
  Transaction,
  utils,
  Wallet,
} from 'ethers';
import axios from 'axios';
import fs from 'fs/promises';
import { TokenListType, TokenValue } from './base';
import { EVMNonceManager } from './evm.nonce';
import NodeCache from 'node-cache';

// information about an Ethereum token
export interface Token {
  chainId: number;
  address: string;
  name: string;
  symbol: string;
  decimals: number;
}

export type NewBlockHandler = (bn: number) => void;

export type NewDebugMsgHandler = (msg: any) => void;

export class EthereumBase {
  private _provider;
  protected tokenList: Token[] = [];
  private _tokenMap: Record<string, Token> = {};
  // there are async values set in the constructor
  private _ready: boolean = false;
  private _initializing: boolean = false;
  private _initPromise: Promise<void> = Promise.resolve();

  public chainName;
  public chainId;
  public rpcUrl;
  public gasPriceConstant;
  public tokenListSource: string;
  public tokenListType: TokenListType;
  public cache: NodeCache;
  private _nonceManager: EVMNonceManager;

  constructor(
    chainName: string,
    chainId: number,
    rpcUrl: string,
    tokenListSource: string,
    tokenListType: TokenListType,
    gasPriceConstant: number
  ) {
    this._provider = new providers.StaticJsonRpcProvider(rpcUrl);
    this.chainName = chainName;
    this.chainId = chainId;
    this.rpcUrl = rpcUrl;
    this.gasPriceConstant = gasPriceConstant;
    this.tokenListSource = tokenListSource;
    this.tokenListType = tokenListType;
    this._nonceManager = new EVMNonceManager(chainName, chainId, 60);
    this._nonceManager.init(this.provider);
    this.cache = new NodeCache({ stdTTL: 3600 }); // set default cache ttl to 1hr
  }

  ready(): boolean {
    return this._ready;
  }

  public get provider() {
    return this._provider;
  }

  public events() {
    this._provider._events.map(function (event) {
      return [event.tag];
    });
  }

  public onNewBlock(func: NewBlockHandler) {
    this._provider.on('block', func);
  }

  public onDebugMessage(func: NewDebugMsgHandler) {
    this._provider.on('debug', func);
  }

  async init(): Promise<void> {
    if (!this.ready() && !this._initializing) {
      this._initializing = true;
      this._initPromise = this.loadTokens(
        this.tokenListSource,
        this.tokenListType
      ).then(() => {
        this._ready = true;
        this._initializing = false;
      });
    }
    return this._initPromise;
  }

  async loadTokens(
    tokenListSource: string,
    tokenListType: TokenListType
  ): Promise<void> {
    this.tokenList = await this.getTokenList(tokenListSource, tokenListType);
    this.tokenList.forEach(
      (token: Token) => (this._tokenMap[token.symbol] = token)
    );
  }

  // returns a Tokens for a given list source and list type
  async getTokenList(
    tokenListSource: string,
    tokenListType: TokenListType
  ): Promise<Token[]> {
    let tokens;
    if (tokenListType === 'URL') {
      ({
        data: { tokens },
      } = await axios.get(tokenListSource));
    } else {
      ({ tokens } = JSON.parse(await fs.readFile(tokenListSource, 'utf8')));
    }
    return tokens;
  }

  public get nonceManager() {
    return this._nonceManager;
  }

  // ethereum token lists are large. instead of reloading each time with
  // getTokenList, we can read the stored tokenList value from when the
  // object was initiated.
  public get storedTokenList(): Token[] {
    return this.tokenList;
  }

  // return the Token object for a symbol
  getTokenForSymbol(symbol: string): Token | null {
    return this._tokenMap[symbol] ? this._tokenMap[symbol] : null;
  }

  // returns Wallet for a private key
  getWallet(privateKey: string): Wallet {
    return new Wallet(privateKey, this._provider);
  }

  // returns the Native balance, convert BigNumber to string
  async getNativeBalance(wallet: Wallet): Promise<TokenValue> {
    const balance = await wallet.getBalance();
    return { value: balance, decimals: 18 };
  }

  // returns the balance for an ERC-20 token
  async getERC20Balance(
    contract: Contract,
    wallet: Wallet,
    decimals: number
  ): Promise<TokenValue> {
    logger.info('Requesting balance for owner ' + wallet.address + '.');
    const balance = await contract.balanceOf(wallet.address);
    logger.info(balance);
    return { value: balance, decimals: decimals };
  }

  // returns the allowance for an ERC-20 token
  async getERC20Allowance(
    contract: Contract,
    wallet: Wallet,
    spender: string,
    decimals: number
  ): Promise<TokenValue> {
    logger.info(
      'Requesting spender ' +
        spender +
        ' allowance for owner ' +
        wallet.address +
        '.'
    );
    const allowance = await contract.allowance(wallet.address, spender);
    logger.info(allowance);
    return { value: allowance, decimals: decimals };
  }

  // returns an ethereum TransactionResponse for a txHash.
  async getTransaction(txHash: string): Promise<providers.TransactionResponse> {
    return this._provider.getTransaction(txHash);
  }

  // caches transaction receipt once they arrive
  cacheTransactionReceipt(tx: providers.TransactionReceipt) {
    this.cache.set(tx.transactionHash, tx); // transaction hash is used as cache key since it is unique enough
  }

  // returns an ethereum TransactionReceipt for a txHash if the transaction has been mined.
  async getTransactionReceipt(
    txHash: string
  ): Promise<providers.TransactionReceipt | null> {
    if (this.cache.keys().includes(txHash)) {
      // If it's in the cache, return the value in cache, whether it's null or not
      return this.cache.get(txHash) as providers.TransactionReceipt;
    } else {
      // If it's not in the cache,
      const fetchedTxReceipt = await this._provider.getTransactionReceipt(
        txHash
      );

      this.cache.set(txHash, fetchedTxReceipt); // Cache the fetched receipt, whether it's null or not

      if (!fetchedTxReceipt) {
        this._provider.once(txHash, this.cacheTransactionReceipt.bind(this));
      }

      return fetchedTxReceipt;
    }
  }

  // adds allowance by spender to transfer the given amount of Token
  async approveERC20(
    contract: Contract,
    wallet: Wallet,
    spender: string,
    amount: BigNumber,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber,
    gasPrice?: number
  ): Promise<Transaction> {
    logger.info(
      'Calling approve method called for spender ' +
        spender +
        ' requesting allowance ' +
        amount.toString() +
        ' from owner ' +
        wallet.address +
        '.'
    );
    if (!nonce) {
      nonce = await this.nonceManager.getNonce(wallet.address);
    }
    const params: any = {
      gasLimit: 100000,
      nonce: nonce,
    };
    if (maxFeePerGas || maxPriorityFeePerGas) {
      params.maxFeePerGas = maxFeePerGas;
      params.maxPriorityFeePerGas = maxPriorityFeePerGas;
    } else if (gasPrice) {
      params.gasPrice = gasPrice * 1e9;
    }
    const response = await contract.approve(spender, amount, params);
    logger.info(response);
    await this.nonceManager.commitNonce(wallet.address, nonce);
    return response;
  }

  public getTokenBySymbol(tokenSymbol: string): Token | undefined {
    return this.tokenList.find(
      (token: Token) => token.symbol.toUpperCase() === tokenSymbol.toUpperCase()
    );
  }

  // returns the current block number
  async getCurrentBlockNumber(): Promise<number> {
    return this._provider.getBlockNumber();
  }

  // cancel transaction
  async cancelTx(
    wallet: Wallet,
    nonce: number,
    gasPrice: number
  ): Promise<Transaction> {
    const tx = {
      from: wallet.address,
      to: wallet.address,
      value: utils.parseEther('0'),
      nonce: nonce,
      gasPrice: gasPrice * 1e9 * 2,
    };
    const response = await wallet.sendTransaction(tx);
    logger.info(response);

    return response;
  }
}
