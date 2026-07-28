"""Shared Postgres core for Foundry apps — pool, tenant transaction, RLS helper.

Every app's db_pg.py builds on the same three pieces:

    from foundry_common.db import make_pool, make_tx, admin_connect, apply_rls

    _pool = make_pool("myapp")
    _tx = make_tx(_pool)                    # with _tx(owner) as cur: ...
    def admin_conn(): return admin_connect("myapp")
    # inside init(), after CREATE TABLEs:
    apply_rls(conn, ["table_a", "table_b"])  # FORCE RLS + isolation policy + grants

Tenant isolation is enforced by the database: app connections use the non-superuser
app_rls role, tenant tables carry FORCE ROW LEVEL SECURITY, and the policy exposes only
rows whose owner_user_id matches `app.current_owner` (set per transaction) or is NULL
(shared seed). DDL and cross-tenant admin use the foundry superuser, which bypasses RLS
by design.
"""
import os

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _dsn(dbname, admin=False):
    key = "DATABASE_URL_ADMIN" if admin else "DATABASE_URL"
    user = "foundry" if admin else "app_rls"
    return os.environ.get(key, f"postgresql://{user}@127.0.0.1:5433/{dbname}")


def make_pool(dbname, min_size=1, max_size=10):
    return ConnectionPool(_dsn(dbname), min_size=min_size, max_size=max_size,
                          open=True, kwargs={"autocommit": False})


def admin_connect(dbname):
    return psycopg.connect(_dsn(dbname, admin=True), row_factory=dict_row)


def make_tx(pool):
    """A transaction class scoped to a tenant: sets app.current_owner so RLS applies.

    `pool` may be a ConnectionPool OR a zero-arg callable returning the current pool.
    Prefer the callable form (`make_tx(lambda: _pool)`) in any app that runs Celery: under
    prefork, fork_safe() replaces the module's pool inside each worker child, and a _tx that
    captured the ORIGINAL pool object would keep using the closed one — which surfaces as the
    PoolTimeout / jobs-stuck-in-queued failure this library exists to prevent. Resolving the
    pool per transaction makes that rebinding actually take effect.
    """
    resolve = pool if callable(pool) else (lambda: pool)

    class _tx:
        def __init__(self, owner):
            self.owner = owner or ""

        def __enter__(self):
            self.pool = resolve()
            self.conn = self.pool.getconn()
            self.cur = self.conn.cursor(row_factory=dict_row)
            self.cur.execute("SELECT set_config('app.current_owner', %s, true)", (self.owner,))
            return self.cur

        def __exit__(self, exc_type, exc, tb):
            try:
                if exc_type:
                    self.conn.rollback()
                else:
                    self.conn.commit()
            finally:
                self.cur.close()
                self.pool.putconn(self.conn)
    return _tx


def apply_rls(conn, tenant_tables, owner_col="owner_user_id"):
    """FORCE row-level security + the standard isolation policy on each table, and grant
    DML to app_rls. Call from init() on an admin connection after CREATE TABLEs."""
    for t in tenant_tables:
        conn.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        conn.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        conn.execute(f"DROP POLICY IF EXISTS {t}_isolation ON {t}")
        conn.execute(f"""CREATE POLICY {t}_isolation ON {t}
            USING ({owner_col} IS NULL OR {owner_col} = current_setting('app.current_owner', true))
            WITH CHECK ({owner_col} IS NULL OR {owner_col} = current_setting('app.current_owner', true))""")
    conn.execute("GRANT USAGE ON SCHEMA public TO app_rls")
    conn.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO app_rls")


def fork_safe(celery_app_module_pool_ref):
    """Celery prefork guard: recreate the given pool in each worker child (connections
    opened pre-fork break on fork). Usage in celery_app.py:

        from foundry_common.db import fork_safe
        fork_safe(lambda: __import__("db_pg"))
    """
    from celery.signals import worker_process_init

    @worker_process_init.connect
    def _fresh_pool(**_):
        mod = celery_app_module_pool_ref()
        try:
            mod._pool.close()
        except Exception:
            pass
        mod._pool = ConnectionPool(mod.DATABASE_URL, min_size=1, max_size=10,
                                   open=True, kwargs={"autocommit": False})
    return _fresh_pool
