import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev server na 5173; /api vai para o uvicorn na 8000 (ver workbench/dev.sh). As portas aceitam override por ambiente.
const apiPort = process.env.WORKBENCH_API_PORT ?? "8000";
const webPort = Number(process.env.WORKBENCH_WEB_PORT ?? 5173);

export default defineConfig({
  plugins: [react()],
  server: {
    port: webPort,
    proxy: { "/api": `http://localhost:${apiPort}` },
  },
  test: {
    environment: "node",
    globals: true,
    // CSS fica vazio nos testes, exceto quando importado como texto (?raw): a guarda de generalidade lê os .css
    css: { include: [/\.css\?raw$/] },
  },
});
