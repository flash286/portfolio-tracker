import { defineConfig } from "vite";
import preact from "@preact/preset-vite";
import { viteSingleFile } from "vite-plugin-singlefile";

const apiPort = process.env.VITE_API_PORT || 3001;

export default defineConfig({
  plugins: [preact(), viteSingleFile()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": `http://127.0.0.1:${apiPort}`,
    },
  },
});
