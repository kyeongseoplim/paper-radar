-- Open a run-log row. @trigger@ = 'schedule' | 'manual'.
INSERT INTO runs (trigger) VALUES (@trigger@) RETURNING id;
