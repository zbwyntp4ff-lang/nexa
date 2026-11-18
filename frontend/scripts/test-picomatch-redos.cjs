'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const frontendRoot = path.resolve(__dirname, '..');
const patchFiles = {
  '2.3.2': path.join(frontendRoot, 'patches', 'picomatch-2.3.2-parse.js'),
  '4.0.7': path.join(frontendRoot, 'patches', 'picomatch-4.0.7-parse.js')
};
const patches = Object.fromEntries(
  Object.entries(patchFiles).map(([version, file]) => [version, fs.readFileSync(file, 'utf8')])
);
const constantsPatch = fs.readFileSync(path.join(frontendRoot, 'patches', 'picomatch-4.0.7-constants.js'), 'utf8');

const seen = new Set();
const packages = new Map();

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
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

  if (manifest.name === 'picomatch') {
    const expected = patches[manifest.version];
    assert.ok(expected, `Unreviewed picomatch version found: ${manifest.version}`);
    const actual = fs.readFileSync(path.join(realPath, 'lib', 'parse.js'), 'utf8');
    assert.equal(actual, expected, `Unpatched picomatch ${manifest.version} at ${realPath}`);
    if (manifest.version === '4.0.7') {
      const constants = fs.readFileSync(path.join(realPath, 'lib', 'constants.js'), 'utf8');
      assert.equal(constants, constantsPatch, `Unpatched picomatch 4.0.7 constants at ${realPath}`);
    }
    if (!packages.has(manifest.version)) packages.set(manifest.version, []);
    packages.get(manifest.version).push(realPath);
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
  assert.ok(packages.has(version), `Expected picomatch ${version} was not found`);
  const testFile = path.join(__dirname, `picomatch-redos-${version.startsWith('2.') ? 'v2' : 'v4'}.cjs`);
  const result = spawnSync(process.execPath, ['--test', testFile], {
    cwd: frontendRoot,
    encoding: 'utf8',
    timeout: 180000,
    maxBuffer: 8 * 1024 * 1024,
    env: { ...process.env, PICOMATCH_PACKAGE: packages.get(version)[0] }
  });

  assert.equal(
    result.error?.code,
    undefined,
    `picomatch ${version} test process failed: ${result.error?.message || result.error?.code || ''}`
  );
  assert.equal(
    result.status,
    0,
    `picomatch ${version} regression suite failed:\n${result.stdout || ''}\n${result.stderr || ''}`
  );
  console.log(`picomatch ${version}: ${packages.get(version).length} installed copies verified; regression suite passed`);
}
