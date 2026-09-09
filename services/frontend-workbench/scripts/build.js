const fs = require("node:fs");
const path = require("node:path");

const mode = process.argv[2];
const source = fs.readFileSync(path.join(__dirname, "..", "src", "app.js"), "utf8");
const buildRoot = path.join(__dirname, "..", "build");

if (!["client", "ssr"].includes(mode)) {
  process.stderr.write("usage: node scripts/build.js client|ssr\n");
  process.exit(1);
}

if (mode === "client") {
  const outputDirectory = path.join(buildRoot, "client");
  fs.mkdirSync(outputDirectory, { recursive: true });
  fs.writeFileSync(path.join(outputDirectory, "bundle.js"), `'use strict';\n${source}`);
} else {
  const outputDirectory = path.join(buildRoot, "ssr");
  fs.mkdirSync(outputDirectory, { recursive: true });
  fs.writeFileSync(path.join(outputDirectory, "server.js"), `'use strict';\n${source}`);
  fs.writeFileSync(
    path.join(buildRoot, "index.html"),
    "<!doctype html><html><body><div id=\"root\"></div></body></html>\n"
  );
}
