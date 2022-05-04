jest.useFakeTimers();
import { Uniswap } from '../../../../src/connectors/uniswap/uniswap';
import { patch, unpatch } from '../../../services/patch';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import {
  Fetcher,
  Pair,
  Route,
  Token,
  TokenAmount,
  Trade,
  TradeType,
} from '@uniswap/sdk';
import { BigNumber } from 'ethers';
import { Ethereum } from '../../../../src/chains/ethereum/ethereum';

let ethereum: Ethereum;
let uniswap: Uniswap;

const WETH = new Token(
  3,
  '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
  18,
  'WETH'
);
const DAI = new Token(
  3,
  '0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa',
  18,
  'DAI'
);

beforeAll(async () => {
  ethereum = Ethereum.getInstance('kovan');
  patch(ethereum._nonceManager, 'init', () => {
    return;
  });
  patch(ethereum._nonceManager, 'mergeNonceFromEVMNode', () => {
    return;
  });
  patch(ethereum._nonceManager, 'getNonceFromNode', (_ethAddress: string) => {
    return Promise.resolve(12);
  });
  await ethereum.init();
  uniswap = Uniswap.getInstance('ethereum', 'kovan');
  await uniswap.init();
});

beforeEach(() => {
  patch(ethereum._nonceManager, 'init', () => {
    return;
  });
  patch(ethereum._nonceManager, 'mergeNonceFromEVMNode', () => {
    return;
  });
  patch(ethereum._nonceManager, 'getNonceFromNode', (_ethAddress: string) => {
    return Promise.resolve(12);
  });
});

afterEach(() => {
  unpatch();
});

const patchFetchPairData = () => {
  patch(Fetcher, 'fetchPairData', () => {
    return new Pair(
      new TokenAmount(WETH, '2000000000000000000'),
      new TokenAmount(DAI, '1000000000000000000')
    );
  });
};

const patchTrade = (key: string, error?: Error) => {
  patch(Trade, key, () => {
    if (error) return [];
    const WETH_DAI = new Pair(
      new TokenAmount(WETH, '2000000000000000000'),
      new TokenAmount(DAI, '1000000000000000000')
    );
    const DAI_TO_WETH = new Route([WETH_DAI], DAI);
    return [
      new Trade(
        DAI_TO_WETH,
        new TokenAmount(DAI, '1000000000000000'),
        TradeType.EXACT_INPUT
      ),
    ];
  });
};

describe('verify Uniswap estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn');

    const expectedTrade = await uniswap.estimateSellTrade(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn', new Error('error getting trade'));

    await expect(async () => {
      await uniswap.estimateSellTrade(WETH, DAI, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify Uniswap estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut');

    const expectedTrade = await uniswap.estimateBuyTrade(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut', new Error('error getting trade'));

    await expect(async () => {
      await uniswap.estimateBuyTrade(WETH, DAI, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});
