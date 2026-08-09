# Take-Home Test: Full-Stack Engineer (.NET + Next.js)

## Objective

Build a small **loan application flow** — a simplified version of our real product.

A user fills a form, a rule engine decides if the application is approved or denied, approved applications are saved in our database, and a background event sends the same data to an external service over HTTP.

We care about **simplicity and design**. Over-engineering is a negative point.

---

## Stack (required)

| Part | Technology |
|---|---|
| Backend | .NET (C#) |
| Frontend | Next.js |
| External service | A mock you build (json-server, a small Node/.NET app, whatever you prefer) |

Database is your choice (SQL Server, PostgreSQL, SQLite), as long as it supports real transactions — the EF Core in-memory provider does not, so it is not an option here. Everything else — UI library, styling, messaging, containers — is up to you.

---

## The Flow

### 1. Application form (Next.js)

Collect:

- First name
- Last name
- Address (must include **state**)
- Company name
- Requested amount
- SSN

Design the pages and the UX the way you think is best.

### 2. Decision — must run through a rule engine

The decision logic must live in a **rule engine on the backend**, not scattered inside a controller or a component. Adding a new rule should not require changing existing ones.

Deny rules:

1. **State is `NY`** → deny.
2. **SSN is on a blacklist** → deny.

Denied users are redirected to a **denied page**. Any denial reason handling is your call.

If no deny rule matches, the application is approved and continues.

### 3. Persistence

On approval, create two records:

- **Customer** — the personal data from the form.
- **Application** — `id`, `requestedAmount`, `customerId`.

**This must be transactional.** Saving the customer, saving the application, and publishing the event are one unit of work: if any of them fails, roll everything back — no half-saved customer, no orphan application, and no event published. The same applies to the returning-customer path (updates instead of inserts).

### 4. Returning customer

While checking the SSN, if the customer **already exists** in the database:

- **Update** the existing customer record with the new data from the form — do not create a second customer.
- **Update** the existing application (for example, the requested amount) — do not create a second application.
- The background event must **update** the external service, not create a new record there.

In short: same SSN means one customer and one application in the database, updated with the latest submission.

### 5. Background event → external service

After both records are saved, publish an **event processed in the background** (not inside the HTTP request that answers the form). The handler sends the customer and application to an **external service over HTTP**.

- New customer → create in the external service.
- Returning customer → update in the external service.

The external service is a **mock**: it receives the payload and returns `200`. Build it however you like. Design the contract (endpoints, payload, retries or not) the way you consider best — and explain the choice.

---

## What We Evaluate

1. **Simplicity** — the smallest solution that solves the problem. No layers, patterns, or abstractions that nothing needs.
2. **Design** — clean architecture: dependencies point inward, business rules live in the domain/application layer, the controller is thin, infrastructure (HTTP client, DB, messaging) is replaceable.
3. **UI/UX** — clear, functional, and pleasant. It does not need to be beautiful, it needs to be thought through.
4. **Tests** — cover what matters: the rule engine, the returning-customer path, and the endpoint. Not 100% coverage.
5. **Documentation** — see below.

> Your code will be reviewed by **Claude Code using Fundo's internal review skills**, which check clean architecture, DDD, SOLID and naming. Write the documentation so a reviewer can validate your decisions without asking you.

---

## Documentation Required

In your repository, include:

**`README.md`**
- How to run everything locally (backend, frontend, mock service, database) — copy-paste commands.
- How to run the tests.
- Test data: which SSNs are blacklisted, what to type to get approved, denied, or returning-customer.

**`ARCHITECTURE.md`** (or a section in the README)
- Project structure and what each layer/folder is responsible for.
- How the rule engine works and how to add a new rule.
- How the background event works and how the external service is called.
- How the transaction is handled: what happens if the database or the event publishing fails.
- Trade-offs: what you chose to leave out, and why.

Keep the docs short. One good page beats five vague ones.

---

## Deliverables

- One repository with the backend, the frontend, and the mock external service.
- Everything running locally with clear instructions.
- **A short video of the app running**, with the link at the top of your `README.md`. Use Loom, Jam, Figma/FigJam recording, or any tool you prefer — just make sure the link is public.
- Send us the repository link when you are done.

The video should walk through the flows: approved application, denial by state `NY`, denial by blacklisted SSN, returning customer updating the existing records, and the external service receiving the data. A few minutes is enough.

Suggested effort: **around two days**. If something is missing, say so in the README instead of rushing it.

---

## Notes

- Authentication is **not** required.
- Seed data, Docker, CI, structured logging, etc. are welcome — only if they earn their place.
- Feel free to add anything you consider necessary. Just be ready to explain why it exists.
