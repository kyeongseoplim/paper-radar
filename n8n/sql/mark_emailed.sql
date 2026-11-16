-- Mark the sent reports. In test mode (@test_mode@ = true) nothing is marked, so tests can be repeated.
UPDATE reports SET emailed_at = now()
WHERE id = ANY(@ids@::bigint[]) AND emailed_at IS NULL AND NOT @test_mode@;
