import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const securityHeaders = {
  "Content-Security-Policy": "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws://localhost:5173 ws://127.0.0.1:5173",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "same-origin",
  "X-Frame-Options": "DENY",
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    headers: securityHeaders,
    proxy: { "/api": "http://localhost:8000" },
  },
  preview: { headers: securityHeaders },
});
