/**
 * Minimal local static file server for the packaged NEXA desktop app
 * (Part 8.5).
 *
 * Next.js's static export (`out/`) uses absolute `/_next/...` asset paths,
 * which break under a raw `file://` load in Electron. Serving `out/` over
 * loopback HTTP on an OS-assigned ephemeral port fixes that without a new
 * dependency. Bound to 127.0.0.1 only - never reachable from the network -
 * and every resolved path is checked to stay inside `rootDir` (the same
 * path-traversal discipline used by the backend's file tools).
 */
"use strict";
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
// A fixed loopback port (rather than an OS-assigned ephemeral one) so the
// packaged app's origin ("http://127.0.0.1:<port>") stays the same across
// restarts. Chromium's localStorage/IndexedDB - and therefore every
// zustand-persisted store (chat history, sidebar state, language, model
// selection cache, etc.) - is scoped per-origin, so a changing port used to
// silently wipe all of that on every launch.
const NEXA_STATIC_PORT = 48420;
const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".txt": "text/plain; charset=utf-8",
  ".map": "application/json; charset=utf-8",
};
/** Resolves `urlPath` under `rootDir`, refusing to escape it. Returns null on traversal. */
function resolveSafePath(rootDir, urlPath) {
  const normalizedRoot = path.normalize(rootDir);
  const decoded = decodeURIComponent(urlPath.split("?")[0].split("#")[0]);
  const candidate = path.normalize(path.join(normalizedRoot, decoded));
  if (candidate !== normalizedRoot && !candidate.startsWith(normalizedRoot + path.sep)) {
    return null;
  }
  return candidate;
}
function createServer(rootDir) {
  return http.createServer((req, res) => {
    const urlPath = req.url === "/" ? "/index.html" : req.url;
    const filePath = resolveSafePath(rootDir, urlPath);
    if (!filePath) {
      res.writeHead(403, { "Content-Type": "text/plain" });
      res.end("Forbidden");
      return;
    }
    fs.readFile(filePath, (err, data) => {
      if (!err) {
        res.writeHead(200, { "Content-Type": MIME_TYPES[path.extname(filePath)] || "application/octet-stream" });
        res.end(data);
        return;
      }
      // Next export emits per-route .html files for client-side navigation.
      fs.readFile(`${filePath}.html`, (err2, data2) => {
        if (!err2) {
          res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
          res.end(data2);
          return;
        }
        fs.readFile(path.join(rootDir, "404.html"), (err3, data3) => {
          res.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
          res.end(err3 ? "Not found" : data3);
        });
      });
    });
  });
}
function listen(server, port) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => resolve(server));
  });
}
/**
 * Starts the static server on the fixed ``NEXA_STATIC_PORT`` so the app's
 * origin is stable across restarts. Falls back to an OS-assigned ephemeral
 * port (old behavior) only if that fixed port is already taken by something
 * else on the machine - the app still works then, it just won't retain
 * frontend-only state (persisted via localStorage) for that session.
 */
async function startStaticServer(rootDir, preferredPort = NEXA_STATIC_PORT) {
  try {
    return await listen(createServer(rootDir), preferredPort);
  } catch (err) {
    if (err && err.code === "EADDRINUSE") {
      return listen(createServer(rootDir), 0);
    }
    throw err;
  }
}
module.exports = { startStaticServer, resolveSafePath, NEXA_STATIC_PORT };
