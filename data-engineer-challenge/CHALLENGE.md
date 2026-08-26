# Take-Home Test: Data Engineer

## The problem

We move data out of an operational **SQL Server** database into **BigQuery**. Three things hurt today:

1. **Transfer cost.** We copy the whole database every day to detect a change rate of about 1%.
2. **Bad operational data.** Duplicate customer records, scratch tables nobody owns, history kept forever.
3. **No trust.** Nothing tells us whether the warehouse is complete and correct. We find gaps when a number looks wrong on a dashboard.

Build a small local version of this and solve as much of it as you can in working code.

## Scope

**Expected effort: 4–8 hours. You are not expected to implement everything.**

Choose the problems where you can show the most, and solve those well. We would rather see one part done properly, with the reasoning behind it, than three parts half-finished. What you deliberately skipped — and why — is part of the answer, not a gap in it.

The quality of your decisions matters more than the number of features.

---

## Environment

Everything should run locally with **`docker compose up`** plus at most one extra command. No cloud credentials, no access to our systems, synthetic data only.

| Part | What we expect |
|---|---|
| Source database | Any relational database. **SQL Server is preferred** because it matches our environment; if you pick another, briefly say what you traded off. |
| Warehouse | Any local stand-in — DuckDB, PostgreSQL, a BigQuery emulator, your choice. |
| Pipeline | Any language you are fast in. |

We are evaluating data engineering, not database administration.

### What to seed

Keep the volume small — enough to measure something, not enough to slow down a laptop.

**Source database**, shaped roughly like ours:

- `Customers` — with duplicates of the same person, a few test accounts (`test@fundo.com` and similar), and some malformed phones and emails
- `Advances` — referencing customers, with a status marking one as *funded* or *paid off*
- `Transactions` — the large table, mostly historical, rarely changed after insert
- `Cards` — payment cards belonging to a customer
- one append-only history/version table
- one unused scratch table
- at least one bad schema choice, such as an identifier stored as unbounded text

At least one duplicate group should contain a customer with a funded or paid-off advance. That is the interesting case.

---

## What to solve

### 1. Move only what changed

Load the source into the warehouse incrementally rather than by full copy. It should handle:

- initial load, then incremental
- inserts, updates, and **deletes**
- being run twice with the same result
- recovering from a failure mid-run

Not every table deserves the same strategy. Use more than one, and say why.

### 2. Resolve duplicate customers

Decide which record survives, merge the rest, and stop the same duplicate from being created again.

What matters more than the merge code: **some fields prove identity, others only suggest a possible match.** Treating the second kind as the first merges people who are not the same person. Say which fields you put in each category, and why.

Four rules from the business:

- **A customer with a funded or paid-off advance is untouchable.** It survives and never loses a record that belongs to it. If two customers in a group both have one, do not guess — say what you would do.
- **Test data is excluded, not merged.** Decide how you identify it, and be careful: the naive pattern catches real people. A surname can be "Testerman", and staff run genuine transactions from company addresses.
- **Malformed phones and emails** — find them, count them, decide what happens to them. Fixing, flagging, or leaving them alone are all defensible; say which you chose.
- **Cards belonging to a merged customer** have to end up somewhere. Decide where, and say what breaks if you get it wrong.

### 3. Prove the data is correct

Build checks that answer, without anyone reading code: **is the warehouse complete and correct right now?** Compare the source against the warehouse — completeness, gaps, and rows that should no longer be there.

Then break something on purpose and show the check failing.

---

## Deliverables

### The code

Scripts, a Makefile, SQL, migrations — whatever solves the problems you took on. It should run on our machine from a clean checkout.

### `README.md`

- How to run it: copy-paste commands, in order.
- What each command does and what output to expect.
- How to run the checks and reproduce the failing-check demo.

Screenshots or a short terminal recording are welcome but optional — we do not evaluate presentation.

### `SOLUTION.md`

Short — two or three pages. Written for an engineering lead who will read it before your code:

- **How you solved each problem you took on**, and which you skipped and why.
- What you **measured**, with numbers, versus what you **estimated**. Label which is which.
- Your per-table strategy and the trade-off behind it.
- Cost impact: what drives the bill today and what changes.
- Your identity rules: what proves identity, what only suggests it, and how you handled funded customers, test data, malformed contacts and cards.

Close with a short section on **how this would evolve into a production system**:

- Which tools you would choose, and why.
- What would be a one-time script versus something that runs permanently.
- What you would deliver first, and why that one.

A few paragraphs is enough.

Your submission will be reviewed by engineers.

---

## What we evaluate

- **It runs** from a clean checkout, following your own instructions.
- **Judgement** — did you measure before deciding? Changing your mind because the data disagreed with you is a good sign, not a bad one.
- **Reliability** — idempotency, deletes, replay, partial runs.
- **Simplicity** — the smallest thing that solves it. Over-engineering counts against you.
- **Clarity** — someone should be able to run and understand your work without you in the room.
- **Safety** — nothing destructive without a way back.

If something is missing, say so rather than rushing it. An honest gap costs less than a confident guess.

Send us the repository link when you are done.
