Runnable Node.js scaffold for the frontend-workbench migration demo.
It provides dependency-free client and SSR build outputs with Node tests.
Run `npm ci && npm run lint && npm test` from this directory.
`scripts/test.js` ignores extra arguments, so `npm test -- --ci --coverage` (as the pipeline runs it) produces no coverage report.
Use Node.js 18.1+ or 20: Node 18.0 rejects `--test`, and on Node 22+ `npm test` fails with "Cannot find module '.../tests'".
