// n8n Code node "Summarize + render" (mode: Run Once for All Items).
// Roadmap Step 7 (Gemini summary) + the Markdown and email versions of each report. See blueprint.md, module 02.
// Input/output: items from "Build reports"; adds data.summary (null if Gemini fails), markdown and email_html.

const cfg = $('Config').first().json;
const appUrl = (cfg.APP_URL || '').replace(/\/$/, '');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtChange = (k) => (k.change === null ? 'new' : `×${k.change.toFixed(1)}`);

const summarize = async (d) => {
  const papers = [...(d.papers ? d.papers.rows : []), ...(d.author ? d.author.rows : [])].slice(0, 15);
  if (!papers.length || !cfg.GEMINI_API_KEY) return null;
  const trends = (d.trends ? d.trends.keywords : [])
    .map((k) => `${k.term}: ${k.this_week} papers this week vs ${k.avg4.toFixed(1)} per week before`).join('\n');
  const prompt = `You write a weekly research briefing for a university lab.
Topics: ${d.keywords.join(', ')}.
New papers this week:
${papers.map((p) => `- ${p.title} (${p.venue || p.type}, ${p.date})`).join('\n')}
Weekly counts:
${trends}
Write 3-5 plain sentences (no markdown, no lists): the main themes of these papers and whether activity is up or down. Do not invent results that are not in the titles.`;
  try {
    const r = await this.helpers.httpRequest({
      method: 'POST', url: `https://generativelanguage.googleapis.com/v1beta/models/${cfg.GEMINI_MODEL}:generateContent`,
      headers: { 'x-goog-api-key': cfg.GEMINI_API_KEY }, body: { contents: [{ parts: [{ text: prompt }] }] },
      json: true, timeout: 60000,
    });
    return r.candidates[0].content.parts.map((p) => p.text).join('').trim() || null;
  } catch (e) {
    return null;   // the report is sent without a summary
  }
};

const markdown = (d) => {
  const lines = [`# Paper Radar · week of ${d.week}`, '', `Keywords: ${d.keywords.join(', ')}`, ''];
  if (d.summary) lines.push('## Summary', '', d.summary, '');
  const list = (rows) => rows.map((p) => `- [${p.title}](${p.link}) · ${p.venue || p.type} · ${p.date}`);
  if (d.papers && d.papers.rows.length) lines.push(`## New papers (last ${d.papers.days} days)`, '', ...list(d.papers.rows), '');
  if (d.author && d.author.rows.length) lines.push(`## From ${d.author.name}`, '', ...list(d.author.rows), '');
  if (d.trends) {
    lines.push('## This week vs 4-week average', '', '| Keyword | This week | 4-week avg | Change |', '|---|---|---|---|',
      ...d.trends.keywords.map((k) => `| ${k.term} | ${k.this_week} | ${k.avg4.toFixed(1)} | ${fmtChange(k)} |`), '');
    if (d.trends.new_topics.length) lines.push(`New topics: ${d.trends.new_topics.map((t) => t.keyword).join(', ')}`, '');
  }
  return lines.join('\n');
};

const emailHtml = (d, name) => {
  const h2 = (t) => `<h2 style="font-size:17px;color:#17212F;margin:26px 0 8px">${esc(t)}</h2>`;
  const paper = (p) => `<p style="margin:0 0 12px"><a href="${esc(p.link)}" style="color:#0F766E;font-weight:600;text-decoration:none">${esc(p.title)}</a><br>
    <span style="color:#64748B;font-size:13px">${esc(p.venue || p.type)} · ${esc(p.date)} · ${esc(p.authors.slice(0, 3).join(', '))}${p.authors.length > 3 ? ' et al.' : ''}</span></p>`;
  const parts = [`<p style="color:#334155">Hi ${esc(name || 'there')}, here is your Paper Radar for the week of <b>${esc(d.week)}</b>
    (${esc(d.keywords.join(', '))}).</p>`];
  if (d.summary) parts.push(`<div style="background:#F0FDFA;border-radius:10px;padding:14px 16px;color:#17212F">${esc(d.summary)}</div>`);
  if (d.papers && d.papers.rows.length) parts.push(h2(`New papers (last ${d.papers.days} days)`), ...d.papers.rows.slice(0, 5).map(paper));
  if (d.author && d.author.rows.length) parts.push(h2(`From ${d.author.name}`), ...d.author.rows.slice(0, 3).map(paper));
  if (d.trends) {
    const td = 'style="padding:4px 12px 4px 0;border-bottom:1px solid #E2E8F0"';
    parts.push(h2('This week vs 4-week average'), `<table style="border-collapse:collapse;font-size:14px;color:#334155">
      <tr><th align="left" ${td}>Keyword</th><th align="left" ${td}>This week</th><th align="left" ${td}>4-week avg</th><th align="left" ${td}>Change</th></tr>
      ${d.trends.keywords.map((k) => `<tr><td ${td}>${esc(k.term)}</td><td ${td}>${k.this_week}</td><td ${td}>${k.avg4.toFixed(1)}</td><td ${td}>${fmtChange(k)}</td></tr>`).join('')}
    </table>`);
  }
  parts.push(`<p style="margin:28px 0"><a href="${esc(appUrl)}/?page=me" style="background:#0F766E;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600">Open the full report</a></p>
    <p style="color:#94A3B8;font-size:12px">You get this email because you signed up for Paper Radar. Turn it off in Settings.</p>`);
  return `<div style="font-family:Arial,sans-serif;max-width:640px;margin:auto;line-height:1.5">
    <h1 style="font-size:22px;color:#17212F">📡 Paper Radar</h1>${parts.join('\n')}</div>`;
};

const out = [];
for (const item of $input.all()) {
  const it = item.json;
  if (it.ok) {
    it.data.summary = await summarize(it.data);
    it.markdown = markdown(it.data);
    it.email_html = emailHtml(it.data, it.name);
  }
  out.push({ json: it });
}
return out;
