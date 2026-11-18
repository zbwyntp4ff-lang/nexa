'use strict';

const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');

const frontendRoot = path.resolve(__dirname, '..');
const patchFiles = {
  '2.3.2': path.join(frontendRoot, 'patches', 'picomatch-2.3.2-parse.js'),
  '4.0.7': path.join(frontendRoot, 'patches', 'picomatch-4.0.7-parse.js')
};
const patches = Object.fromEntries(
  Object.entries(patchFiles).map(([version, file]) => [version, fs.readFileSync(file, 'utf8')])
);
const constantsPatch = fs.readFileSync(path.join(frontendRoot, 'patches', 'picomatch-4.0.7-constants.js'), 'utf8');
const expectedParseBlobs = {
  '2.3.2': 'caa2b86aa5a567df33cef4bda3c7a97794f439f8',
  '4.0.7': '29207512c60183b4bb9bf5112be3b9b5f4a9a9fd'
};
const expectedV4ConstantsBlob = 'f0aeda7d48171c71603af40d23bd4c8de7522c0e';
const gitBlobSha = content => crypto.createHash('sha1')
  .update('blob ' + Buffer.byteLength(content) + '\0')
  .update(content)
  .digest('hex');

const seen = new Set();
const patched = [];

function inspectPackage(packageDir) {
  if (!fs.existsSync(packageDir)) return;
  let realPath;
  try {
    realPath = fs.realpathSync(packageDir);
    if (seen.has(realPath)) return;
    seen.add(realPath);
  } catch {
    return;
  }

  const manifestPath = path.join(realPath, 'package.json');
  if (!fs.existsSync(manifestPath)) return;

  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  } catch (error) {
    throw new Error(`Cannot read package manifest at ${manifestPath}: ${error.message}`);
  }

  if (manifest.name === 'picomatch') {
    const patch = patches[manifest.version];
    if (!patch) {
      throw new Error(`Unreviewed picomatch version found: ${manifest.version} at ${realPath}`);
    }
    const parsePath = path.join(realPath, 'lib', 'parse.js');
    if (!fs.existsSync(parsePath)) throw new Error(`Missing picomatch parser: ${parsePath}`);
    const current = fs.readFileSync(parsePath, 'utf8');
    if (current !== patch) {
      if (gitBlobSha(current) !== expectedParseBlobs[manifest.version]) {
        throw new Error(`Unexpected picomatch ${manifest.version} parser contents at ${parsePath}`);
      }
      fs.writeFileSync(parsePath, patch, 'utf8');
    }
    if (manifest.version === '4.0.7') {
      const constantsPath = path.join(realPath, 'lib', 'constants.js');
      const currentConstants = fs.readFileSync(constantsPath, 'utf8');
      if (currentConstants !== constantsPatch) {
        if (gitBlobSha(currentConstants) !== expectedV4ConstantsBlob) {
          throw new Error(`Unexpected picomatch 4.0.7 constants at ${constantsPath}`);
        }
        fs.writeFileSync(constantsPath, constantsPatch, 'utf8');
      }
    }
    patched.push({ version: manifest.version, path: realPath });
  }

  scanNodeModules(path.join(realPath, 'node_modules'));
}

function scanNodeModules(nodeModulesPath) {
  if (!fs.existsSync(nodeModulesPath)) return;
  for (const entry of fs.readdirSync(nodeModulesPath, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    const entryPath = path.join(nodeModulesPath, entry.name);
    if (entry.name.startsWith('@') && entry.isDirectory()) {
      for (const scoped of fs.readdirSync(entryPath, { withFileTypes: true })) {
        if (scoped.isDirectory() || scoped.isSymbolicLink()) {
          inspectPackage(path.join(entryPath, scoped.name));
        }
      }
    } else if (entry.isDirectory() || entry.isSymbolicLink()) {
      inspectPackage(entryPath);
    }
  }
}

scanNodeModules(path.join(frontendRoot, 'node_modules'));

for (const version of Object.keys(patches)) {
  if (!patched.some(item => item.version === version)) {
    throw new Error(`Expected picomatch ${version} was not found; refusing to continue`);
  }
}

console.log(`Applied verified ReDoS parser patches to ${patched.length} picomatch copies:`);
for (const item of patched) console.log(`- ${item.version}: ${item.path}`);
