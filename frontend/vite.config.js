import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        // Surface backend-down errors loudly instead of swallowing them
        // into silent 404s.
        configure: (proxy) => {
          proxy.on("error", (err, req, res) => {
            console.error("[vite proxy] backend unreachable:", err.code || err.message);
            if (!res.headersSent && res.writeHead) {
              res.writeHead(502, { "Content-Type": "application/json" });
              res.end(
                JSON.stringify({
                  detail:
                    "Backend not running on http://localhost:8000. Start it with: uvicorn api.main:app --reload",
                })
              );
            }
          });
        },
      },
    },
  },
});
