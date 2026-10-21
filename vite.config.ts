import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/rest/": {
        target: "http://localhost:54321",
        changeOrigin: true,
      },
      "/realtime/": {
        target: "ws://localhost:54321",
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
