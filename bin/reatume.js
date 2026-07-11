#!/usr/bin/env node
const { run } = require('../src/cli');

run().catch((err) => {
  process.stderr.write(`Error: ${err.message}\n`);
  process.exit(1);
});
