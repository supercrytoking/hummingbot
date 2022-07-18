import { Router } from 'express';
import { asyncHandler } from '../services/error-handler';
import { PangolinConfig } from './pangolin/pangolin.config';
import { QuickswapConfig } from './quickswap/quickswap.config';
import { PerpConfig } from './perp/perp.config';
import { SushiswapConfig } from './sushiswap/sushiswap.config';
import { TraderjoeConfig } from './traderjoe/traderjoe.config';
import { UniswapConfig } from './uniswap/uniswap.config';

export namespace ConnectorsRoutes {
  export const router = Router();

  router.get(
    '/',
    asyncHandler(async (_req, res) => {
      res.status(200).json({
        connectors: [
          {
            name: 'uniswap',
            trading_type: UniswapConfig.config.tradingTypes('swap'),
            available_networks: UniswapConfig.config.availableNetworks,
          },
          {
            name: 'uniswapLP',
            trading_type: UniswapConfig.config.tradingTypes('LP'),
            available_networks: UniswapConfig.config.availableNetworks,
            additional_spenders: ['uniswap'],
          },
          {
            name: 'pangolin',
            trading_type: PangolinConfig.config.tradingTypes,
            available_networks: PangolinConfig.config.availableNetworks,
          },
          {
            name: 'quickswap',
            trading_type: QuickswapConfig.config.tradingTypes,
            available_networks: QuickswapConfig.config.availableNetworks,
          },
          {
            name: 'perp',
            trading_type: PerpConfig.config.tradingTypes('perp'),
            available_networks: PerpConfig.config.availableNetworks,
          },
          {
            name: 'sushiswap',
            trading_type: SushiswapConfig.config.tradingTypes,
            available_networks: SushiswapConfig.config.availableNetworks,
          },
          {
            name: 'traderjoe',
            trading_type: TraderjoeConfig.config.tradingTypes,
            available_networks: TraderjoeConfig.config.availableNetworks,
          },
        ],
      });
    })
  );
}
