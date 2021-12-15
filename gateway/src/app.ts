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

const swaggerUi = require('swagger-ui-express');

export const app = express();
let server: Server;

// parse body for application/json
app.use(express.json());

// parse url for application/x-www-form-urlencoded
app.use(express.urlencoded({ extended: true }));

// mount sub routers
app.use('/avalanche', AvalancheRoutes.router);
app.use('/avalanche/pangolin', PangolinRoutes.router);

app.use('/eth', EthereumRoutes.router);
app.use('/eth/uniswap', UniswapRoutes.router);

app.use('/wallet', WalletRoutes.router);

// a simple route to test that the server is running
app.get('/', (_req: Request, res: Response) => {
  res.status(200).json({ status: 'ok' });
});

app.get('/config', (_req: Request, res: Response<any, any>) => {
  // res.status(200).json(ConfigManager.config);
  res.status(200).json(ConfigManagerV2.getInstance().allConfigurations);
});

interface ConfigUpdateRequest {
  configPath: string;
  configValue: any;
}

app.post(
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
app.use(
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

export const startGateway = async () => {
  const port = ConfigManagerV2.getInstance().get('server.port');
  logger.info(`⚡️ Gateway API listening on port ${port}`);
  if (ConfigManagerV2.getInstance().get('server.unsafeDevModeWithHTTP')) {
    logger.info('Running in UNSAFE HTTP! This could expose private keys.');

    const swaggerDocument = SwaggerManager.generateSwaggerJson(
      './docs/swagger/swagger.yml',
      './docs/swagger/definitions.yml',
      [
        './docs/swagger/main-routes.yml',
        './docs/swagger/eth-routes.yml',
        './docs/swagger/eth-uniswap-routes.yml',
        './docs/swagger/avalanche-routes.yml',
        './docs/swagger/avalanche-pangolin-routes.yml',
      ]
    );

    // mount swagger api docs
    app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerDocument));

    server = await app.listen(port);
  } else {
    server = await addHttps(app).listen(port);
    logger.info('The server is secured behind HTTPS.');
  }
};

const stopGateway = async () => {
  return server.close();
};
