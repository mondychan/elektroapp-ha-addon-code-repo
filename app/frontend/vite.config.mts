import { defineConfig } from "vitest/config";
import { transformWithEsbuild } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          const normalizedId = id.replace(/\\/g, "/");

          if (!normalizedId.includes("/node_modules/")) return undefined;

          if (
            normalizedId.includes("/node_modules/react/") ||
            normalizedId.includes("/node_modules/react-dom/") ||
            normalizedId.includes("/node_modules/scheduler/")
          ) {
            return "vendor-react";
          }

          if (
            normalizedId.includes("/node_modules/chart.js/") ||
            normalizedId.includes("/node_modules/react-chartjs-2/") ||
            normalizedId.includes("/node_modules/chartjs-")
          ) {
            return "vendor-charts";
          }

          if (normalizedId.includes("/node_modules/framer-motion/")) {
            return "vendor-motion";
          }

          if (normalizedId.includes("/node_modules/react-day-picker/")) {
            return "vendor-calendar";
          }

          return undefined;
        },
      },
    },
  },
  plugins: [
    {
      name: "load-js-as-jsx",
      enforce: "pre",
      async transform(code, id) {
        if (!id.includes("/src/") && !id.includes("\\src\\")) return null;
        if (!id.endsWith(".js")) return null;
        return transformWithEsbuild(code, id, {
          loader: "jsx",
          jsx: "automatic",
        });
      },
    },
    react(),
  ],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.js",
    css: true,
  },
});
