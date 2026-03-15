import { defineConfig } from 'tsup';

export default defineConfig([
  // Main library
  {
    entry: ['src/index.ts', 'src/sqlite-store.ts', 'src/mcp/index.ts'],
    format: ['esm'],
    dts: true,
    clean: true,
    sourcemap: true,
    target: 'es2022',
    external: ['@neondatabase/serverless', 'pg'],
  },
  // CLI with shebang
  {
    entry: ['src/mcp/cli.ts'],
    format: ['esm'],
    dts: false,
    sourcemap: true,
    target: 'es2022',
    external: ['@neondatabase/serverless', 'pg'],
    // Note: shebang added in src/mcp/cli.ts itself
  },
]);
