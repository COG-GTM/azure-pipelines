const childProcess = require("node:child_process");

const result = childProcess.spawnSync(process.execPath, ["--test", "tests/"], {
  stdio: "inherit",
});
process.exit(result.status ?? 1);
