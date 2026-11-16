-- Onboarded users with their keywords, followed author and the papers already shown to them in EARLIER weeks
-- (this week's are left out, so re-running the same week rebuilds the same report).
SELECT u.id, u.email, u.name, u.lab_name,
       coalesce((SELECT array_agg(k.term ORDER BY k.position) FROM keywords k WHERE k.user_id = u.id), '{}') AS keywords,
       (SELECT jsonb_build_object('openalex_id', a.openalex_id, 'display_name', a.display_name, 'institution', a.institution)
          FROM followed_authors a WHERE a.user_id = u.id ORDER BY a.confirmed_at DESC LIMIT 1) AS author,
       coalesce((SELECT array_agg(s.work_id) FROM seen_papers s
                  WHERE s.user_id = u.id
                    AND s.first_seen_week < date_trunc('week', now() AT TIME ZONE 'Asia/Seoul')::date), '{}') AS seen
FROM users u
WHERE u.onboarded_at IS NOT NULL
ORDER BY u.id;
