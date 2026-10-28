import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev server na 5173; /api vai para o uvicorn na 8000 (ver workbench/dev.sh).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "node",
    globals: true,
    // CSS fica vazio nos testes, exceto quando importado como texto (?raw): a guarda de generalidade lê os .css
    css: { include: [/\.css\?raw$/] },
  },
});
