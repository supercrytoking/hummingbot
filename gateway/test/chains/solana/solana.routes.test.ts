import request from 'supertest';
import { patch, unpatch } from '../../services/patch';
import { gatewayApp } from '../../../src/app';
import { Solana } from '../../../src/chains/solana/solana';
import { publicKey, privateKey } from './solana.validators.test';
import { tokenSymbols, txHash } from '../../services/validators.test';
import { TransactionResponseStatusCode } from '../../../src/chains/solana/solana.requests';
import * as getTransactionData from './fixtures/getTransaction.json';
import getTokenAccountData from './fixtures/getTokenAccount';
import getOrCreateAssociatedTokenAccountData from './fixtures/getOrCreateAssociatedTokenAccount';
import * as getTokenListData from './fixtures/getTokenList.json';
import { Keypair } from '@solana/web3.js';
import bs58 from 'bs58';
import { BigNumber } from 'ethers';

let solana: Solana;
beforeAll(async () => {
  solana = Solana.getInstance();
  solana.getTokenList = jest
    .fn()
    .mockReturnValue([
      getTokenListData[0],
      getTokenListData[1],
      getTokenListData[2],
      getTokenListData[3],
    ]);
  await solana.init();
});

afterEach(() => unpatch());

const patchGetKeypair = () => {
  patch(solana, 'getKeypair', (pubkey: string) => {
    return pubkey === publicKey
      ? Keypair.fromSecretKey(bs58.decode(privateKey))
      : null;
  });
};

describe('GET /solana', () => {
  it('should return 200', async () => {
    request(gatewayApp)
      .get(`/solana`)
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.connection).toBe(true))
      .expect((res) => expect(res.body.rpcUrl).toBe(solana.rpcUrl));
  });
});

const patchGetBalances = () => {
  patch(solana, 'getBalances', () => {
    return {
      SOL: { value: BigNumber.from(228293), decimals: 9 },
      [tokenSymbols[0]]: { value: BigNumber.from(100001), decimals: 9 },
      [tokenSymbols[1]]: { value: BigNumber.from(200002), decimals: 9 },
      OTH: { value: BigNumber.from(300003), decimals: 9 },
    };
  });
};

describe('POST /solana/balances', () => {
  it('should return 200', async () => {
    patchGetKeypair();
    patchGetBalances();

    await request(gatewayApp)
      .post(`/solana/balances`)
      .send({ address: publicKey, tokenSymbols })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.latency).toBeNumber())
      .expect((res) =>
        expect(res.body.balances).toEqual({
          [tokenSymbols[0]]: '0.000100001',
          [tokenSymbols[1]]: '0.000200002',
        })
      );
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp).post(`/solana/balances`).send({}).expect(404);
  });
});

const patchGetTokenAccount = () => {
  patch(solana, 'getTokenAccount', () => getTokenAccountData);
};

const patchGetSplBalance = () => {
  patch(solana, 'getSplBalance', () => {
    return { value: BigNumber.from(123456), decimals: 9 };
  });
};

describe('GET /solana/token', () => {
  it('should get accountAddress = undefined when Token account not found', async () => {
    patch(solana, 'getTokenAccount', () => {
      return null;
    });
    patchGetSplBalance();

    await request(gatewayApp)
      .get(`/solana/token`)
      .send({ token: tokenSymbols[0], address: publicKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) => expect(res.body.accountAddress).toBeUndefined())
      .expect((res) => expect(res.body.amount).toBe('0.000123456'));
  });

  it('should get amount = undefined when Token account not initialized', async () => {
    patchGetTokenAccount();
    patch(solana, 'getSplBalance', () => {
      throw new Error(`Token account not initialized`);
    });

    await request(gatewayApp)
      .get(`/solana/token`)
      .send({ token: tokenSymbols[0], address: publicKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) =>
        expect(res.body.accountAddress).toBe(
          getTokenAccountData.pubkey.toBase58()
        )
      )
      .expect((res) => expect(res.body.amount).toBeUndefined());
  });

  it('should return 200', async () => {
    patchGetTokenAccount();
    patchGetSplBalance();

    await request(gatewayApp)
      .get(`/solana/token`)
      .send({ token: tokenSymbols[0], address: publicKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) =>
        expect(res.body.accountAddress).toBe(
          getTokenAccountData.pubkey.toBase58()
        )
      )
      .expect((res) => expect(res.body.amount).toBe('0.000123456'));
  });

  it('should return 500 when token not found', async () => {
    await request(gatewayApp)
      .get(`/solana/token`)
      .send({ token: 'not found', address: publicKey })
      .expect(500);
  });
  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp).get(`/solana/token`).send({}).expect(404);
  });
});

const patchGetOrCreateAssociatedTokenAccount = () => {
  patch(
    solana,
    'getOrCreateAssociatedTokenAccount',
    () => getOrCreateAssociatedTokenAccountData
  );
};

describe('POST /solana/token', () => {
  it('should get accountAddress = undefined when Token account not found', async () => {
    patch(solana, 'getOrCreateAssociatedTokenAccount', () => {
      return null;
    });
    patchGetKeypair();
    patchGetSplBalance();

    await request(gatewayApp)
      .post(`/solana/token`)
      .send({ token: tokenSymbols[0], address: publicKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) => expect(res.body.accountAddress).toBeUndefined())
      .expect((res) => expect(res.body.amount).toBe('0.000123456'));
  });

  it('should get amount = undefined when Token account not initialized', async () => {
    patchGetOrCreateAssociatedTokenAccount();
    patchGetKeypair();
    patch(solana, 'getSplBalance', () => {
      throw new Error(`Token account not initialized`);
    });

    await request(gatewayApp)
      .post(`/solana/token`)
      .send({ token: tokenSymbols[0], address: publicKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) =>
        expect(res.body.accountAddress).toBe(
          getTokenAccountData.pubkey.toBase58()
        )
      )
      .expect((res) => expect(res.body.amount).toBeUndefined());
  });

  it('should return 200', async () => {
    patchGetOrCreateAssociatedTokenAccount();
    patchGetKeypair();
    patchGetSplBalance();

    await request(gatewayApp)
      .post(`/solana/token`)
      .send({ token: tokenSymbols[0], address: publicKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) =>
        expect(res.body.accountAddress).toBe(
          getTokenAccountData.pubkey.toBase58()
        )
      )
      .expect((res) => expect(res.body.amount).toBe('0.000123456'));
  });
  it('should return 500 when token not found', async () => {
    await request(gatewayApp)
      .post(`/solana/token`)
      .send({ token: 'not found', address: publicKey })
      .expect(500);
  });
  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp).post(`/solana/token`).send({}).expect(404);
  });
});

const CurrentBlockNumber = 112646487;
const patchGetCurrentBlockNumber = () => {
  patch(solana, 'getCurrentBlockNumber', () => CurrentBlockNumber);
};

const patchGetTransaction = () => {
  patch(solana, 'getTransaction', () => getTransactionData);
};

describe('POST /solana/poll', () => {
  it('should return 200', async () => {
    patchGetCurrentBlockNumber();
    patchGetTransaction();

    await request(gatewayApp)
      .post(`/solana/poll`)
      .send({ txHash })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.currentBlock).toBe(CurrentBlockNumber))
      .expect((res) => expect(res.body.txHash).toBe(txHash))
      .expect((res) =>
        expect(res.body.txStatus).toBe(TransactionResponseStatusCode.CONFIRMED)
      )
      .expect((res) =>
        expect(res.body.txData).toStrictEqual(getTransactionData)
      );
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp).post(`/solana/poll`).send({}).expect(404);
  });
});
