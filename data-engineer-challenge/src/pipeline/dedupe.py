"""Customer duplicate resolution and FK remapping."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .config import TEST_EMAIL_DOMAINS
from .db import warehouse_conn

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
# E.164-ish or plain 10–15 digits
PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")

FUNDED_STATUSES = frozenset({"funded", "paid_off"})


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    return email.strip().lower()


def is_valid_email(email: str | None) -> bool:
    if not email:
        return False
    return bool(EMAIL_RE.match(email.strip()))


def is_valid_phone(phone: str | None) -> bool:
    if not phone:
        return False
    compact = re.sub(r"[\s\-()]", "", phone.strip())
    return bool(PHONE_RE.match(compact))


def is_test_customer(email: str | None, is_test: bool) -> bool:
    """Identify test data without surname substring traps (Testerman)."""
    if is_test:
        return True
    norm = normalize_email(email)
    if not norm or "@" not in norm:
        return False
    domain = norm.rsplit("@", 1)[-1]
    # fundo.com addresses used for QA — staff personal mail is not on this domain in seed
    return domain in TEST_EMAIL_DOMAINS


@dataclass
class CustomerRow:
    id: int
    external_id: str | None
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    address: str | None
    is_test: bool


def _load_customers(con) -> list[CustomerRow]:
    rows = con.execute(
        """
        SELECT id, external_id, first_name, last_name, email, phone, address, is_test
        FROM raw.customers
        WHERE deleted_at IS NULL
        """
    ).fetchall()
    return [CustomerRow(*r) for r in rows]


def _funded_customer_ids(con) -> set[int]:
    rows = con.execute(
        """
        SELECT DISTINCT customer_id
        FROM raw.advances
        WHERE deleted_at IS NULL AND status IN ('funded', 'paid_off')
        """
    ).fetchall()
    return {r[0] for r in rows}


def _identity_groups(customers: list[CustomerRow]) -> dict[str, list[CustomerRow]]:
    """Group only on fields that prove identity (valid email or external_id)."""
    by_email: dict[str, list[CustomerRow]] = defaultdict(list)
    by_ext: dict[str, list[CustomerRow]] = defaultdict(list)

    for c in customers:
        if is_test_customer(c.email, c.is_test):
            continue
        if is_valid_email(c.email):
            by_email[normalize_email(c.email)].append(c)  # type: ignore[arg-type]
        if c.external_id and str(c.external_id).strip():
            by_ext[str(c.external_id).strip()].append(c)

    # Union-find style merge of overlapping email / external_id groups
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for group in list(by_email.values()) + list(by_ext.values()):
        if len(group) < 2:
            continue
        anchor = group[0].id
        for other in group[1:]:
            union(anchor, other.id)

    clusters: dict[int, list[CustomerRow]] = defaultdict(list)
    by_id = {c.id: c for c in customers if not is_test_customer(c.email, c.is_test)}
    for cid, c in by_id.items():
        root = find(cid) if cid in parent else cid
        # only include customers that participate in a multi-member cluster or alone
        clusters[root].append(c)

    # Re-key groups that actually need merge decisions (size > 1) plus singles
    result: dict[str, list[CustomerRow]] = {}
    for root, members in clusters.items():
        # Deduplicate members
        uniq = {m.id: m for m in members}
        result[f"cluster:{root}"] = list(uniq.values())
    return result


def _pick_survivor(
    members: list[CustomerRow], funded: set[int]
) -> tuple[CustomerRow | None, str | None]:
    funded_members = [m for m in members if m.id in funded]
    if len(funded_members) > 1:
        return None, "multiple_funded_or_paid_off"
    if len(funded_members) == 1:
        return funded_members[0], "funded_untouchable"
    # Prefer lowest id for stability when no funded member
    return sorted(members, key=lambda m: m.id)[0], "lowest_id"


def resolve_customers() -> dict[str, Any]:
    stats: dict[str, Any] = {
        "survivors": 0,
        "merged_away": 0,
        "excluded_test": 0,
        "conflicts": 0,
        "malformed_email": 0,
        "malformed_phone": 0,
    }

    with warehouse_conn() as con:
        customers = _load_customers(con)
        funded = _funded_customer_ids(con)

        test_ids = {
            c.id for c in customers if is_test_customer(c.email, c.is_test)
        }
        stats["excluded_test"] = len(test_ids)

        for c in customers:
            if c.id in test_ids:
                continue
            if not is_valid_email(c.email):
                stats["malformed_email"] += 1
            if not is_valid_phone(c.phone):
                stats["malformed_phone"] += 1

        groups = _identity_groups(customers)
        survivor_map: dict[int, tuple[int, str]] = {}
        conflicts: list[tuple[str, str, str]] = []

        for key, members in groups.items():
            if len(members) == 1:
                m = members[0]
                survivor_map[m.id] = (m.id, "singleton")
                continue
            survivor, reason = _pick_survivor(members, funded)
            if survivor is None:
                ids = ",".join(str(m.id) for m in sorted(members, key=lambda x: x.id))
                conflicts.append((key, ids, reason or "conflict"))
                # Map each to self — no merge
                for m in members:
                    survivor_map[m.id] = (m.id, "conflict_no_merge")
                continue
            for m in members:
                survivor_map[m.id] = (survivor.id, reason or "merged")

        # Ensure every non-test customer is mapped
        for c in customers:
            if c.id in test_ids:
                continue
            survivor_map.setdefault(c.id, (c.id, "singleton"))

        con.execute("DELETE FROM curated.merge_conflicts")
        con.execute("DELETE FROM curated.customer_survivor_map")
        con.execute("DELETE FROM curated.customers")
        con.execute("DELETE FROM curated.advances")
        con.execute("DELETE FROM curated.cards")
        con.execute("DELETE FROM curated.transactions")
        con.execute("DELETE FROM curated.customer_history")
        con.execute("DELETE FROM curated.contact_quality")

        for group_key, ids, reason in conflicts:
            con.execute(
                """
                INSERT INTO curated.merge_conflicts (group_key, customer_ids, reason)
                VALUES (?, ?, ?)
                """,
                [group_key, ids, reason],
            )
        stats["conflicts"] = len(conflicts)

        for src_id, (surv_id, reason) in survivor_map.items():
            con.execute(
                """
                INSERT INTO curated.customer_survivor_map
                    (source_customer_id, survivor_customer_id, reason)
                VALUES (?, ?, ?)
                """,
                [src_id, surv_id, reason],
            )

        # Build curated customers: one row per survivor
        survivors = {surv for surv, _ in survivor_map.values()}
        by_id = {c.id: c for c in customers}

        for surv_id in sorted(survivors):
            c = by_id[surv_id]
            merged_from = sorted(
                sid for sid, (s, _) in survivor_map.items() if s == surv_id and sid != surv_id
            )
            con.execute(
                """
                INSERT INTO curated.customers
                    (id, external_id, first_name, last_name, email, phone, address,
                     email_valid, phone_valid, merged_from)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    c.id,
                    c.external_id,
                    c.first_name,
                    c.last_name,
                    c.email,
                    c.phone,
                    c.address,
                    is_valid_email(c.email),
                    is_valid_phone(c.phone),
                    ",".join(map(str, merged_from)) if merged_from else None,
                ],
            )
            stats["survivors"] += 1
            stats["merged_away"] += len(merged_from)

        # Remap FKs for advances / cards / transactions onto survivors; drop test customers
        def map_cid(cid: int) -> int | None:
            if cid in test_ids:
                return None
            if cid not in survivor_map:
                return None
            return survivor_map[cid][0]

        for row in con.execute(
            """
            SELECT id, customer_id, amount_cents, status
            FROM raw.advances WHERE deleted_at IS NULL
            """
        ).fetchall():
            new_cid = map_cid(row[1])
            if new_cid is None:
                continue
            con.execute(
                """
                INSERT INTO curated.advances (id, customer_id, amount_cents, status)
                VALUES (?, ?, ?, ?)
                """,
                [row[0], new_cid, row[2], row[3]],
            )

        for row in con.execute(
            """
            SELECT id, customer_id, last_four, brand
            FROM raw.cards WHERE deleted_at IS NULL
            """
        ).fetchall():
            new_cid = map_cid(row[1])
            if new_cid is None:
                continue
            con.execute(
                """
                INSERT INTO curated.cards (id, customer_id, last_four, brand)
                VALUES (?, ?, ?, ?)
                """,
                [row[0], new_cid, row[2], row[3]],
            )

        for row in con.execute(
            """
            SELECT id, customer_id, advance_id, amount_cents, txn_type, created_at
            FROM raw.transactions
            """
        ).fetchall():
            new_cid = map_cid(row[1])
            if new_cid is None:
                continue
            con.execute(
                """
                INSERT INTO curated.transactions
                    (id, customer_id, advance_id, amount_cents, txn_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [row[0], new_cid, row[2], row[3], row[4], row[5]],
            )

        for row in con.execute(
            """
            SELECT id, customer_id, change_type, payload, recorded_at
            FROM raw.customer_history
            """
        ).fetchall():
            new_cid = map_cid(row[1])
            # Keep history even if customer soft-deleted later; map when possible
            mapped = new_cid if new_cid is not None else row[1]
            con.execute(
                """
                INSERT INTO curated.customer_history
                    (id, customer_id, change_type, payload, recorded_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [row[0], mapped, row[2], row[3], row[4]],
            )

        con.execute(
            """
            INSERT INTO curated.contact_quality (metric, value) VALUES
                ('malformed_email_count', ?),
                ('malformed_phone_count', ?),
                ('excluded_test_customers', ?)
            """,
            [
                stats["malformed_email"],
                stats["malformed_phone"],
                stats["excluded_test"],
            ],
        )

    return stats


if __name__ == "__main__":
    import json

    print(json.dumps(resolve_customers(), indent=2))
