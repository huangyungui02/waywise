"""测试专用 PostgreSQL 数据库；按临时路径隔离，并供恢复子进程复用。"""

from hashlib import sha256
from pathlib import Path

import psycopg
from psycopg import sql
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    test_database_url: SecretStr = SecretStr("postgresql://localhost:55432/postgres")


DATABASES: set[str] = set()


def pg_database(path: Path) -> str:
    name = "waywise_test_" + sha256(str(path).encode()).hexdigest()[:24]
    url = make_url(DatabaseSettings().test_database_url.get_secret_value())
    with psycopg.connect(
        url.render_as_string(hide_password=False), autocommit=True
    ) as conn:
        if not conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
        ).fetchone():
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    DATABASES.add(name)
    return url.set(database=name).render_as_string(hide_password=False)


def drop_test_databases() -> None:
    with psycopg.connect(
        DatabaseSettings().test_database_url.get_secret_value(), autocommit=True
    ) as conn:
        for name in DATABASES:
            conn.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )
        DATABASES.clear()
