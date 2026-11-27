import { defineConfig } from "vite";

// Sources live in web/; the static build goes to app/, which GitHub Pages serves (legacy build from main)
// at https://unicef.github.io/GCHD/browser_app/app/ (browser_app/index.html redirects there).
export default defineConfig({
  root: "web",
  base: "./",
  build: { outDir: "../app", emptyOutDir: true, target: "es2022", chunkSizeWarningLimit: 4000 },
  worker: { format: "es" },
  test: { root: ".", include: ["tests/**/*.test.ts"] },
} as any);
