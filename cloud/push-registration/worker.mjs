// Staging-only registration API. It is intentionally not an end-user API:
// only an administrator with a server-held secret may register a device.
const encoder = new TextEncoder();

function reply(status, body) {
  return Response.json(body, { status, headers: { 'Cache-Control': 'no-store' } });
}

async function authorized(request, secret) {
  if (typeof secret !== 'string' || secret.length < 32) return false;
  const header = request.headers.get('Authorization') || '';
  if (!header.startsWith('Bearer ')) return false;
  const supplied = header.slice(7);
  if (supplied.length > 512) return false;
  const key = await crypto.subtle.importKey('raw', encoder.encode('sci-letter-scout-admin-comparison'),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
  const reference = await crypto.subtle.sign('HMAC', key, encoder.encode(secret));
  return crypto.subtle.verify('HMAC', key, reference, encoder.encode(supplied));
}

async function encryptToken(token, encodedKey) {
  const binary = atob(encodedKey);
  const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
  if (bytes.byteLength !== 32) throw new Error('Invalid encryption key');
  const key = await crypto.subtle.importKey('raw', bytes, 'AES-GCM', false, ['encrypt']);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, encoder.encode(token)));
  return { iv: Array.from(iv, b => b.toString(16).padStart(2, '0')).join(''),
    ciphertext: Array.from(encrypted, b => b.toString(16).padStart(2, '0')).join('') };
}

async function decryptToken(record, encodedKey) {
  const keyBytes = Uint8Array.from(atob(encodedKey), c => c.charCodeAt(0));
  if (keyBytes.length !== 32 || !/^[0-9a-f]{24}$/.test(record.token_iv) ||
      !/^(?:[0-9a-f]{2})+$/.test(record.token_ciphertext)) throw new Error('Invalid encrypted record');
  const iv = Uint8Array.from(record.token_iv.match(/../g), value => parseInt(value, 16));
  const ciphertext = Uint8Array.from(record.token_ciphertext.match(/../g), value => parseInt(value, 16));
  const key = await crypto.subtle.importKey('raw', keyBytes, 'AES-GCM', false, ['decrypt']);
  return new TextDecoder().decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ciphertext));
}

async function readBody(request) {
  if (Number(request.headers.get('Content-Length') || 0) > 4096) throw new Error('too large');
  const text = await request.text();
  if (encoder.encode(text).length > 4096) throw new Error('too large');
  return JSON.parse(text);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === 'GET' && url.pathname === '/health') return reply(200, { status: 'ok', mode: 'staging' });
    if (!await authorized(request, env.ADMIN_SECRET)) return reply(401, { error: 'unauthorized' });
    if (!env.DB || !env.TOKEN_ENCRYPTION_KEY) return reply(503, { error: 'not configured' });
    const deleteMatch = url.pathname.match(/^\/admin\/devices\/([0-9a-f-]{36})$/i);
    if (request.method === 'DELETE' && deleteMatch) {
      try {
        await env.DB.prepare('DELETE FROM devices WHERE id = ?').bind(deleteMatch[1]).run();
        return reply(200, { status: 'deleted' });
      } catch { return reply(500, { error: 'deletion failed' }); }
    }
    if (request.method === 'POST' && url.pathname === '/admin/devices') {
      let input;
      try { input = await readBody(request); } catch { return reply(400, { error: 'invalid request' }); }
      if (!input || typeof input.token !== 'string' || input.token.length < 16 || input.token.length > 2048 ||
          !['oncology', 'anesthesiology'].includes(input.specialty)) return reply(400, { error: 'invalid request' });
      try {
        const sealed = await encryptToken(input.token, env.TOKEN_ENCRYPTION_KEY);
        const id = crypto.randomUUID();
        await env.DB.prepare('INSERT INTO devices (id, specialty, token_iv, token_ciphertext) VALUES (?, ?, ?, ?)')
          .bind(id, input.specialty, sealed.iv, sealed.ciphertext).run();
        return reply(201, { id });
      } catch { return reply(500, { error: 'registration failed' }); }
    }
    if (request.method === 'POST' && url.pathname === '/admin/test-notification') {
      if (env.ALLOW_TEST_PUSH !== 'YES' || !/^[A-Za-z0-9_-]{1,64}$/.test(env.HUAWEI_PROJECT_ID || '') ||
          typeof env.HUAWEI_TEST_JWT !== 'string' || !env.HUAWEI_TEST_JWT) {
        return reply(503, { error: 'test push not configured' });
      }
      let input;
      try { input = await readBody(request); } catch { return reply(400, { error: 'invalid request' }); }
      if (!input || typeof input.id !== 'string' || !/^[0-9a-f-]{36}$/i.test(input.id) ||
          typeof input.title !== 'string' || !input.title || input.title.length > 100 ||
          typeof input.body !== 'string' || !input.body || input.body.length > 500 ||
          !['IM', 'VOIP', 'TRAVEL', 'HEALTH', 'WORK', 'MARKETING'].includes(input.category)) {
        return reply(400, { error: 'invalid request' });
      }
      try {
        const record = await env.DB.prepare('SELECT token_iv, token_ciphertext FROM devices WHERE id = ?')
          .bind(input.id).first();
        if (!record) return reply(404, { error: 'device not found' });
        const token = await decryptToken(record, env.TOKEN_ENCRYPTION_KEY);
        const response = await fetch(`https://push-api.cloud.huawei.com/v3/${env.HUAWEI_PROJECT_ID}/messages:send`, {
          method: 'POST', headers: { 'Content-Type': 'application/json', 'push-type': '0',
            Authorization: `Bearer ${env.HUAWEI_TEST_JWT}` },
          body: JSON.stringify({ payload: { notification: { category: input.category, title: input.title,
            body: input.body, clickAction: { actionType: 0 }, foregroundShow: true } },
            target: { token: [token] }, pushOptions: { testMessage: true, ttl: 3600 } }),
        });
        const data = await response.json();
        if (!response.ok || data.code !== '80000000') return reply(502, { error: 'Huawei did not accept request' });
        return reply(200, { status: 'accepted', delivery: 'unconfirmed' });
      } catch { return reply(502, { error: 'test push failed' }); }
    }
    return reply(404, { error: 'not found' });
  }
};
