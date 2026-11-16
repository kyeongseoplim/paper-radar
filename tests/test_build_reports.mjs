// Smoke test for n8n/src/build_reports.js with a fake OpenAlex (no network).
//   docker run -i --rm -v $PWD:/app -w /app node:22-bullseye node --test tests/test_build_reports.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runNode } from '../n8n/harness.mjs';

const CODE = readFileSync(new URL('../n8n/src/build_reports.js', import.meta.url), 'utf8');
const DAY = 86400000;
const today = new Date(new Date().toLocaleString('en-CA', { timeZone: 'Asia/Seoul' }).slice(0, 10) + 'T00:00:00Z');
const week = new Date(today.getTime() - ((today.getUTCDay() + 6) % 7) * DAY);
const WEEK = week.toISOString().slice(0, 10);

const work = (id, type = 'article') => ({
  id: `https://openalex.org/${id}`, display_name: `Paper ${id}`, publication_date: WEEK, type,
  authorships: [{ author: { display_name: 'Ann Lee' } }], cited_by_count: 1, doi: `https://doi.org/10.1/${id}`,
  primary_location: { source: { display_name: 'IEEE Access', host_organization_name: 'IEEE' } },
});
const ids = (p, n) => Array.from({ length: n }, (_, i) => `${p}${i + 1}`);

// Fake helpers.httpRequest: answers from the request's qs. `fail(qs)` -> throw for that request.
const fakeHelpers = (fail = () => false) => {
  const calls = [];
  const httpRequest = async ({ qs }) => {
    calls.push(qs);
    if (fail(qs)) throw new Error('boom');
    const from = /from_publication_date:([\d-]+)/.exec(qs.filter)[1];
    const back = Math.round((week - new Date(from + 'T00:00:00Z')) / DAY); // days before week_start
    if (qs.group_by === 'keywords.id') {
      const now = [{ key_display_name: 'Fresh Topic', count: 5 }, { key_display_name: 'Old Topic', count: 3 },
                   { key_display_name: 'Rare Topic', count: 1 }, { key_display_name: 'O-RAN fronthaul', count: 4 }];
      return { meta: { count: 99 }, group_by: back === 7 ? now : [{ key_display_name: 'Old Topic', count: 2 }] };
    }
    if (qs['per-page'] === 1) {
      const sched = qs.filter.includes('MAC scheduler');
      return { meta: { count: back === 7 ? 6 : sched ? 0 : 8 }, results: [] };
    }
    const n = { 7: 2, 30: 4, 90: 8 }[back];
    const list = qs.filter.includes('author.id:') ? ids('A', n) : ids('W', n);
    return { meta: { count: n * 10 }, results: [...list.map((i) => work(i)), work('D1', 'dataset')] };
  };
  return { helpers: { httpRequest }, calls };
};

const user = (over = {}) => ({
  id: 1, email: 'a@x.org', name: 'Ann', lab_name: 'Lab', keywords: ['O-RAN', 'MAC scheduler'],
  author: { openalex_id: 'A5000', display_name: 'Tom M', institution: 'NEU' }, seen: [], ...over,
});
const run = (users, fail) => { const f = fakeHelpers(fail); return runNode(CODE, users, { OPENALEX_API_KEY: 'k' }, f.helpers).then((out) => ({ out, calls: f.calls })); };
const PAPER_KEYS = ['id', 'title', 'date', 'authors', 'venue', 'publisher', 'type', 'cited', 'link'];

