/**
 * Cross-platform Electron Next build.
 * Sets NEXA_TARGET=electron then runs `next build` (works on Windows PowerShell
 * where `NEXA_TARGET=electron next build` is not valid shell syntax).
 */
"use strict";
const { spawnSync } = require("node:child_process");
const path = require("node:path");

const env = { ...process.env, NEXA_TARGET: "electron" };
const nextBin = path.join(
  __dirname,
  "..",
  "node_modules",
  "next",
  "dist",
  "bin",
  "next"
);
const result = spawnSync(process.execPath, [nextBin, "build"], {
  env,
  stdio: "inherit",
  cwd: path.join(__dirname, ".."),
});
process.exit(result.status === null ? 1 : result.status);
