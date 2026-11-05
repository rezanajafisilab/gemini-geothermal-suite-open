/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Python server (python -m gemini_agent.server) serves the API on :8000 and, once built,
// this bundle from frontend/dist. In dev, Vite serves the UI and proxies /api to it.
const api = process.env.DIOSCURI_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  base: "/",
  server: {
    port: 5173,
    proxy: { "/api": { target: api, changeOrigin: false } },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    assetsDir: "assets",
    sourcemap: false,
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
