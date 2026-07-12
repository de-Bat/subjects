import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Dev proxy: /api and /share-target go to the FastAPI backend.
const API_TARGET = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      // We inject our own service worker (handles the share_target POST).
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw-share-target.ts",
      manifest: {
        name: "Subjects",
        short_name: "Subjects",
        description: "Self-hosted AI capture — share anything, get a typed, filed item.",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
        // Android Web Share Target (spec Section 5). iOS does NOT support this.
        share_target: {
          action: "/share-target",
          method: "POST",
          enctype: "multipart/form-data",
          params: {
            title: "title",
            text: "text",
            url: "url",
            files: [{ name: "media", accept: ["image/*"] }],
          },
        },
      },
    }),
  ],
  server: {
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
    },
  },
});
