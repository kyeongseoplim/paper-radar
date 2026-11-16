// Run n8n Code-node files outside n8n (dev/testing only). Mimics the parts of the n8n API the nodes use:
// $input.all(), $('Config').first().json and this.helpers.httpRequest.
//
//   node n8n/harness.mjs n8n/src/build_reports.js n8n/src/summarize_render.js < input.json > items.json
//
// stdin: {"config": {...Config node values}, "items": [...input rows]}. stdout: JSON array of the last node's items' json.
import { readFileSync } from 'node:fs';

export async function httpRequest({ method = 'GET', url, qs, body, headers = {}, timeout = 20000 }) {
  const u = new URL(url);
  for (const [k, v] of Object.entries(qs || {})) if (v !== undefined) u.searchParams.set(k, v);
  const r = await fetch(u, {
    method, signal: AbortSignal.timeout(timeout),
    headers: body ? { 'content-type': 'application/json', ...headers } : headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  if (!r.ok) {
    const e = new Error(`HTTP ${r.status}: ${text.slice(0, 200)}`);
    e.httpCode = String(r.status);
    throw e;
  }
  return JSON.parse(text);
}

// Run one Code-node body. `items` are plain json objects; returns plain json objects.
export async function runNode(code, items, config, helpers = { httpRequest }) {
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  const $input = { all: () => items.map((json) => ({ json })) };
  const $ = (name) => {
    if (name !== 'Config') throw new Error(`harness only knows the Config node, not ${name}`);
    return { first: () => ({ json: config }) };
  };
  const out = await new AsyncFunction('$input', '$', code).call({ helpers }, $input, $);
  return out.map((i) => i.json);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  let { config, items } = JSON.parse(readFileSync(0, 'utf8'));
  for (const f of process.argv.slice(2)) items = await runNode(readFileSync(f, 'utf8'), items, config);
  process.stdout.write(JSON.stringify(items));
}
