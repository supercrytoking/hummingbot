import {
  isPrivateKey,
  isPublicKey,
  validatePrivateKey,
  invalidPrivateKeyError,
  validateSpender,
  invalidSpenderError,
  validateToken,
  invalidTokenError,
  validateAmount,
  invalidAmountError,
  validateNonce,
  invalidNonceError,
  validateTxHash,
  invalidTxHashError,
  invalidMaxFeePerGasError,
  validateMaxFeePerGas,
  invalidMaxPriorityFeePerGasError,
  validateMaxPriorityFeePerGas,
} from '../../../src/chains/ethereum/ethereum.validators';

import { missingParameter } from '../../../src/services/validators';

import 'jest-extended';

describe('isPublicKey', () => {
  it('pass against a well formed public key', () => {
    expect(isPublicKey('0xFaA12FD102FE8623C9299c72B03E45107F2772B5')).toEqual(
      true
    );
  });

  it('fail against a string that is too short', () => {
    expect(isPublicKey('0xFaA12FD102FE8623C9299c72')).toEqual(false);
  });

  it('fail against a string that has non-hexadecimal characters', () => {
    expect(isPublicKey('0xFaA12FD102FE8623C9299c7iwqpneciqwopienff')).toEqual(
      false
    );
  });

  it('fail against a valid public key that is missing the initial 0x', () => {
    expect(isPublicKey('FaA12FD102FE8623C9299c72B03E45107F2772B5')).toEqual(
      false
    );
  });
});

describe('isPrivateKey', () => {
  it('pass against a well formed public key', () => {
    expect(
      isPrivateKey(
        'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4'
      )
    ).toEqual(true);
  });

  it('fail against a string that is too short', () => {
    expect(isPrivateKey('da857cbda0ba96757fed842617a40693d0')).toEqual(false);
  });

  it('fail against a string that has non-hexadecimal characters', () => {
    expect(
      isPrivateKey(
        'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747qwer'
      )
    ).toEqual(false);
  });
});

describe('validatePrivateKey', () => {
  it('valid when req.privateKey is a privateKey', () => {
    expect(
      validatePrivateKey({
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4',
      })
    ).toEqual([]);
  });

  it('return error when req.privateKey does not exist', () => {
    expect(
      validatePrivateKey({
        hello: 'world',
      })
    ).toEqual([missingParameter('privateKey')]);
  });

  it('return error when req.privateKey is invalid', () => {
    expect(
      validatePrivateKey({
        privateKey: 'world',
      })
    ).toEqual([invalidPrivateKeyError]);
  });
});

describe('validateSpender', () => {
  it('valid when req.spender is a publicKey', () => {
    expect(
      validateSpender({
        spender: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      })
    ).toEqual([]);
  });

  it("valid when req.spender is a 'uniswap'", () => {
    expect(
      validateSpender({
        spender: 'uniswap',
      })
    ).toEqual([]);
  });

  it('return error when req.spender does not exist', () => {
    expect(
      validateSpender({
        hello: 'world',
      })
    ).toEqual([missingParameter('spender')]);
  });

  it('return error when req.spender is invalid', () => {
    expect(
      validateSpender({
        spender: 'world',
      })
    ).toEqual([invalidSpenderError]);
  });
});

describe('validateToken', () => {
  it('valid when req.token is a string', () => {
    expect(
      validateToken({
        token: 'DAI',
      })
    ).toEqual([]);

    expect(
      validateToken({
        token: 'WETH',
      })
    ).toEqual([]);
  });

  it('return error when req.token does not exist', () => {
    expect(
      validateToken({
        hello: 'world',
      })
    ).toEqual([missingParameter('token')]);
  });

  it('return error when req.token is invalid', () => {
    expect(
      validateToken({
        token: 123,
      })
    ).toEqual([invalidTokenError]);
  });
});

describe('validateAmount', () => {
  it('valid when req.amount is a string of an integer', () => {
    expect(
      validateAmount({
        amount: '0',
      })
    ).toEqual([]);
    expect(
      validateAmount({
        amount: '9999999999999999999999',
      })
    ).toEqual([]);
  });

  it('valid when req.amount does not exist', () => {
    expect(
      validateAmount({
        hello: 'world',
      })
    ).toEqual([]);
  });

  it('return error when req.amount is invalid', () => {
    expect(
      validateAmount({
        amount: 'WETH',
      })
    ).toEqual([invalidAmountError]);
  });
});

describe('validateNonce', () => {
  it('valid when req.nonce is a number', () => {
    expect(
      validateNonce({
        nonce: 0,
      })
    ).toEqual([]);
    expect(
      validateNonce({
        nonce: 999,
      })
    ).toEqual([]);
  });

  it('valid when req.nonce does not exist', () => {
    expect(
      validateNonce({
        hello: 'world',
      })
    ).toEqual([]);
  });

  it('return error when req.nonce is invalid', () => {
    expect(
      validateNonce({
        nonce: '123',
      })
    ).toEqual([invalidNonceError]);
  });
});

describe('validateTxHash', () => {
  it('valid when req.txHash is a string', () => {
    expect(
      validateTxHash({
        txHash:
          '0x6d068067a5e5a0f08c6395b31938893d1cdad81f54a54456221ecd8c1941294d',
      })
    ).toEqual([]);
  });

  it('invalid when req.txHash does not exist', () => {
    expect(
      validateTxHash({
        hello: 'world',
      })
    ).toEqual([missingParameter('txHash')]);
  });

  it('return error when req.txHash is invalid', () => {
    expect(
      validateTxHash({
        txHash: 123,
      })
    ).toEqual([invalidTxHashError]);
  });
});

describe('validateMaxFeePerGas', () => {
  it('valid when req.quote is a string', () => {
    expect(
      validateMaxFeePerGas({
        maxFeePerGas: '5000000000',
      })
    ).toEqual([]);

    expect(
      validateMaxFeePerGas({
        maxFeePerGas: '1',
      })
    ).toEqual([]);
  });

  it('return no error when req.maxFeePerGas does not exist', () => {
    expect(
      validateMaxFeePerGas({
        hello: 'world',
      })
    ).toEqual([]);
  });

  it('return error when req.maxFeePerGas is invalid', () => {
    expect(
      validateMaxFeePerGas({
        maxFeePerGas: 123,
      })
    ).toEqual([invalidMaxFeePerGasError]);
  });
});

describe('validateMaxPriorityFeePerGas', () => {
  it('valid when req.quote is a string', () => {
    expect(
      validateMaxPriorityFeePerGas({
        maxPriorityFeePerGasError: '5000000000',
      })
    ).toEqual([]);

    expect(
      validateMaxPriorityFeePerGas({
        maxPriorityFeePerGasError: '1',
      })
    ).toEqual([]);
  });

  it('return no error when req.maxPriorityFeePerGas does not exist', () => {
    expect(
      validateMaxPriorityFeePerGas({
        hello: 'world',
      })
    ).toEqual([]);
  });

  it('return error when req.maxPriorityFeePerGas is invalid', () => {
    expect(
      validateMaxPriorityFeePerGas({
        maxPriorityFeePerGas: 123,
      })
    ).toEqual([invalidMaxPriorityFeePerGasError]);
  });
});
