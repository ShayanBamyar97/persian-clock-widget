#!/usr/bin/env node
"use strict";

const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const rootDir = path.resolve(__dirname, "..");
const winExe = path.join(rootDir, "release", "windows", "PersianClockWidget.exe");
const mainPy = path.join(rootDir, "main.py");

function launchDetached(cmd, args, cwd) {
  const child = spawn(cmd, args, {
    cwd,
    detached: true,
    stdio: "ignore",
    windowsHide: false,
  });
  child.unref();
}

if (process.platform === "win32" && fs.existsSync(winExe)) {
  console.log("Launching Persian Clock & Calendar Widget (Windows)...");
  launchDetached(winExe, [], rootDir);
  process.exit(0);
}

const pyCandidates = process.platform === "win32" ? ["python", "python3", "py"] : ["python3", "python"];
let pyBin = null;

for (const candidate of pyCandidates) {
  const res = spawnSync(candidate, ["--version"], { stdio: "ignore" });
  if (res.status === 0) {
    pyBin = candidate;
    break;
  }
}

if (!pyBin) {
  console.error("Error: Python 3 is required on this platform.");
  if (process.platform === "linux") {
    console.error("Install it with: sudo apt install python3 python3-tk");
  } else if (process.platform === "darwin") {
    console.error("Install it with: brew install python python-tk");
  }
  process.exit(1);
}

const tkCheck = spawnSync(pyBin, ["-c", "import tkinter"], { stdio: "ignore" });
if (tkCheck.status !== 0) {
  console.error("Error: python3-tk (Tkinter) is not installed.");
  if (process.platform === "linux") {
    console.error("  Ubuntu/Debian: sudo apt update && sudo apt install -y python3-tk");
    console.error("  Fedora:        sudo dnf install -y python3-tkinter");
    console.error("  Arch/Manjaro:  sudo pacman -S tk");
  } else if (process.platform === "darwin") {
    console.error("  macOS (Homebrew): brew install python-tk");
  }
  process.exit(1);
}

console.log("Launching Persian Clock & Calendar Widget...");
launchDetached(pyBin, [mainPy], rootDir);
process.exit(0);
