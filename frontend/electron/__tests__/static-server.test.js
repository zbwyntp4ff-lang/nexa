/**
 * Tests for the packaged-app static file server's path-traversal guard
 * (Part 8.5). No real Electron runtime needed - pure Node `http`/`fs`.
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { resolveSafePath, startStaticServer } from "../static-server.js";
describe("resolveSafePath", () => {
  const root = "/opt/nexa/out";
  it("resolves a normal path under the root", () => {
    expect(resolveSafePath(root, "/index.html")).toBe(path.join(root, "index.html"));
  });
  it("refuses to escape the root via ../", () => {
    expect(resolveSafePath(root, "/../../etc/passwd")).toBeNull();
  });
  it("refuses a URL-encoded traversal attempt", () => {
    expect(resolveSafePath(root, "/%2e%2e/%2e%2e/etc/passwd")).toBeNull();
  });
  it("treats the root itself as valid", () => {
    expect(resolveSafePath(root, "/")).not.toBeNull();
    expect(path.normalize(resolveSafePath(root, "/"))).toBe(path.normalize(`${root}/`));
  });
});
describe("startStaticServer", () => {
  let tmpDir;
  let server;
  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "nexa-out-"));
    fs.writeFileSync(path.join(tmpDir, "index.html"), "<html>NEXA</html>");
    fs.mkdirSync(path.join(tmpDir, "secret_sibling_dir"), { recursive: true });
  });
  afterEach(() => {
    server?.close();
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });
  it("serves index.html for /", async () => {
    server = await startStaticServer(tmpDir);
    const { port } = server.address();
    const res = await fetch(`http://127.0.0.1:${port}/`);
    expect(res.status).toBe(200);
    expect(await res.text()).toContain("NEXA");
  });
  it("returns 403 for a path-traversal attempt instead of leaking files", async () => {
    server = await startStaticServer(tmpDir);
    const { port } = server.address();
    const res = await fetch(`http://127.0.0.1:${port}/../../../etc/passwd`);
    expect([403, 404]).toContain(res.status);
    const body = await res.text();
    expect(body).not.toContain("root:");
  });
  it("is only reachable on loopback, not on all interfaces", async () => {
    server = await startStaticServer(tmpDir);
    expect(server.address().address).toBe("127.0.0.1");
  });
});
