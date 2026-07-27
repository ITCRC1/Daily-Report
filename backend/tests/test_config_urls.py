"""La URL de Postgres que inyecta el proveedor (Railway) viene sin driver.

Si el backend la toma tal cual, arranca y muere en el primer query. `Settings`
la normaliza; estos tests fijan esa conducta y, sobre todo, que una URL que YA
trae driver explícito no se toque.
"""
import pytest

from app.config import Settings


def _settings(url: str) -> Settings:
    # _env_file=None: ignora el backend/.env local, que pisaría los valores.
    return Settings(_env_file=None, DATABASE_URL=url, DATABASE_URL_SYNC=url)


@pytest.mark.parametrize("raw", ["postgresql://u:p@h:5432/railway", "postgres://u:p@h:5432/railway"])
def test_url_plana_recibe_driver(raw: str) -> None:
    s = _settings(raw)
    assert s.DATABASE_URL == "postgresql+asyncpg://u:p@h:5432/railway"
    assert s.DATABASE_URL_SYNC == "postgresql+psycopg2://u:p@h:5432/railway"


@pytest.mark.parametrize(
    "raw", ["postgresql+asyncpg://u:p@h/db", "postgresql+psycopg2://u:p@h/db"]
)
def test_driver_explicito_no_se_toca(raw: str) -> None:
    assert _settings(raw).DATABASE_URL == raw


def test_password_url_encoded_intacta() -> None:
    """Railway genera passwords con caracteres escapados (%40 = '@'); tocarlos
    rompería la conexión."""
    s = _settings("postgresql://postgres:aB3%40xY@monorail.proxy.rlwy.net:41234/railway")
    assert s.DATABASE_URL == (
        "postgresql+asyncpg://postgres:aB3%40xY@monorail.proxy.rlwy.net:41234/railway"
    )
