import {
  invalidEthPrivateKeyError,
  isEthPrivateKey,
  validatePrivateKey,
  invalidChainNameError,
  invalidAddressError,
  validateChainName,
  validateAddress,
  isSolPrivateKey,
  invalidSolPrivateKeyError,
} from '../../../src/services/wallet/wallet.validators';

import { missingParameter } from '../../../src/services/validators';

import 'jest-extended';

describe('isEthPrivateKey', () => {
  it('pass against a well formed private key', () => {
    expect(
      isEthPrivateKey(
        'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4'
      )
    ).toEqual(true);
  });

  it('fail against a string that is too short', () => {
    expect(isEthPrivateKey('da857cbda0ba96757fed842617a40693d0')).toEqual(
      false
    );
  });

  it('fail against a string that has non-hexadecimal characters', () => {
    expect(
      isEthPrivateKey(
        'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747qwer'
      )
    ).toEqual(false);
  });
});

describe('isSolPrivateKey', () => {
  it('pass against a well formed base58 private key', () => {
    expect(
      isSolPrivateKey(
        '5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4uppgaLegmuPpq4ftBpcMw7NNoJHJefiTt'
      )
    ).toEqual(true);
  });

  it('fail against a string that is too short', () => {
    expect(
      isSolPrivateKey('5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4')
    ).toEqual(false);
  });

  it('fail against a string that has non-base58 characters', () => {
    expect(
      isSolPrivateKey(
        '5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4uppgaLegmuPpq4ftBpcMw7NNoJHO0O0O0'
      )
    ).toEqual(false);
  });
});

describe('validatePrivateKey', () => {
  it('valid when req.privateKey is an ethereum key', () => {
    expect(
      validatePrivateKey({
        chainName: 'ethereum',
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4',
      })
    ).toEqual([]);
  });

  it('valid when req.privateKey is a solana key', () => {
    expect(
      validatePrivateKey({
        chainName: 'solana',
        privateKey:
          '5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4uppgaLegmuPpq4ftBpcMw7NNoJHJefiTt',
      })
    ).toEqual([]);
  });

  it('return error when req.privateKey does not exist', () => {
    expect(
      validatePrivateKey({
        chainName: 'ethereum',
        hello: 'world',
      })
    ).toEqual([missingParameter('privateKey')]);
  });

  it('return error when req.chainName does not exist', () => {
    expect(
      validatePrivateKey({
        privateKey:
          '5r1MuqBa3L9gpXHqULS3u2B142c5jA8szrEiL8cprvhjJDe6S2xz9Q4uppgaLegmuPpq4ftBpcMw7NNoJHJefiTt',
      })
    ).toEqual([missingParameter('chainName')]);
  });

  it('return error when req.privateKey is invalid ethereum key', () => {
    expect(
      validatePrivateKey({
        chainName: 'ethereum',
        privateKey: 'world',
      })
    ).toEqual([invalidEthPrivateKeyError]);
  });

  it('return error when req.privateKey is invalid solana key', () => {
    expect(
      validatePrivateKey({
        chainName: 'solana',
        privateKey: 'world',
      })
    ).toEqual([invalidSolPrivateKeyError]);
  });
});

describe('validateChainName', () => {
  it('valid when chainName is ethereum', () => {
    expect(
      validateChainName({
        chainName: 'ethereum',
      })
    ).toEqual([]);
  });

  it('valid when chainName is avalanche', () => {
    expect(
      validateChainName({
        chainName: 'avalanche',
      })
    ).toEqual([]);
  });

  it('valid when chainName is solana', () => {
    expect(
      validateChainName({
        chainName: 'solana',
      })
    ).toEqual([]);
  });

  it('return error when req.chainName does not exist', () => {
    expect(
      validateChainName({
        hello: 'world',
      })
    ).toEqual([missingParameter('chainName')]);
  });

  it('return error when req.chainName is invalid', () => {
    expect(
      validateChainName({
        chainName: 'shibainu',
      })
    ).toEqual([invalidChainNameError]);
  });
});

describe('validateAddress', () => {
  it('valid when address is a string', () => {
    expect(
      validateAddress({
        address: '0x000000000000000000000000000000000000000',
      })
    ).toEqual([]);
  });

  it('return error when req.address does not exist', () => {
    expect(
      validateAddress({
        hello: 'world',
      })
    ).toEqual([missingParameter('address')]);
  });

  it('return error when req.address is not a string', () => {
    expect(
      validateAddress({
        address: 1,
      })
    ).toEqual([invalidAddressError]);
  });
});
