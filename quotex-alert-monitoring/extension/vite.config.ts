import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";
import { copyFileSync, mkdirSync, existsSync } from "fs";

function copyStaticFiles() {
  return {
    name: "copy-static-files",
    closeBundle() {
      const distDir = resolve(__dirname, "dist");
      const assetsDir = resolve(distDir, "assets");
      if (!existsSync(assetsDir)) mkdirSync(assetsDir, { recursive: true });

      // Copy manifest.json
      copyFileSync(resolve(__dirname, "manifest.json"), resolve(distDir, "manifest.json"));

      // Copy overlay.css
      copyFileSync(resolve(__dirname, "src/styles/overlay.css"), resolve(assetsDir, "overlay.css"));

      // Copy icons
      const iconsDir = resolve(__dirname, "icons");
      const distIconsDir = resolve(distDir, "icons");
      if (existsSync(iconsDir)) {
        if (!existsSync(distIconsDir)) mkdirSync(distIconsDir, { recursive: true });
        for (const icon of ["icon-16.png", "icon-48.png", "icon-128.png"]) {
          const src = resolve(iconsDir, icon);
          if (existsSync(src)) copyFileSync(src, resolve(distIconsDir, icon));
        }
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), copyStaticFiles()],
  resolve: {
    alias: {
      "@shared": resolve(__dirname, "src/shared"),
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        "service-worker": resolve(__dirname, "src/background/service-worker.ts"),
        "content-script": resolve(__dirname, "src/content/content-script.ts"),
        "ws-interceptor": resolve(__dirname, "src/content/ws-interceptor.ts"),
        popup: resolve(__dirname, "popup.html"),
      },
      output: {
        entryFileNames: (chunkInfo) => {
          if (chunkInfo.name === "service-worker") return "service-worker.js";
          if (chunkInfo.name === "content-script") return "content-script.js";
          if (chunkInfo.name === "ws-interceptor") return "ws-interceptor.js";
          return "assets/[name]-[hash].js";
        },
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash].[ext]",
      },
    },
    target: "esnext",
    minify: "esbuild",
  },
});
