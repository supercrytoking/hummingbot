module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  forceExit: true,
  coveragePathIgnorePatterns: [
    'src/app.ts',
    'src/https.ts',
    'src/services/ethereum-base.ts',
    'src/services/telemetry-transport.ts',
    'src/chains/ethereum/ethereum.ts',
    'src/chains/ethereum/uniswap/uniswap.ts',
    'src/chains/avalanche/avalanche.ts',
    'src/chains/avalanche/pangolin/pangolin.ts',
    'conf/migration/migrations.js',
    'src/chains/solana/solana.ts',
  ],
  modulePathIgnorePatterns: ['<rootDir>/dist/'],
  setupFilesAfterEnv: ['<rootDir>/test/setupTests.js'],
};
