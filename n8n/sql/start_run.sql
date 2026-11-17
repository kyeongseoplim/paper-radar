-- Open a run-log row. @trigger@ = 'schedule' | 'manual' | 'webhook'.
INSERT INTO runs (trigger) VALUES (@trigger@) RETURNING id;
