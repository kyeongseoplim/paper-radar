-- This week's reports not emailed yet, for users who have email turned on.
SELECT r.id, r.week_start::text AS week_start, r.email_html, u.email, u.name
FROM reports r JOIN users u ON u.id = r.user_id
WHERE r.emailed_at IS NULL AND u.email_enabled
  AND r.week_start = date_trunc('week', now() AT TIME ZONE 'Asia/Seoul')::date
ORDER BY r.id;
