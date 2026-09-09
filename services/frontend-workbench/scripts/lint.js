const childProcess = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const directories = ["src", "scripts", "tests"];
const files = [];

function collect(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      collect(file);
    } else if (entry.name.endsWith(".js")) {
      files.push(file);
    }
  }
}

for (const directory of directories) {
  collect(path.join(root, directory));
}

for (const file of files) {
  const result = childProcess.spawnSync(process.execPath, ["--check", file], {
    stdio: "inherit",
  });
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
  if (!file.startsWith(path.join(root, "scripts")) && fs.readFileSync(file, "utf8").includes("console.log(")) {
    process.stderr.write(`console.log is not allowed in ${path.relative(root, file)}\n`);
    process.exit(1);
  }
}
