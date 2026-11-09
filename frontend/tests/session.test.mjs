import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';
import { authenticatedFetch, isLoggedIn, setTokens } from '../src/api/client.ts';

const storage = new Map();
globalThis.sessionStorage = {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value),
  removeItem: (key) => storage.delete(key),
};
globalThis.window = new EventTarget();
beforeEach(() => { storage.clear(); setTokens(null, null); });

const response = (status, body = {}) => new Response(JSON.stringify(body), { status });

test('concurrent page requests rotate a refresh token once', async () => {
  setTokens(null, 'initial-refresh');
  let refreshes = 0;
  globalThis.fetch = async (url, init) => {
    if (url.endsWith('/auth/token/refresh')) {
      refreshes += 1;
      await new Promise((resolve) => setTimeout(resolve, 10));
      return response(200, { access: 'new-access', refresh: 'rotated-refresh' });
    }
    assert.equal(init.headers.get('Authorization'), 'Bearer new-access');
    return response(200);
  };
  const results = await Promise.all([
    authenticatedFetch('/evaluations'), authenticatedFetch('/workspaces/available'),
  ]);
  assert.deepEqual(results.map((item) => item.status), [200, 200]);
  assert.equal(refreshes, 1);
  assert.equal(sessionStorage.getItem('refresh'), 'rotated-refresh');
});

test('an in-flight refresh cannot restore a signed-out session', async () => {
  setTokens(null, 'initial-refresh');
  let release;
  let started;
  const ready = new Promise((resolve) => { started = resolve; });
  globalThis.fetch = async (url) => {
    if (url.endsWith('/auth/token/refresh')) {
      started();
      return new Promise((resolve) => { release = () => resolve(response(200, {
        access: 'stale-access', refresh: 'stale-refresh',
      })); });
    }
    return response(401);
  };
  const pending = authenticatedFetch('/evaluations');
  await ready;
  setTokens(null, null);
  release();
  await pending;
  assert.equal(isLoggedIn(), false);
  assert.equal(sessionStorage.getItem('refresh'), null);
});

test('expired refresh ends the session and returns the unauthorized response', async () => {
  setTokens(null, 'expired-refresh');
  let ended = 0;
  const listener = () => { ended += 1; };
  window.addEventListener('session-ended', listener);
  globalThis.fetch = async () => response(401);
  const result = await authenticatedFetch('/evaluations');
  assert.equal(result.status, 401);
  assert.equal(isLoggedIn(), false);
  assert.ok(ended >= 1);
  window.removeEventListener('session-ended', listener);
});
