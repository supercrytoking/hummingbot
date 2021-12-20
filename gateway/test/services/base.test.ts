import { BigNumber } from 'ethers';
import {
  bigNumberWithDecimalToStr,
  stringWithDecimalToBigNumber,
  gasCostInEthString,
  countDecimals,
} from '../../src/services/base';
import 'jest-extended';

test('countDecimals', () => {
  expect(countDecimals(0)).toEqual(0);
  expect(countDecimals(1)).toEqual(0);
  expect(countDecimals(100)).toEqual(0);
  expect(countDecimals(0.0000123)).toEqual(5);
  expect(countDecimals(1.0000123)).toEqual(0);
  expect(countDecimals(100.0000123)).toEqual(0);
  expect(countDecimals(1e9)).toEqual(0);
  expect(countDecimals(1e-9)).toEqual(9);
});

test('bigNumberWithDecimalToStr', () => {
  expect(bigNumberWithDecimalToStr(BigNumber.from(10), 1)).toEqual('1.0');

  expect(bigNumberWithDecimalToStr(BigNumber.from(1), 1)).toEqual('0.1');

  expect(bigNumberWithDecimalToStr(BigNumber.from(12345), 8)).toEqual(
    '0.00012345'
  );

  expect(
    bigNumberWithDecimalToStr(BigNumber.from('8447700000000000000'), 18)
  ).toEqual('8.447700000000000000');

  expect(
    bigNumberWithDecimalToStr(BigNumber.from('1200304050607080001'), 18)
  ).toEqual('1.200304050607080001');

  expect(
    bigNumberWithDecimalToStr(BigNumber.from('1345000000000000000000'), 18)
  ).toEqual('1345.000000000000000000');
});

test('stringWithDecimalToBigNumber', () => {
  expect(stringWithDecimalToBigNumber('1.001', 5)).toEqual(
    BigNumber.from('100100')
  );

  expect(stringWithDecimalToBigNumber('1', 5)).toEqual(
    BigNumber.from('100000')
  );

  expect(stringWithDecimalToBigNumber('1.00000000000', 2)).toEqual(
    BigNumber.from('100')
  );
});

test('gasCostInEthString', () => {
  expect(gasCostInEthString(200, 21000)).toEqual('0.004200000000000000');
});
