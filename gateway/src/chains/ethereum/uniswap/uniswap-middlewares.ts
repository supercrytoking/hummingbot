import { Uniswap } from './uniswap';
import { NextFunction, Request, Response } from 'express';

export const verifyUniswapIsAvailable = async (
  _req: Request,
  _res: Response,
  next: NextFunction
) => {
  const uniswap = Uniswap.getInstance();
  if (!uniswap.ready()) {
    await uniswap.init();
  }
  return next();
};
