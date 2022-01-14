import express from 'express';
import { Server } from 'http';
import { Request, Response, NextFunction } from 'express';
import { EthereumRoutes } from './chains/ethereum/ethereum.routes';
import { UniswapRoutes } from './chains/ethereum/uniswap/uniswap.routes';
import { AvalancheRoutes } from './chains/avalanche/avalanche.routes';
import { PangolinRoutes } from './chains/avalanche/pangolin/pangolin.routes';
import { WalletRoutes } from './services/wallet/wallet.routes';
import { logger, updateLoggerToStdout } from './services/logger';
import { addHttps } from './https';
import {
  asyncHandler,
  HttpException,
  NodeError,
  gatewayErrorMiddleware,
} from './services/error-handler';
import { ConfigManagerV2 } from './services/config-manager-v2';
import { SwaggerManager } from './services/swagger-manager';
import { EthereumBase } from './services/ethereum-base';

const swaggerUi = require('swagger-ui-express');

export const gatewayApp = express();
let gatewayServer: Server;
let swaggerServer: Server;

// parse body for application/json
gatewayApp.use(express.json());

// parse url for application/x-www-form-urlencoded
gatewayApp.use(express.urlencoded({ extended: true }));

// mount sub routers
gatewayApp.use('/avalanche', AvalancheRoutes.router);
gatewayApp.use('/avalanche/pangolin', PangolinRoutes.router);

gatewayApp.use('/eth', EthereumRoutes.router);
gatewayApp.use('/eth/uniswap', UniswapRoutes.router);

gatewayApp.use('/wallet', WalletRoutes.router);

// a simple route to test that the server is running
gatewayApp.get('/', (_req: Request, res: Response) => {
  res.status(200).json({ status: 'ok' });
});

gatewayApp.get('/status', async (_req: Request, res: Response) => {
  const avalanche = AvalancheRoutes.avalanche;
  const ethereum = EthereumRoutes.ethereum;
  const connectedNetworks = [];
  try {
    const avalancheNetwork = await getConnectionInformation(avalanche);
    connectedNetworks.push(avalancheNetwork);
  } catch (err) {
    logger.error(err);
  }
  try {
    const ethNetwork = await getConnectionInformation(ethereum);
    connectedNetworks.push(ethNetwork);
  } catch (err) {
    logger.error(err);
  }

  res.status(200).json({
    connectedNetworks,
  });
});

async function getConnectionInformation(connector: EthereumBase) {
  return {
    chainName: connector.chainName,
    chainId: connector.chainId,
    rpcUrl: connector.rpcUrl,
    currentBlockNumber: await connector.getCurrentBlockNumber(),
  };
}

gatewayApp.get('/config', (_req: Request, res: Response<any, any>) => {
  res.status(200).json(ConfigManagerV2.getInstance().allConfigurations);
});

interface ConfigUpdateRequest {
  configPath: string;
  configValue: any;
}

gatewayApp.post(
  '/config/update',
  asyncHandler(
    async (
      req: Request<unknown, unknown, ConfigUpdateRequest>,
      res: Response
    ) => {
      console.log('req.body.configPath ' + req.body.configPath);
      console.log('req.body.configValue ' + req.body.configValue);
      const config = ConfigManagerV2.getInstance().get(req.body.configPath);
      if (typeof req.body.configValue == 'string')
        switch (typeof config) {
          case 'number':
            req.body.configValue = Number(req.body.configValue);
            break;
          case 'boolean':
            req.body.configValue =
              req.body.configValue.toLowerCase() === 'true';
            break;
        }
      ConfigManagerV2.getInstance().set(
        req.body.configPath,
        req.body.configValue
      );

      logger.info('Reload logger to stdout.');
      updateLoggerToStdout();

      logger.info('Reloading Ethereum routes.');
      EthereumRoutes.reload();

      logger.info('Restarting gateway.');
      await stopGateway();
      await startGateway();

      res.status(200).json({ message: 'The config has been updated' });
    }
  )
);

// handle any error thrown in the gateway api route
gatewayApp.use(
  (
    err: Error | NodeError | HttpException,
    _req: Request,
    res: Response,
    _next: NextFunction
  ) => {
    const response = gatewayErrorMiddleware(err);
    logger.error(err);
    return res.status(response.httpErrorCode).json(response);
  }
);

export const startSwagger = async () => {
  const swaggerApp = express();
  const swaggerPort = 8080;

  const swaggerDocument = SwaggerManager.generateSwaggerJson(
    './docs/swagger/swagger.yml',
    './docs/swagger/definitions.yml',
    [
      './docs/swagger/main-routes.yml',
      './docs/swagger/eth-routes.yml',
      './docs/swagger/eth-uniswap-routes.yml',
      './docs/swagger/avalanche-routes.yml',
      './docs/swagger/avalanche-pangolin-routes.yml',
      './docs/swagger/wallet-routes.yml',
    ]
  );

  logger.info(
    `⚡️ Swagger listening on port ${swaggerPort}. Read the Gateway API documentation at 127.0.0.1:${swaggerPort}`
  );

  swaggerApp.use('/', swaggerUi.serve, swaggerUi.setup(swaggerDocument));

  swaggerServer = await swaggerApp.listen(swaggerPort);
};

export const startGateway = async () => {
  const port = ConfigManagerV2.getInstance().get('server.port');
  logger.info(`⚡️ Gateway API listening on port ${port}`);
  if (ConfigManagerV2.getInstance().get('server.unsafeDevModeWithHTTP')) {
    logger.info('Running in UNSAFE HTTP! This could expose private keys.');
    gatewayServer = await gatewayApp.listen(port);
  } else {
    try {
      gatewayServer = await addHttps(gatewayApp).listen(port);
    } catch (e) {
      logger.error(
        `Failed to start the server with https. Confirm that the SSL certificate files exist and are correct. Error: ${e}`
      );
      process.exit(1);
    }
    logger.info('The gateway server is secured behind HTTPS.');
  }

  await startSwagger();
};

const stopGateway = async () => {
  await swaggerServer.close();
  return gatewayServer.close();
};
