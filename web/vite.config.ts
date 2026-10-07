import { copyFileSync, cpSync, createReadStream, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, extname, relative, resolve } from "node:path";

const projectDir = dirname(fileURLToPath(import.meta.url));
const repoDir = resolve(projectDir, "..");
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const REPO_BASE = "/bookshelves/";

const LIBRARY_FILES = [
  { source: resolve(repoDir, "data/data.json"), urlPath: "data.json" },
  { source: resolve(repoDir, "assets/covers"), urlPath: "assets/covers" }
];

const CONTENT_TYPES: Record<string, string> = {
  ".json": "application/json; charset=utf-8",
  ".webp": "image/webp",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png"
};

function resolveLibraryFile(requestPath: string): string | null {
  for (const { source, urlPath } of LIBRARY_FILES) {
    if (requestPath !== urlPath && !requestPath.startsWith(`${urlPath}/`)) continue;
    const filePath = resolve(source, `.${requestPath.slice(urlPath.length)}`);
    const insideSource = relative(source, filePath);
    if (insideSource.startsWith("..")) return null;
    try {
      return statSync(filePath).isFile() ? filePath : null;
    } catch {
      return null;
    }
  }
  return null;
}

function libraryFiles(): Plugin {
  return {
    name: "library-files",
    configureServer(server) {
      server.middlewares.use(REPO_BASE, (request, response, next) => {
        let requestPath: string;
        try {
          requestPath = decodeURIComponent((request.url ?? "").split("?")[0]).replace(/^\/+/, "");
        } catch {
          return next();
        }
        const filePath = resolveLibraryFile(requestPath);
        if (!filePath) return next();
        response.setHeader("Content-Type", CONTENT_TYPES[extname(filePath).toLowerCase()] ?? "application/octet-stream");
        response.setHeader("Cache-Control", "no-cache");
        createReadStream(filePath).pipe(response);
      });
    },
    writeBundle(options) {
      const outDir = options.dir ?? resolve(projectDir, "dist");
      for (const { source, urlPath } of LIBRARY_FILES) {
        cpSync(source, resolve(outDir, urlPath), { recursive: true });
      }
    }
  };
}

function spaFallbackPage(): Plugin {
  return {
    name: "spa-fallback-page",
    closeBundle() {
      const outDir = resolve(projectDir, "dist");
      copyFileSync(resolve(outDir, "index.html"), resolve(outDir, "404.html"));
    }
  };
}

export default defineConfig(() => ({
  base: REPO_BASE,
  publicDir: false as const,
  plugins: [react(), libraryFiles(), spaFallbackPage()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false
  },
  server: {
    port: 5173,
    open: false
  }
}));
