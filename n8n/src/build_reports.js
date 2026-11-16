// n8n Code node "Build reports" (mode: Run Once for All Items).
// Roadmap Step 5 (weekly job) + Step 6 (weekly keyword trends). See blueprint.md, module 01.
// Input items: rows of n8n/sql/load_users.sql. Output: one item per user {user_id, email, name, ok, data, new_ids, error}.
// The search rules (synonyms, AND across keywords, tidy) are copied from core/query.py and core/openalex.py.

const cfg = $('Config').first().json;
const BASE = 'https://api.openalex.org';
const WORK_TYPES = 'article|preprint|conference-paper|review';
const SKIP_TYPES = new Set(['dataset', 'paratext', 'erratum', 'retraction', 'peer-review', 'other', 'supplementary-materials']);
const SELECT = 'id,display_name,publication_date,authorships,primary_location,doi,cited_by_count,type';
const PAPER_WINDOWS = [7, 30, 90];
const AUTHOR_WINDOWS = [7, 30];
const MIN_PAPERS = 3;
const N_PAPERS = 10;
const SYNONYMS = [
  ['O-RAN', 'Open RAN', 'open radio access network'],
  ['MAC scheduler', 'MAC scheduling'],
  ['scheduler', 'scheduling'],
  ['AI-RAN', 'AI RAN'],
  ['RAN intelligent controller', 'near-RT RIC'],
  ['traffic prediction', 'traffic forecasting'],
  ['cellular traffic prediction', 'cellular traffic forecasting', 'mobile traffic prediction', 'mobile traffic forecasting'],
  ['network slicing', 'RAN slicing'],
  ['digital twin', 'digital twins'],
  ['large language model', 'LLM'],
];

// ---------- dates (report weeks start on Monday, Korea time) ----------
const iso = (d) => d.toISOString().slice(0, 10);
const addDays = (d, n) => new Date(d.getTime() + n * 86400000);
const today = new Date(new Date().toLocaleString('en-CA', { timeZone: 'Asia/Seoul' }).slice(0, 10) + 'T00:00:00Z');
const week = addDays(today, -((today.getUTCDay() + 6) % 7));   // Monday

// ---------- OpenAlex ----------
let last = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const get = async (path, qs) => {
  for (let attempt = 0; ; attempt++) {
    const wait = 200 - (Date.now() - last);
    if (wait > 0) await sleep(wait);
    last = Date.now();
    try {
      return await this.helpers.httpRequest({
        url: `${BASE}/${path}`, qs: { ...qs, api_key: cfg.OPENALEX_API_KEY || undefined }, json: true, timeout: 20000,
      });
    } catch (e) {
      const status = e.httpCode || e.statusCode || (e.response && e.response.status);
      if (attempt === 0 && String(status) === '429') { await sleep(5000); continue; }
      throw e;
    }
  }
};

// ---------- search rules (same as core/query.py) ----------
const key = (s) => { const k = s.toLowerCase().replace(/[^a-z0-9]/g, ''); return k.length > 3 && k.endsWith('s') ? k.slice(0, -1) : k; };
const SYN_INDEX = {};
for (const g of SYNONYMS) for (const t of g) SYN_INDEX[key(t)] = g;
const expand = (term) => [term, ...(SYN_INDEX[key(term)] || []).filter((s) => key(s) !== key(term))];
const kwFilter = (group) => 'title_and_abstract.search:' + group.map((t) => `"${t}"`).join('|');
const between = (from, to) => [`from_publication_date:${iso(from)}`, `to_publication_date:${iso(to)}`];
const describe = (groups) => groups.map((g) => (g.length > 1 ? `(${g.join(' OR ')})` : g[0])).join(' AND ');

