import {
  isNaturalNumberString,
  isFloatString,
  mkValidator,
  mkRequestValidator,
  RequestValidator,
  Validator,
} from '../../../services/validators';

import { validateNonce, validatePrivateKey } from '../ethereum.validators';

export const invalidQuoteError: string = 'The quote param is not a string.';

export const invalidBaseError: string = 'The base param is not a string.';

export const invalidAmountError: string =
  'The amount param must be a string of a non-negative integer.';

export const invalidSideError: string =
  'The side param must be a string of "buy" or "sell".';

export const invalidLimitPriceError: string =
  'The limitPrice param may be null or a string of a float or integer number.';

export const validateQuote: Validator = mkValidator(
  'quote',
  invalidQuoteError,
  (val) => typeof val === 'string'
);

export const validateBase: Validator = mkValidator(
  'base',
  invalidBaseError,
  (val) => typeof val === 'string'
);

export const validateAmount: Validator = mkValidator(
  'amount',
  invalidAmountError,
  (val) => typeof val === 'string' && isNaturalNumberString(val)
);

export const validateSide: Validator = mkValidator(
  'side',
  invalidSideError,
  (val) => typeof val === 'string' && (val === 'BUY' || val === 'SELL')
);

export const validateLimitPrice: Validator = mkValidator(
  'limitPrice',
  invalidLimitPriceError,
  (val) => typeof val === 'string' && isFloatString(val),
  true
);

export const validateUniswapPriceRequest: RequestValidator = mkRequestValidator(
  [validateQuote, validateBase, validateAmount, validateSide]
);

export const validateUniswapTradeRequest: RequestValidator = mkRequestValidator(
  [
    validateQuote,
    validateBase,
    validateAmount,
    validatePrivateKey,
    validateSide,
    validateLimitPrice,
    validateNonce,
  ]
);
