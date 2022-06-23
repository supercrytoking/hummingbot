import fs from 'fs';
import fsp from 'fs/promises';
import os from 'os';
import path from 'path';

import { patch, unpatch } from '../../services/patch';
import { providers } from 'ethers';
import { EVMNonceManager } from '../../../src/services/evm.nonce';
import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../../src/services/error-handler';

import 'jest-extended';
import { ReferenceCountingCloseable } from '../../../src/services/refcounting-closeable';

const exampleAddress = '0xFaA12FD102FE8623C9299c72B03E45107F2772B5';

afterEach(() => {
  unpatch();
});

describe('unitiated EVMNodeService', () => {
  let dbPath = '';
  const handle: string = ReferenceCountingCloseable.createHandle();
  let nonceManager: EVMNonceManager;

  beforeAll(async () => {
    jest.useFakeTimers();
    dbPath = await fsp.mkdtemp(
      path.join(os.tmpdir(), '/evm-nonce1.test.level')
    );
    nonceManager = new EVMNonceManager('ethereum', 43, dbPath, 0);
    nonceManager.declareOwnership(handle);
  });

  afterAll(async () => {
    await nonceManager.close(handle);
    fs.rmSync(dbPath, { force: true, recursive: true });
  });

  it('mergeNonceFromEVMNode throws error', async () => {
    await expect(
      nonceManager.mergeNonceFromEVMNode(exampleAddress)
    ).rejects.toThrow(
      new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE(
          'EVMNonceManager.mergeNonceFromEVMNode'
        ),
        SERVICE_UNITIALIZED_ERROR_CODE
      )
    );
  });

  it('getNonce throws error', async () => {
    await expect(nonceManager.getNonce(exampleAddress)).rejects.toThrow(
      new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.getNonceFromMemory'),
        SERVICE_UNITIALIZED_ERROR_CODE
      )
    );
  });

  it('commitNonce (txNonce not null) throws error', async () => {
    await expect(nonceManager.commitNonce(exampleAddress, 87)).rejects.toThrow(
      new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('EVMNonceManager.commitNonce'),
        SERVICE_UNITIALIZED_ERROR_CODE
      )
    );
  });

  it('delay value too low', async () => {
    const provider = new providers.StaticJsonRpcProvider(
      'https://ethereum.node.com'
    );

    const nonceManager2 = new EVMNonceManager('ethereum', 43, dbPath, -5);
    nonceManager2.declareOwnership(handle);

    try {
      await expect(nonceManager2.init(provider)).rejects.toThrow(
        new InitializationError(
          SERVICE_UNITIALIZED_ERROR_MESSAGE(
            'EVMNonceManager.init delay must be greater than or equal to zero.'
          ),
          SERVICE_UNITIALIZED_ERROR_CODE
        )
      );
    } finally {
      await nonceManager2.close(handle);
    }
  });
});

describe('EVMNodeService', () => {
  let nonceManager: EVMNonceManager;
  let dbPath = '';
  const handle: string = ReferenceCountingCloseable.createHandle();

  beforeAll(async () => {
    dbPath = await fsp.mkdtemp(
      path.join(os.tmpdir(), '/evm-nonce2.test.level')
    );
    nonceManager = new EVMNonceManager('ethereum', 43, dbPath, 60);
    nonceManager.declareOwnership(handle);
    const provider = new providers.StaticJsonRpcProvider(
      'https://ethereum.node.com'
    );
    await nonceManager.init(provider);
  });

  afterAll(async () => {
    await nonceManager.close(handle);
    fs.rmSync(dbPath, { force: true, recursive: true });
  });
  const patchGetTransactionCount = () => {
    if (nonceManager._provider) {
      patch(nonceManager._provider, 'getTransactionCount', () => 11);
    }
  };

  it('commitNonce with a provided txNonce should not increase the nonce by 1', async () => {
    patchGetTransactionCount();
    await nonceManager.commitNonce(exampleAddress, 10);
    const nonce = await nonceManager.getNonce(exampleAddress);

    await expect(nonce).toEqual(10);
  });

  it('mergeNonceFromEVMNode should update with nonce from node (local<node)', async () => {
    patchGetTransactionCount();

    await nonceManager.commitNonce(exampleAddress, 8);
    jest.advanceTimersByTime(300000);
    await nonceManager.mergeNonceFromEVMNode(exampleAddress);
    const nonce = await nonceManager.getNonce(exampleAddress);
    await expect(nonce).toEqual(11);
  });

  it('mergeNonceFromEVMNode should update with the nonce from node (local>node)', async () => {
    patchGetTransactionCount();

    await nonceManager.commitNonce(exampleAddress, 20);
    jest.advanceTimersByTime(300000);
    await nonceManager.mergeNonceFromEVMNode(exampleAddress);
    const nonce = await nonceManager.getNonce(exampleAddress);
    await expect(nonce).toEqual(11);
  });
});

describe("EVMNodeService was previously a singleton. Let's prove that it no longer is.", () => {
  let nonceManager1: EVMNonceManager;
  let nonceManager2: EVMNonceManager;
  let dbPath = '';
  const handle: string = ReferenceCountingCloseable.createHandle();

  beforeAll(async () => {
    dbPath = await fsp.mkdtemp(
      path.join(os.tmpdir(), '/evm-nonce3.test.level')
    );
    nonceManager1 = new EVMNonceManager('ethereum', 43, dbPath, 60);
    const provider1 = new providers.StaticJsonRpcProvider(
      'https://ethereum.node.com'
    );
    nonceManager1.declareOwnership(handle);
    await nonceManager1.init(provider1);

    nonceManager2 = new EVMNonceManager('avalanche', 56, dbPath, 60);
    nonceManager2.declareOwnership(handle);
    const provider2 = new providers.StaticJsonRpcProvider(
      'https://avalanche.node.com'
    );
    await nonceManager2.init(provider2);
  });

  afterAll(async () => {
    await nonceManager1.close(handle);
    await nonceManager2.close(handle);
    fs.rmSync(dbPath, { force: true, recursive: true });
  });
  it('commitNonce with a provided txNonce should increase to external nonce', async () => {
    if (nonceManager1._provider) {
      patch(nonceManager1._provider, 'getTransactionCount', () => 11);
    }
    if (nonceManager2._provider) {
      patch(nonceManager2._provider, 'getTransactionCount', () => 24);
    }

    await nonceManager1.commitNonce(exampleAddress, 10);
    jest.advanceTimersByTime(300000);
    const nonce1 = await nonceManager1.getNonce(exampleAddress);
    await expect(nonce1).toEqual(11);

    await nonceManager2.commitNonce(exampleAddress, 23);
    jest.advanceTimersByTime(300000);
    const nonce2 = await nonceManager2.getNonce(exampleAddress);
    await expect(nonce2).toEqual(24);

    await nonceManager1.commitNonce(exampleAddress, 11);
    jest.advanceTimersByTime(300000);
    const nonce3 = await nonceManager1.getNonce(exampleAddress);
    await expect(nonce3).toEqual(11);
  });
});
