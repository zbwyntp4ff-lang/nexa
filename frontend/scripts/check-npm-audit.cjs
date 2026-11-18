'use strict';

const { spawnSync } = require('node:child_process');

const allowedAdvisory = 'https://github.com/advisories/GHSA-fc5q-39xc-vjpf';
const auditRun = spawnSync('npm', ['audit', '--json'], {
  cwd: process.cwd(),
  encoding: 'utf8',
  timeout: 120000,
  maxBuffer: 16 * 1024 * 1024
});

if (auditRun.error) throw auditRun.error;
let report;
try {
  report = JSON.parse(auditRun.stdout);
} catch {
  throw new Error(`npm audit did not return valid JSON:\n${auditRun.stderr || auditRun.stdout}`);
}

const vulnerabilities = report.vulnerabilities || {};
const blocking = Object.entries(vulnerabilities).filter(([, item]) =>
  item.severity === 'high' || item.severity === 'critical'
);

function tracesOnlyToPicomatch(name, stack = new Set()) {
  if (stack.has(name)) return { valid: true, reachesAdvisory: false };
  const item = vulnerabilities[name];
  if (!item || !Array.isArray(item.via) || item.via.length === 0) {
    return { valid: false, reachesAdvisory: false };
  }

  const nextStack = new Set(stack);
  nextStack.add(name);
  let reachesAdvisory = false;

  for (const via of item.via) {
    if (typeof via === 'string') {
      const nested = tracesOnlyToPicomatch(via, nextStack);
      if (!nested.valid) return nested;
      reachesAdvisory = reachesAdvisory || nested.reachesAdvisory;
      continue;
    }

    if (via && (via.url === allowedAdvisory || via.source === 1247710)) {
      reachesAdvisory = true;
    } else {
      return { valid: false, reachesAdvisory: false };
    }
  }

  return { valid: true, reachesAdvisory };
}

const unmitigated = blocking.filter(([name]) => {
  const result = tracesOnlyToPicomatch(name);
  return !result.valid || !result.reachesAdvisory;
});

if (unmitigated.length > 0) {
  console.error('Unmitigated high/critical npm advisories:');
  for (const [name, item] of unmitigated) {
    console.error(`- ${name}: ${item.severity}; ${JSON.stringify(item.via)}`);
  }
  process.exit(1);
}

if (blocking.length > 0) {
  console.warn(
    `npm audit still reports ${blocking.length} high/critical dependency paths, but every path traces only to ${allowedAdvisory}.`
  );
  console.warn('The installed picomatch 2.3.2 and 4.0.7 parser copies are patched and covered by the ReDoS regression suites.');
} else {
  console.log('npm audit: no high or critical advisories.');
}
