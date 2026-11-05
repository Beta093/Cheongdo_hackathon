const { defineConfig } = require("@playwright/test");
const path = require("node:path");

module.exports = defineConfig({
  testDir: ".",
  testMatch: "flow.spec.js",
  workers: 1,
  retries: 0,
  use: { baseURL: "http://127.0.0.1:8011", viewport: { width: 390, height: 844 } },
  webServer: {
    command: process.env.E2E_SERVER_COMMAND || "python -m uvicorn e2e.server:app --host 127.0.0.1 --port 8011 --workers 1 --no-access-log",
    cwd: path.resolve(__dirname, ".."),
    url: "http://127.0.0.1:8011/",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
