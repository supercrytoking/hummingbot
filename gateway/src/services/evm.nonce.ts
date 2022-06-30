import ethers from 'ethers';
import { logger } from './logger';
import { LocalStorage } from './local-storage';
import {
  InitializationError,
  InvalidNonceError,
  INVALID_NONCE_ERROR_CODE,
  INVALID_NONCE_ERROR_MESSAGE,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from './error-handler';
import { ReferenceCountingCloseable } from './refcounting-closeable';

export class NonceInfo {
  constructor(readonly nonce: number, public expiry: number) {}
}

NonceInfo.prototype.valueOf = function () {
  return this.nonce;
};

export class NonceLocalStorage extends ReferenceCountingCloseable {
  private readonly _localStorage: LocalStorage;

  protected constructor(dbPath: string) {
    super(dbPath);
    this._localStorage = LocalStorage.getInstance(dbPath, this.handle);
  }

  public async init(): Promise<void> {
    await this._localStorage.init();
  }

  public async saveCurrentNonce(
    chain: string,
    chainId: number,
    address: string,
    nonce: NonceInfo
  ): Promise<void> {
    const nonceValue: string = String(nonce.nonce);
    const nonceExpiry: string = String(nonce.expiry);

    return this._localStorage.save(
      chain + '/' + String(chainId) + '/' + address,
      `${nonceValue}:${nonceExpiry}`
    );
  }

  public async getCurrentNonces(
    chain: string,
    chainId: number
  ): Promise<Record<string, NonceInfo>> {
    return this._localStorage.get((key: string, value: any) => {
      const splitKey: string[] = key.split('/');
      if (
        splitKey.length === 3 &&
        splitKey[0] === chain &&
        splitKey[1] === String(chainId)
      ) {
        const nonceValues: string[] = value.split(':');
        const address: string = String(splitKey[2]);
        const nonce: NonceInfo = new NonceInfo(
          parseInt(nonceValues[0]),
          parseInt(nonceValues[1])
        );
        return [address, nonce];
      }
      return;
    });
  }

  public async savePendingNonces(
    chain: string,
    chainId: number,
    address: string,
    nonces: NonceInfo[]
  ): Promise<void> {
    let value = '';

    for (const nonce of nonces) {
      const nonceValue: string = String(nonce.nonce);
      const nonceExpiry: string = String(nonce.expiry);
      value = value + ',' + `${nonceValue}:${nonceExpiry}`;
    }

    return this._localStorage.save(
      `${chain}/${String(chainId)}/${address}/pending`,
      value
    );
  }

  public async getPendingNonces(
    chain: string,
    chainId: number
  ): Promise<Record<string, NonceInfo[]>> {
    return this._localStorage.get((key: string, value: any) => {
      const splitKey: string[] = key.split('/');
      if (
        splitKey.length === 4 &&
        splitKey[0] === chain &&
        splitKey[1] === String(chainId) &&
        splitKey[3] === String('pending')
      ) {
        const address: string = String(splitKey[2]);
        const rawNonceValues: string[] = value.split(',');

        const nonceInfoList = [];
        for (const values of rawNonceValues) {
          const nonceValues: string[] = values.split(':');
          nonceInfoList.push(
            new NonceInfo(parseInt(nonceValues[0]), parseInt(nonceValues[1]))
          );
        }
        nonceInfoList.splice(0, 1);
        return [`${address}`, nonceInfoList];
      }
      return;
    });
  }

  public async close(handle: string): Promise<void> {
    await super.close(handle);
    if (this.refCount < 1) {
      await this._localStorage.close(this.handle);
    }
  }
}

/**
 * Manages EVM nonce for addresses to ensure logical consistency of nonces when
 * there is a burst of transactions being sent out.
 *
 * This class aims to solve the following problems:
 *
 * 1. Sending multiple EVM transactions concurrently.
 *    Naively, developers would use the transaction count from the EVM node as
 *    the nonce for new transactions. When multiple transactions are being sent
 *    out this way - these transactions would often end up using the same nonce
 *    and thus only one of them would succeed.
 *    The EVM nonce manager ensures the correct serialization of nonces used in
 *    this case, s.t. the nonces for new concurrent transactions will go out as
 *    [n, n+1, n+2, ...] rathan than [n, n, n, ...]
 *
 * 2. Stuck or dropped transactions.
 *    If you've sent out a transaction with nonce n before, but it got stuck or
 *    was dropped from the mem-pool - it's better to just forget about its nonce
 *    and send the next transaction with its nonce rather than to wait for it to
 *    be confirmed.
 *    This is where the `localNonceTTL` parameter comes in. The locally cached
 *    nonces are only remembered for a period of time (default is 5 minutes).
 *    After that, nonce values from the EVM node will be used again to prevent
 *    potentially dropped nonces from blocking new transactions.
 *
 * 3. Canceling, or re-sending past transactions.
 *    Canceling or re-sending past transactions would typically re-use past
 *    nonces. This means the user is intending to reset his transaction chain
 *    back to a certain nonce. The manager should allow the cached nonce to go
 *    back to the specified past nonce when it happens.
 *    This means whenever a transaction is sent with a past nonce or an EVM
 *    cancel happens, the API logic **must** call commitNonce() to reset the
 *    cached nonce back to the specified position.
 */
export class EVMNonceManager extends ReferenceCountingCloseable {
  #addressToNonce: Record<string, NonceInfo> = {};
  #addressToPendingNonces: Record<string, NonceInfo[]> = {};

  #initialized: boolean = false;
  #chainId: number;
  #chainName: string;
  #db: NonceLocalStorage;

  // These variables should be private but then we will not be able to mock it otherwise.
  public _provider: ethers.providers.Provider | null = null;
  public _localNonceTTL: number;
  public _pendingNonceTTL: number;

  constructor(
    chainName: string,
    chainId: number,
    dbPath: string,
    localNonceTTL: number = 300 * 1000,
    pendingNonceTTL: number = 300 * 1000
  ) {
    const refCountKey: string = `${chainName}/${chainId}/${dbPath}`;
    super(refCountKey);

    this.#chainName = chainName;
    this.#chainId = chainId;
    this.#db = NonceLocalStorage.getInstance(dbPath, this.handle);
    this._localNonceTTL = localNonceTTL;
    this._pendingNonceTTL = pendingNonceTTL;
  }

  // init can be called many times and generally should always be called
  // getInstance, but it only applies the values the first time it is called
  public async init(provider: ethers.providers.Provider): Promise<void> {
    if (this._localNonceTTL < 0) {
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE(
          'EVMNonceManager.init localNonceTTL must be greater than or equal to zero.'
        ),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }

    if (this._pendingNonceTTL < 0) {
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE(
          'EVMNonceManager.init pendingNonceTTL must be greater than or equal to zero.'
        ),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }

    if (!this._provider) {
      this._provider = provider;
    }

    if (!this.#initialized) {
      await this.#db.init();
      const addressToNonce: Record<string, NonceInfo> =
        await this.#db.getCurrentNonces(this.#chainName, this.#chainId);

      const addressToPendingNonces: Record<string, NonceInfo[]> =
        await this.#db.getPendingNonces(this.#chainName, this.#chainId);

      for (const [address, nonce] of Object.entries(addressToNonce)) {
        this.#addressToNonce[address] = nonce;
      }

      for (const [address, nonceInfoList] of Object.entries(
        addressToPendingNonces
      )) {
        this.#addressToPendingNonces[address] = nonceInfoList;
      }

      await Promise.all(
        Object.keys(this.#addressToNonce).map(async (address) => {
          await this.mergeNonceFromEVMNode(address, true);
        })
      );
      this.#initialized = true;
    }
  }

  async mergeNonceFromEVMNode(
    ethAddress: string,
    intializationPhase: boolean = false
  ): Promise<void> {
    /*
    Retrieves and saves the nonce from the last successful transaction from the EVM node.
    If time period of the last stored nonce exceeds the localNonceTTL, we update the nonce using the getTransactionCount
    call.
    */
    if (this._provider != null && (intializationPhase || this.#initialized)) {
      const mergeExpiryTimestamp: number = this.#addressToNonce[ethAddress]
        ? this.#addressToNonce[ethAddress].expiry
        : -1;
      const now: number = new Date().getTime();
      if (mergeExpiryTimestamp > now) {
        return;
      }

      const externalNonce: number =
        (await this._provider.getTransactionCount(ethAddress)) - 1;

      this.#addressToNonce[ethAddress] = new NonceInfo(
        externalNonce,
        now + this._localNonceTTL
      );

      await this.#db.saveCurrentNonce(
        this.#chainName,
        this.#chainId,
        ethAddress,
        this.#addressToNonce[ethAddress]
      );

      if (
        this.#addressToPendingNonces[ethAddress] &&
        this.#addressToPendingNonces[ethAddress].length > 0
      ) {
        this.#addressToPendingNonces[ethAddress] = this.#addressToPendingNonces[
          ethAddress
        ].filter((nonceInfo) => nonceInfo.nonce > externalNonce);

        await this.#db.savePendingNonces(
          this.#chainName,
          this.#chainId,
          ethAddress,
          this.#addressToPendingNonces[ethAddress]
        );
      }
    } else {
      logger.error(
        'EVMNonceManager.mergeNonceFromEVMNode called before initiated'
      );
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE(
          'EVMNonceManager.mergeNonceFromEVMNode'
        ),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }

  async getNonceFromMemory(ethAddress: string): Promise<number | null> {
    if (this.#initialized) {
      if (this.#addressToNonce[ethAddress]) {
        await this.mergeNonceFromEVMNode(ethAddress);
        return this.#addressToNonce[ethAddress].nonce;
      } else {
        return null;
      }
    } else {
      logger.error(
        'EVMNonceManager.getNonceFromMemory called before initiated'
      );
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.getNonceFromMemory'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }

  async getNonceFromNode(ethAddress: string): Promise<number> {
    if (this.#initialized && this._provider != null) {
      const externalNonce: number =
        (await this._provider.getTransactionCount(ethAddress)) - 1;

      const now: number = new Date().getTime();
      this.#addressToNonce[ethAddress] = new NonceInfo(
        externalNonce,
        now + this._pendingNonceTTL
      );
      await this.#db.saveCurrentNonce(
        this.#chainName,
        this.#chainId,
        ethAddress,
        this.#addressToNonce[ethAddress]
      );
      return this.#addressToNonce[ethAddress].nonce;
    } else {
      logger.error('EVMNonceManager.getNonceFromNode called before initiated');
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.getNonceFromNode'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }

  async getNonce(ethAddress: string): Promise<number> {
    let nonce: number | null = await this.getNonceFromMemory(ethAddress);
    if (nonce === null) {
      nonce = await this.getNonceFromNode(ethAddress);
    }
    return nonce;
  }

  async getNextNonce(ethAddress: string): Promise<number> {
    /*
    Retrieves the next available nonce for a given wallet address.
    This function will automatically increment the leading Nonce of the given wallet address.
    */

    if (this.#initialized) {
      await this.mergeNonceFromEVMNode(ethAddress);

      let newNonce = null;
      let numberOfPendingNonce = 0;
      const now: number = new Date().getTime();

      if (this.#addressToPendingNonces[ethAddress] instanceof Array)
        numberOfPendingNonce = this.#addressToPendingNonces[ethAddress].length;
      if (numberOfPendingNonce > 0) {
        const pendingNonces: NonceInfo[] =
          this.#addressToPendingNonces[ethAddress];

        for (const nonceInfo of pendingNonces) {
          if (now > nonceInfo.expiry) {
            newNonce = nonceInfo;
            newNonce.expiry = now + this._pendingNonceTTL;
            break;
          }
        }
        if (newNonce === null) {
          // All pending nonce have yet to expire.
          // Use last entry in pendingNonce to determine next nonce.
          newNonce = new NonceInfo(
            pendingNonces[pendingNonces.length - 1].nonce + 1,
            now + this._pendingNonceTTL
          );
          this.#addressToPendingNonces[ethAddress].push(newNonce);
        }
      } else {
        newNonce = new NonceInfo(
          (await this.getNonce(ethAddress)) + 1,
          now + this._pendingNonceTTL
        );
        this.#addressToPendingNonces[ethAddress] = [newNonce];
      }
      await this.#db.savePendingNonces(
        this.#chainName,
        this.#chainId,
        `${ethAddress}`,
        this.#addressToPendingNonces[ethAddress]
      );

      return newNonce.nonce;
    } else {
      logger.error('EVMNonceManager.getNextNonce called before initiated');
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.getNextNonce'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }

  async commitNonce(ethAddress: string, txNonce: number): Promise<void> {
    /*
    Stores the nonce of the last successful transaction.
    */
    if (this.#initialized) {
      const now: number = new Date().getTime();

      if (this.#addressToNonce[ethAddress]) {
        if (txNonce > this.#addressToNonce[ethAddress].nonce) {
          const nonce: NonceInfo = new NonceInfo(
            txNonce,
            now + this._localNonceTTL
          );
          this.#addressToNonce[ethAddress] = nonce;
          await this.#db.saveCurrentNonce(
            this.#chainName,
            this.#chainId,
            ethAddress,
            nonce
          );
          return;
        } else {
          logger.error('Provided txNonce is < currentNonce');
          throw new InvalidNonceError(
            INVALID_NONCE_ERROR_MESSAGE +
              `txNonce(${txNonce}) < currentNonce(${
                this.#addressToNonce[ethAddress].nonce
              })`,
            INVALID_NONCE_ERROR_CODE
          );
        }
      }
      const nonce: NonceInfo = new NonceInfo(
        txNonce,
        now + this._localNonceTTL
      );
      this.#addressToNonce[ethAddress] = nonce;
      await this.#db.saveCurrentNonce(
        this.#chainName,
        this.#chainId,
        ethAddress,
        nonce
      );
    } else {
      logger.error('EVMNonceManager.commitNonce called before initiated');
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.commitNonce'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    }
  }

  async isValidNonce(ethAddress: string, nonce: number): Promise<boolean> {
    const expectedNonce: number = await this.getNextNonce(ethAddress);
    if (nonce == expectedNonce) return true;
    return false;
  }

  async close(ownerHandle: string): Promise<void> {
    await super.close(ownerHandle);
    if (this.refCount < 1) {
      await this.#db.close(this.handle);
    }
  }
}
