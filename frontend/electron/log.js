/**
 * Minimal desktop-shell logger (Part 8.5).
 *
 * Intentionally tiny (no new dependency): writes timestamped lines to a
 * rotating-free log file under the app's userData directory. Backend
 * stdout/stderr lines are already redacted by the backend's own
 * SecretRedactionFilter before they ever reach here - this module never
 * receives raw request bodies, env vars, or file contents, so it has
 * nothing further to scrub. Debug detail (stack-shaped lines) stays in this
 * file; user-facing errors are shown via native dialogs instead, kept short.
 */
"use strict";
const fs = require("node:fs");
const path = require("node:path");
function createLogger(logDir) {
  try {
    fs.mkdirSync(logDir, { recursive: true });
  } catch {
    // best-effort - if we can't create the log dir, fall back to console only
  }
  const logFile = path.join(logDir, "nexa-desktop.log");
  function write(line) {
    const stamped = `${new Date().toISOString()} ${line}`;
    // eslint-disable-next-line no-console
    console.log(stamped);
    try {
      fs.appendFileSync(logFile, stamped + "\n");
    } catch {
      // logging must never crash the app
    }
  }
  return { write, logFile };
}
module.exports = { createLogger };
