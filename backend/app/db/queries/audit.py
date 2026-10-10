"""Read-only queries over the audit log. Nothing here writes; the log is append-only."""

from __future__ import annotations

from datetime import date

import asyncpg


async def page(
    pool: asyncpg.Pool,
    *,
    date_from: date | None,
    date_to: date | None,
    actor: str | None,
    action: str | None,
    before: int | None,
    limit: int,
) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        select id, created_at, actor, action, target_id, payload
        from audit_log
        where ($1::date is null or created_at >= $1::date)
          and ($2::date is null or created_at < ($2::date + 1))
          and ($3::text is null or actor = $3)
          and ($4::text is null or action = $4)
          and ($5::bigint is null or id < $5)
        order by id desc
        limit $6
        """,
        date_from,
        date_to,
        actor,
        action,
        before,
        limit,
    )
