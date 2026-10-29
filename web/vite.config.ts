import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    // Production is served by FastAPI from the repository-level dist folder.
    // Keep unrelated desktop packaging artifacts that may already be present.
    outDir: "../dist",
    emptyOutDir: false,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
