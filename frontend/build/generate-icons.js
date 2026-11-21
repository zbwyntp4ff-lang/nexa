/**
 * Generates desktop-packaging icons from NEXA's existing logo (Part 8.5).
 *
 * Never creates a new logo - only converts the existing
 * `frontend/public/nexa-logo.png` into the formats electron-builder needs
 * per platform (a real multi-size .ico for Windows; the source PNG is used
 * as-is for Linux). Run automatically before `electron-builder` via the
 * `dist:electron*` npm scripts.
 */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const sharp = require("sharp");
const SOURCE_LOGO = path.join(__dirname, "..", "public", "nexa-logo.png");
const OUT_DIR = __dirname;
// Standard Windows .ico frame sizes. NSIS's bundled icon reader rejects a
// single oversized (e.g. 1080x1080) frame with "invalid icon file size" -
// each frame must be a normal icon resolution.
const ICO_SIZES = [16, 24, 32, 48, 64, 128, 256];
async function convertPngToIco(framePaths) {
  // png-to-ico v3 is ESM-first; load its default export from this CommonJS script.
  const module = await import("png-to-ico");
  const convert = module.default || module;
  if (typeof convert !== "function") {
    throw new TypeError("png-to-ico did not expose a callable default export");
  }
  return convert(framePaths);
}

async function main() {
  if (!fs.existsSync(SOURCE_LOGO)) {
    throw new Error(`NEXA logo not found at ${SOURCE_LOGO}`);
  }
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "nexa-icons-"));
  const framePaths = await Promise.all(
    ICO_SIZES.map(async (size) => {
      const framePath = path.join(tmpDir, `icon-${size}.png`);
      await sharp(SOURCE_LOGO).resize(size, size).png().toFile(framePath);
      return framePath;
    })
  );
  const icoBuffer = await convertPngToIco(framePaths);
  fs.writeFileSync(path.join(OUT_DIR, "icon.ico"), icoBuffer);
  // A single reasonably-sized PNG is enough for Linux/tray icons.
  await sharp(SOURCE_LOGO).resize(512, 512).png().toFile(path.join(OUT_DIR, "icon.png"));
  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log("Generated build/icon.ico and build/icon.png from the existing NEXA logo.");
}
if (require.main === module) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { convertPngToIco };
