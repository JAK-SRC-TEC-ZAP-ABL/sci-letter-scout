import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.mjs';

const secret = 'a'.repeat(40);
const token = 'device-token-example-12345';
const records = [];
const env = {
  ADMIN_SECRET: secret,
  TOKEN_ENCRYPTION_KEY: Buffer.alloc(32, 7).toString('base64'),
  DB: { prepare(sql) { return { bind(...args) { return {
    async run() {
      if (sql.startsWith('DELETE')) {
        const index = records.findIndex(record => record[0] === args[0]);
        if (index >= 0) records.splice(index, 1);
      } else records.push(args);
    },
    async first() {
      const saved = records.find(record => record[0] === args[0]);
      return saved ? { token_iv: saved[2], token_ciphertext: saved[3] } : null;
    },
  }; } }; } },
};
function registration(auth, value = { token, specialty: 'oncology' }) {
  return new Request('https://example.test/admin/devices', {
    method: 'POST', headers: { Authorization: `Bearer ${auth}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  });
}

test('requires administrator credential', async () => {
  const response = await worker.fetch(registration('wrong'), env);
  assert.equal(response.status, 401);
  assert.equal(records.length, 0);
});

test('stores an encrypted token only and does not return the token', async () => {
  const response = await worker.fetch(registration(secret), env);
  assert.equal(response.status, 201);
  const body = await response.text();
  assert.ok(!body.includes(token));
  const saved = records.at(-1);
  assert.equal(saved[1], 'oncology');
  assert.ok(!JSON.stringify(saved).includes(token));
  assert.equal(saved[2].length, 24);
});

test('rejects unsupported specialty', async () => {
  const response = await worker.fetch(registration(secret, { token, specialty: 'other' }), env);
  assert.equal(response.status, 400);
});

test('test sending is disabled without explicit configuration', async () => {
  const request = new Request('https://example.test/admin/test-notification', {
    method: 'POST', headers: { Authorization: `Bearer ${secret}` }, body: '{}',
  });
  assert.equal((await worker.fetch(request, env)).status, 503);
});

test('sends decrypted token only to Huawei and distinguishes acceptance from delivery', async () => {
  const id = records.at(-1)[0];
  const testEnv = { ...env, ALLOW_TEST_PUSH: 'YES', HUAWEI_PROJECT_ID: '123', HUAWEI_TEST_JWT: 'test-jwt' };
  const request = new Request('https://example.test/admin/test-notification', {
    method: 'POST', headers: { Authorization: `Bearer ${secret}` },
    body: JSON.stringify({ id, title: 'title', body: 'body', category: 'WORK' }),
  });
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, 'https://push-api.cloud.huawei.com/v3/123/messages:send');
      assert.equal(JSON.parse(options.body).target.token[0], token);
      assert.equal(JSON.parse(options.body).pushOptions.testMessage, true);
      return Response.json({ code: '80000000' });
    };
    const response = await worker.fetch(request, testEnv);
    assert.deepEqual(await response.json(), { status: 'accepted', delivery: 'unconfirmed' });
  } finally { globalThis.fetch = originalFetch; }
});

test('administrator can delete a registered device', async () => {
  const id = records.at(-1)[0];
  const request = new Request(`https://example.test/admin/devices/${id}`, {
    method: 'DELETE', headers: { Authorization: `Bearer ${secret}` },
  });
  assert.equal((await worker.fetch(request, env)).status, 200);
  assert.equal(records.some(record => record[0] === id), false);
});
