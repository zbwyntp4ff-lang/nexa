# Frontend dependency security patches

The npm audit currently reports GHSA-fc5q-39xc-vjpf / CVE-2026-112366 through picomatch.

- picomatch 2.3.2 parser patch: backport proposed in upstream PR #265, commit `dda1c43a8e9cae36ffb0407127ee64e17fbc1c2c`.
- picomatch 4.0.7 parser patch: proposed in upstream PR #264, commit `8144a1a22a8fa1766951411f220cc8c6228cb041`.
- The 4.0.7 parser patch is based on the upstream development branch, so the matching `lib/constants.js` change from that same upstream base is applied with it.
- `npm ci` applies the patch only to the exact known upstream package versions and verifies their original Git blob hashes before changing files. Unknown versions or unexpected source contents fail installation.
- The regression tests are adapted from the upstream PR test suites and run against both installed versions.
- The npm audit database still reports the advisory because upstream has not published a fixed npm release. CI permits only high/critical dependency paths that resolve exclusively to this single advisory, and only after the patched source and regression suites are verified. Any unrelated high/critical advisory still fails CI.

Revisit and remove these local patches when an official fixed picomatch release is available and validated.
