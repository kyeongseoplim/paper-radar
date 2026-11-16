// Tests for n8n/src/summarize_render.js (module 02) with a fake httpRequest (no network).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runNode } from '../n8n/harness.mjs';

const code = readFileSync(new URL('../n8n/src/summarize_render.js', import.meta.url), 'utf8');
const config = { GEMINI_API_KEY: 'k123', GEMINI_MODEL: 'gemini-2.5-flash', APP_URL: 'https://radar.example.app/' };

const paper = (i, extra = {}) => ({
  id: `W${i}`, title: `Paper ${i}`, date: '2026-11-10', authors: ['A One', 'B Two', 'C Three', 'D Four'],
  venue: 'IEEE Access', publisher: 'IEEE', type: 'article', cited: 0, link: `https://doi.org/x/${i}`, ...extra,
});

const okItem = (dataOver = {}) => ({
  user_id: 1, email: 'u@example.com', name: 'Kim', ok: true, new_ids: ['W1'], error: null,
  data: {
    version: 1, week: '2026-11-16', generated_at: '2026-11-16T07:00:00+09:00',
    keywords: ['O-RAN', 'MAC scheduler'], query_text: '(O-RAN) AND (MAC scheduler)',
    papers: { rows: [paper(1), paper(2)], total: 2, days: 7, widened_from: null, skipped_seen: 0 },
    author: { id: 'A1', name: 'Jane Doe', inst: 'KAIST', rows: [paper(3)], total: 1, days: 7 },
    trends: { keywords: [{ term: 'O-RAN', this_week: 5, avg4: 2.5, change: 2 },
                         { term: 'MAC scheduler', this_week: 1, avg4: 0, change: null }],
              new_topics: [{ keyword: 'xApp', count: 3 }] },
    summary: null, errors: {}, ...dataOver,
  },
});

const gemini = (text) => ({ candidates: [{ content: { parts: [{ text }] } }] });
const fakeHttp = (impl) => {
  const calls = [];
  return { calls, helpers: { httpRequest: async (opts) => { calls.push(opts); return impl(opts); } } };
};

test('ok item gets summary, markdown and email_html; request uses model + key header', async () => {
  const f = fakeHttp(() => gemini('Activity is up. Themes are scheduling.'));
  const [out] = await runNode(code, [okItem()], config, f.helpers);
  assert.equal(out.data.summary, 'Activity is up. Themes are scheduling.');
  assert.equal(typeof out.markdown, 'string');
  assert.equal(typeof out.email_html, 'string');
  assert.match(out.markdown, /Activity is up/);
  assert.match(out.markdown, /Paper 1/);
  assert.match(out.email_html, /Activity is up/);
  assert.equal(f.calls.length, 1);
  const req = f.calls[0];
  assert.equal(req.method, 'POST');
  assert.equal(req.url, 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent');
  assert.equal(req.headers['x-goog-api-key'], 'k123');
  assert.match(JSON.stringify(req.body), /Paper 1/);
});

test('multiple parts are joined', async () => {
  const f = fakeHttp(() => ({ candidates: [{ content: { parts: [{ text: 'One. ' }, { text: 'Two.' }] } }] }));
  const [out] = await runNode(code, [okItem()], config, f.helpers);
  assert.equal(out.data.summary, 'One. Two.');
});

test('Gemini throwing -> summary null, markdown/email still produced', async () => {
  const f = fakeHttp(() => { throw new Error('HTTP 500'); });
  const [out] = await runNode(code, [okItem()], config, f.helpers);
  assert.equal(out.data.summary, null);
  assert.match(out.markdown, /Paper 1/);
  assert.match(out.email_html, /Paper 1/);
});

test('no GEMINI_API_KEY -> no request, summary null', async () => {
  const f = fakeHttp(() => gemini('should not be used'));
  const [out] = await runNode(code, [okItem()], { ...config, GEMINI_API_KEY: '' }, f.helpers);
  assert.equal(f.calls.length, 0);
  assert.equal(out.data.summary, null);
  assert.ok(out.markdown && out.email_html);
});

test('ok:false items pass through untouched', async () => {
  const f = fakeHttp(() => gemini('x'));
  const bad = { user_id: 2, email: 'b@example.com', name: 'B', ok: false, data: null, new_ids: [], error: 'all sections failed' };
  const [out] = await runNode(code, [structuredClone(bad)], config, f.helpers);
  assert.deepEqual(out, bad);
  assert.equal(f.calls.length, 0);
});

test('HTML special characters are escaped in email_html', async () => {
  const f = fakeHttp(() => gemini('Summary <script>x</script> & more'));
  const item = okItem({ papers: { rows: [paper(1, { title: 'A <b>bold</b> & "quoted" title' })], total: 1, days: 7, widened_from: null, skipped_seen: 0 } });
  item.name = '<Kim>';
  const [out] = await runNode(code, [item], config, f.helpers);
  assert.ok(!out.email_html.includes('<b>bold</b>'));
  assert.ok(out.email_html.includes('A &lt;b&gt;bold&lt;/b&gt; &amp; &quot;quoted&quot; title'));
  assert.ok(!out.email_html.includes('<script>'));
  assert.ok(out.email_html.includes('&lt;Kim&gt;'));
});

test('email contains the APP_URL/?page=me link (trailing slash handled)', async () => {
  const f = fakeHttp(() => gemini('ok'));
  const [out] = await runNode(code, [okItem()], config, f.helpers);
  assert.ok(out.email_html.includes('href="https://radar.example.app/?page=me"'));
});

test('email shows top 5 papers and top 3 author papers', async () => {
  const f = fakeHttp(() => gemini('ok'));
  const rows = Array.from({ length: 8 }, (_, i) => paper(i + 10));
  const arows = Array.from({ length: 5 }, (_, i) => paper(i + 30));
  const item = okItem({ papers: { rows, total: 8, days: 7, widened_from: null, skipped_seen: 0 },
                        author: { id: 'A1', name: 'Jane', inst: 'X', rows: arows, total: 5, days: 7 } });
  const [out] = await runNode(code, [item], config, f.helpers);
  assert.ok(out.email_html.includes('Paper 14') && !out.email_html.includes('Paper 15'));
  assert.ok(out.email_html.includes('Paper 32') && !out.email_html.includes('Paper 33'));
  // prompt has at most 15 titles
  const prompt = f.calls[0].body.contents[0].parts[0].text;
  assert.equal((prompt.match(/^- Paper/gm) || []).length, 13);
});

test('papers/author/trends null do not crash; no papers -> no Gemini call', async () => {
  const f = fakeHttp(() => gemini('x'));
  const [out] = await runNode(code, [okItem({ papers: null, author: null, trends: null })], config, f.helpers);
  assert.equal(f.calls.length, 0);
  assert.equal(out.data.summary, null);
  assert.match(out.markdown, /2026-11-16/);
  assert.ok(out.email_html.includes('?page=me'));
});

test('trend table rendered with change and "new" for null change', async () => {
  const f = fakeHttp(() => gemini('x'));
  const [out] = await runNode(code, [okItem()], config, f.helpers);
  assert.match(out.markdown, /\| O-RAN \| 5 \| 2.5 \| ×2.0 \|/);
  assert.match(out.markdown, /\| MAC scheduler \| 1 \| 0.0 \| new \|/);
  assert.ok(out.email_html.includes('O-RAN'));
});
