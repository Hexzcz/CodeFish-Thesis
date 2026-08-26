/**
 * Start the app, run the browser tests against it, stop the app.
 *
 * Self-contained on purpose: `npm test` should work from a clean checkout
 * without anyone remembering to start a server in another terminal.
 */
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const REPO = path.resolve(__dirname, '..', '..');
const PORT = process.env.CODEFISH_PORT || '8000';
const URL = `http://127.0.0.1:${PORT}`;
const PYTHON = process.env.CODEFISH_PYTHON || path.join(REPO, '.venv', 'bin', 'python');

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function isUp() {
  try {
    const res = await fetch(`${URL}/health`);
    return res.ok;
  } catch (e) {
    return false;
  }
}

(async () => {
  let server = null;

  if (await isUp()) {
    console.log(`• using the server already running on ${URL}`);
  } else {
    console.log(`• starting the app on ${URL}`);
    server = spawn(PYTHON, ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', PORT], {
      cwd: REPO,
      env: { ...process.env, USE_LOCAL_DATA: '1' },
      stdio: 'ignore',
    });

    const deadline = Date.now() + 120000;
    while (Date.now() < deadline && !(await isUp())) await sleep(1000);

    if (!(await isUp())) {
      server.kill();
      console.error('the app did not start — is the virtualenv installed?');
      process.exit(1);
    }
  }

  // Name the files explicitly: passing the directory makes node try to
  // resolve it as a module instead of scanning it for tests.
  const files = fs.readdirSync(__dirname)
    .filter(name => name.endsWith('.test.js'))
    .map(name => path.join(__dirname, name));

  const result = spawnSync(process.execPath, ['--test', '--test-concurrency=1', ...files], {
    stdio: 'inherit',
    env: { ...process.env, CODEFISH_URL: URL },
  });

  if (server) server.kill();
  process.exit(result.status === null ? 1 : result.status);
})();
