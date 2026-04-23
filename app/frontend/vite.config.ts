import { defineConfig } from "vitest/config";
import { transformWithEsbuild } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
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
