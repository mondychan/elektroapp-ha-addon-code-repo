"use strict";

const fs = require("fs");
const path = require("path");

const targetFile = path.resolve(__dirname, "..", "node_modules", "react-dev-utils", "checkRequiredFiles.js");

try {
  if (!fs.existsSync(targetFile)) {
    console.log("[postinstall] react-dev-utils patch skipped (file not found).");
    process.exit(0);
  }

  const source = fs.readFileSync(targetFile, "utf8");
  if (!source.includes("fs.F_OK")) {
    console.log("[postinstall] react-dev-utils patch not needed.");
    process.exit(0);
  }

  const patched = source.replace(/fs\.F_OK/g, "fs.constants.F_OK");
  fs.writeFileSync(targetFile, patched, "utf8");
  console.log("[postinstall] react-dev-utils patched: fs.F_OK -> fs.constants.F_OK");
} catch (err) {
  console.error("[postinstall] Failed to patch react-dev-utils:", err);
  process.exit(1);
}