test('item and data shape, widening 7->30, trends, new topics', async () => {
  const { out, calls } = await run([user()]);
  assert.equal(out.length, 1);
  const it = out[0];
  assert.deepEqual(Object.keys(it).sort(), ['data', 'email', 'error', 'name', 'new_ids', 'ok', 'user_id']);
  assert.equal(it.ok, true); assert.equal(it.error, null); assert.equal(it.user_id, 1);
  const d = it.data;
  assert.deepEqual(Object.keys(d).sort(), ['author', 'errors', 'generated_at', 'keywords', 'papers', 'query_text',
    'summary', 'trends', 'version', 'week'].sort());
  assert.equal(d.version, 1); assert.equal(d.week, WEEK); assert.equal(new Date(d.week).getUTCDay(), 1);
  assert.ok(!isNaN(Date.parse(d.generated_at))); assert.equal(d.summary, null); assert.deepEqual(d.errors, {});
  assert.equal(d.query_text, '(O-RAN OR Open RAN OR open radio access network) AND (MAC scheduler OR MAC scheduling)');
  // papers: 7d gives 2 (<3) -> widened to 30; dataset dropped by tidy
  assert.deepEqual(Object.keys(d.papers).sort(), ['days', 'rows', 'skipped_seen', 'total', 'widened_from']);
  assert.equal(d.papers.days, 30); assert.equal(d.papers.widened_from, 7); assert.equal(d.papers.total, 40);
  assert.deepEqual(d.papers.rows.map((r) => r.id), ids('W', 4));
  assert.deepEqual(Object.keys(d.papers.rows[0]).sort(), [...PAPER_KEYS].sort());
  assert.deepEqual(d.papers.rows[0].authors, ['Ann Lee']);
  // author: 1 paper in 7d is enough
  assert.equal(d.author.id, 'A5000'); assert.equal(d.author.name, 'Tom M'); assert.equal(d.author.inst, 'NEU');
  assert.equal(d.author.days, 7); assert.deepEqual(d.author.rows.map((r) => r.id), ids('A', 2));
  // trends
  assert.deepEqual(d.trends.keywords, [
    { term: 'O-RAN', this_week: 6, avg4: 2, change: 3 },
    { term: 'MAC scheduler', this_week: 6, avg4: 0, change: null },
  ]);
  assert.deepEqual(d.trends.new_topics, [{ keyword: 'Fresh Topic', count: 5 }]);
  assert.deepEqual(it.new_ids, [...ids('W', 4), ...ids('A', 2)]);
  // request filters
  const list = calls.find((q) => q.sort);
  assert.match(list.filter, /title_and_abstract\.search:"O-RAN"\|"Open RAN"\|"open radio access network"/);
  assert.match(list.filter, /type:article\|preprint\|conference-paper\|review/);
  assert.equal(list['per-page'], 50); assert.equal(list.api_key, 'k');
});

test('seen ids are skipped and window widens to 90', async () => {
  const { out } = await run([user({ seen: ['W1', 'W2', 'W3', 'A1'] })]);
  const p = out[0].data.papers;
  assert.equal(p.days, 90); assert.equal(p.widened_from, 7); assert.equal(p.skipped_seen, 3);
  assert.deepEqual(p.rows.map((r) => r.id), ['W4', 'W5', 'W6', 'W7', 'W8']);
  assert.deepEqual(out[0].data.author.rows.map((r) => r.id), ['A2']);
  assert.ok(!out[0].new_ids.some((i) => ['W1', 'W2', 'W3', 'A1'].includes(i)));
});

test('user with no author', async () => {
  const { out, calls } = await run([user({ author: null })]);
  assert.equal(out[0].ok, true); assert.equal(out[0].data.author, null);
  assert.ok(!calls.some((q) => q.filter.includes('author.id:')));
});

test('one section failing goes to data.errors, ok stays true', async () => {
  const { out } = await run([user()], (qs) => qs.group_by === 'keywords.id');
  assert.equal(out[0].ok, true);
  assert.equal(out[0].data.trends, null);
  assert.deepEqual(out[0].data.errors, { trends: 'boom' });
  assert.ok(out[0].data.papers && out[0].data.author);
});

test('all sections failing -> ok:false with error; other users unaffected', async () => {
  const { out } = await run([user({ id: 1 }), user({ id: 2, author: null, email: 'b@x.org' })],
    () => true);
  for (const it of out) {
    assert.equal(it.ok, false); assert.equal(it.data, null); assert.deepEqual(it.new_ids, []);
    assert.match(it.error, /boom/);
  }
  assert.deepEqual(out.map((i) => i.user_id), [1, 2]);
});
