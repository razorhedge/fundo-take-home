-- Seed: small volume, includes interesting duplicate + funded case

INSERT INTO customers (id, external_id, first_name, last_name, email, phone, address, is_test, created_at, updated_at) VALUES
-- Duplicate group A: same person; id=1 has funded advance (untouchable survivor)
(1,  'EXT-1001', 'Jane', 'Doe',       'jane.doe@email.com',  '+15551110001', '100 Main St',  FALSE, '2024-01-01', '2024-06-01'),
(2,  'EXT-1001', 'Jane', 'Doe',       'jane.doe@email.com',  '555-111-0001', '100 Main Street', FALSE, '2024-02-01', '2024-06-02'),
-- Duplicate group B: soft-match name only (different emails) — must NOT auto-merge on name alone
(3,  'EXT-2001', 'Alex', 'Rivera',    'alex.r@email.com',    '+15552220002', '200 Oak Ave',  FALSE, '2024-01-15', '2024-05-01'),
(4,  'EXT-2002', 'Alex', 'Rivera',    'a.rivera@other.com',  '+15552220099', '200 Oak Avenue', FALSE, '2024-03-01', '2024-05-02'),
-- Real customer whose surname contains "test" — must NOT be treated as test data
(5,  'EXT-3001', 'Sam',  'Testerman', 'sam.testerman@email.com', '+15553330003', '300 Pine Rd', FALSE, '2024-01-20', '2024-04-01'),
-- Explicit test accounts (exclude, do not merge)
(6,  NULL,       'QA',   'Bot',       'test@fundo.com',      '+15550000000', '1 Test Lane', TRUE,  '2024-01-01', '2024-01-01'),
(7,  NULL,       'Load', 'Tester',    'loadtest@fundo.com',  'not-a-phone',  '1 Test Lane', TRUE,  '2024-01-02', '2024-01-02'),
-- Malformed contacts (flag + count; leave as-is)
(8,  'EXT-4001', 'Pat',  'Lee',       'pat.lee@@email..com', '555CALLME',    '400 Elm St',  FALSE, '2024-02-10', '2024-03-01'),
(9,  'EXT-4002', 'Chris','Nguyen',    NULL,                  '123',          '500 Cedar',   FALSE, '2024-02-11', '2024-03-02'),
-- Dual-funded conflict group (same email, both funded) — do not merge
(10, 'EXT-5001', 'Morgan','Blake',    'morgan.blake@email.com', '+15554440004', '600 Birch', FALSE, '2024-01-05', '2024-05-10'),
(11, 'EXT-5001', 'Morgan','Blake',    'morgan.blake@email.com', '+15554440004', '600 Birch St', FALSE, '2024-01-06', '2024-05-11'),
-- Soft-deleted customer (should not remain active in warehouse)
(12, 'EXT-6001', 'Gone', 'Person',    'gone@email.com',      '+15555550005', '700 Willow', FALSE, '2024-01-01', '2024-07-01');

UPDATE customers SET deleted_at = '2024-07-01', updated_at = '2024-07-01' WHERE id = 12;

INSERT INTO advances (id, customer_id, amount_cents, status, created_at, updated_at) VALUES
(1, 1,  50000,  'funded',   '2024-03-01', '2024-03-15'),
(2, 2,  25000,  'pending',  '2024-04-01', '2024-04-01'),
(3, 3,  10000,  'cancelled','2024-02-01', '2024-02-10'),
(4, 5,  75000,  'paid_off', '2024-01-25', '2024-06-01'),
(5, 8,  30000,  'pending',  '2024-03-01', '2024-03-01'),
(6, 10, 40000,  'funded',   '2024-02-01', '2024-02-20'),
(7, 11, 45000,  'funded',   '2024-02-05', '2024-02-25'),
(8, 6,  1000,   'pending',  '2024-01-03', '2024-01-03');

INSERT INTO cards (id, customer_id, last_four, brand, created_at, updated_at) VALUES
(1, 1,  '1111', 'visa',       '2024-01-10', '2024-01-10'),
(2, 2,  '2222', 'mastercard', '2024-02-10', '2024-02-10'),  -- belongs to duplicate; must move to survivor
(3, 3,  '3333', 'visa',       '2024-01-20', '2024-01-20'),
(4, 5,  '4444', 'amex',       '2024-01-22', '2024-01-22'),
(5, 8,  '5555', 'visa',       '2024-02-12', '2024-02-12'),
(6, 10, '6666', 'visa',       '2024-01-08', '2024-01-08'),
(7, 11, '7777', 'mastercard', '2024-01-09', '2024-01-09');

-- ~120 historical transactions (append-only)
INSERT INTO transactions (customer_id, advance_id, amount_cents, txn_type, created_at)
SELECT
    CASE (g % 5)
        WHEN 0 THEN 1
        WHEN 1 THEN 3
        WHEN 2 THEN 5
        WHEN 3 THEN 8
        ELSE 10
    END,
    CASE WHEN g % 7 = 0 THEN 1 ELSE NULL END,
    1000 + (g * 37) % 9000,
    CASE WHEN g % 3 = 0 THEN 'disbursement' WHEN g % 3 = 1 THEN 'repayment' ELSE 'fee' END,
    TIMESTAMPTZ '2024-01-01' + (g || ' hours')::INTERVAL
FROM generate_series(1, 120) AS g;

INSERT INTO customer_history (customer_id, change_type, payload, recorded_at) VALUES
(1,  'created', '{"source":"app"}'::jsonb, '2024-01-01'),
(1,  'updated', '{"field":"phone"}'::jsonb, '2024-06-01'),
(2,  'created', '{"source":"app"}'::jsonb, '2024-02-01'),
(5,  'created', '{"source":"app"}'::jsonb, '2024-01-20'),
(10, 'created', '{"source":"app"}'::jsonb, '2024-01-05'),
(11, 'created', '{"source":"app"}'::jsonb, '2024-01-06'),
(12, 'deleted', '{"reason":"gdpr"}'::jsonb, '2024-07-01');

INSERT INTO tmp_scratch_imports (id, junk) VALUES
(1, 'do not replicate'),
(2, 'orphan scratch');