// ---------- result cleaning (same as core/openalex.py) ----------
const clean = (s) => (s || '').replace(/‐|‑/g, '-').trim();
const parseWork = (w) => {
  const loc = w.primary_location || {};
  const src = loc.source || {};
  return {
    id: w.id.split('/').pop(), title: clean(w.display_name) || '(untitled)', date: w.publication_date || '',
    authors: (w.authorships || []).map((a) => clean(a.author.display_name)),
    venue: clean(src.display_name), publisher: clean(src.host_organization_name), type: w.type || '',
    cited: w.cited_by_count || 0, link: w.doi || loc.landing_page_url || w.id,
  };
};
const tidy = (rows) => {
  const zenodo = (r) => r.venue.toLowerCase().includes('zenodo') || r.link.toLowerCase().includes('zenodo');
  const seen = new Set();
  const out = rows.filter((r) => !SKIP_TYPES.has(r.type) && !zenodo(r)).filter((r) => {
    const k = r.title.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (!k || seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return out.sort((a, b) => b.date.localeCompare(a.date));
};

// Newest unseen works for `filters`, widening the window until at least `minRows` are left.
const newest = async (filters, windows, minRows, seen) => {
  let first = null;
  for (const days of windows) {
    const data = await get('works', {
      filter: [...filters, ...between(addDays(week, -days), today)].join(','),
      sort: 'publication_date:desc', 'per-page': 50, select: SELECT,
    });
    const all = tidy(data.results.map(parseWork));
    const rows = all.filter((r) => !seen.has(r.id));
    if (first === null) first = days;
    if (rows.length >= minRows || days === windows[windows.length - 1]) {
      return { rows: rows.slice(0, N_PAPERS), total: data.meta.count, days,
               widened_from: days !== first ? first : null, skipped_seen: all.length - rows.length };
    }
  }
};

const count = async (filters, from, to) =>
  (await get('works', { filter: [...filters, ...between(from, to)].join(','), 'per-page': 1, select: 'id' })).meta.count;

const topics = async (filters, from, to) => {
  const data = await get('works', { filter: [...filters, ...between(from, to)].join(','), group_by: 'keywords.id' });
  return Object.fromEntries(data.group_by.map((g) => [clean(g.key_display_name), g.count]));
};

const buildReport = async (user) => {
  const groups = user.keywords.map(expand);
  const seen = new Set(user.seen || []);
  const typeF = `type:${WORK_TYPES}`;
  const data = {
    version: 1, week: iso(week), generated_at: new Date().toISOString(), keywords: user.keywords,
    query_text: describe(groups), papers: null, author: null, trends: null, summary: null, errors: {},
  };
  const sections = 2 + (user.author ? 1 : 0);

  try {
    data.papers = await newest([...groups.map(kwFilter), typeF], PAPER_WINDOWS, MIN_PAPERS, seen);
  } catch (e) { data.errors.papers = e.message; }

  if (user.author) {
    const a = user.author;
    try {
      const r = await newest([`author.id:${a.openalex_id}`], AUTHOR_WINDOWS, 1, seen);
      data.author = { id: a.openalex_id, name: a.display_name, inst: a.institution, ...r };
    } catch (e) { data.errors.author = e.message; }
  }

  try {
    // this week = the 7 days before the report Monday; the 4 weeks before that are the baseline
    const [t0, t1, p0, p1] = [addDays(week, -7), addDays(week, -1), addDays(week, -35), addDays(week, -8)];
    const keywords = [];
    for (const [i, g] of groups.entries()) {
      const thisWeek = await count([kwFilter(g), typeF], t0, t1);
      const avg4 = (await count([kwFilter(g), typeF], p0, p1)) / 4;
      keywords.push({ term: user.keywords[i], this_week: thisWeek, avg4, change: avg4 ? thisWeek / avg4 : null });
    }
    const field = [kwFilter([...new Set(groups.flat())]), typeF];
    const now = await topics(field, t0, t1);
    const before = await topics(field, p0, p1);
    const stops = groups.flat().map(key);
    const new_topics = Object.entries(now)
      .filter(([k, n]) => n >= 2 && !before[k] && !stops.some((s) => key(k).includes(s)))
      .sort((a, b) => b[1] - a[1]).slice(0, 6).map(([keyword, n]) => ({ keyword, count: n }));
    data.trends = { keywords, new_topics };
  } catch (e) { data.errors.trends = e.message; }

  if (Object.keys(data.errors).length === sections) throw new Error(Object.values(data.errors).join(' | '));
  const new_ids = [...(data.papers ? data.papers.rows : []), ...(data.author ? data.author.rows : [])].map((r) => r.id);
  return { data, new_ids };
};

const out = [];
for (const item of $input.all()) {
  const u = item.json;
  const base = { user_id: u.id, email: u.email, name: u.name };
  try {
    out.push({ json: { ...base, ok: true, ...(await buildReport(u)), error: null } });
  } catch (e) {
    out.push({ json: { ...base, ok: false, data: null, new_ids: [], error: e.message } });
  }
}
return out;
