-- Save every successful report (a report already emailed keeps its emailed_at), remember the shown papers,
-- and close the run log. @items@ = JSON array of "Summarize + render" items, @run_id@ = id from start_run.sql.
WITH input AS (
    SELECT * FROM jsonb_to_recordset(@items@::jsonb)
        AS x(user_id bigint, ok boolean, data jsonb, new_ids jsonb, markdown text, email_html text, error text)
), saved AS (
    INSERT INTO reports (user_id, week_start, run_id, data, markdown, email_html)
    SELECT user_id, (data->>'week')::date, @run_id@, data, markdown, email_html FROM input WHERE ok
    ON CONFLICT (user_id, week_start) DO UPDATE SET
        run_id = EXCLUDED.run_id, data = EXCLUDED.data, markdown = EXCLUDED.markdown,
        email_html = EXCLUDED.email_html, updated_at = now()
    RETURNING user_id
), seen AS (
    INSERT INTO seen_papers (user_id, work_id, first_seen_week)
    SELECT i.user_id, w.id, (i.data->>'week')::date
    FROM input i, jsonb_array_elements_text(i.new_ids) AS w(id)
    WHERE i.ok
    ON CONFLICT DO NOTHING
), counts AS (
    SELECT (SELECT count(*) FROM saved) AS ok_n,
           (SELECT count(*) FROM input WHERE NOT ok) AS failed_n,
           (SELECT string_agg('user ' || user_id || ': ' || error, E'\n') FROM input WHERE NOT ok) AS errors
)
UPDATE runs SET finished_at = now(), users_ok = c.ok_n, users_failed = c.failed_n, error = c.errors,
       status = CASE WHEN c.failed_n = 0 THEN 'success' WHEN c.ok_n > 0 THEN 'partial' ELSE 'failed' END
FROM counts c
WHERE runs.id = @run_id@
RETURNING runs.*;
