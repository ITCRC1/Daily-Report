from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://daily_ops:daily_ops@localhost:5433/daily_ops"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://daily_ops:daily_ops@localhost:5433/daily_ops"
    CORS_ORIGINS: str = "http://localhost:3000"
    DEFAULT_PROPERTY: str = "COWLCR"
    # Raíz de subidas reales de Tab 1 (uploads/inputs/<fecha>). Vacío = usar el
    # cálculo relativo de siempre (correcto en dev local). En producción se
    # apunta a un volumen persistente de Railway montado en el contenedor,
    # para que un redeploy del backend no borre archivos aún no ingestados.
    UPLOADS_DIR: str = ""

    # Railway (y casi cualquier proveedor) inyecta la URL de Postgres como
    # `postgresql://...` a secas -- sin el driver que SQLAlchemy necesita. Antes
    # había que reescribirla a mano en las variables del servicio; si se pegaba
    # tal cual, el backend arrancaba y moría en el primer query. Normalizar acá
    # deja que `DATABASE_URL=${{Postgres.DATABASE_URL}}` funcione directo. Una
    # URL que YA trae driver explícito (`+asyncpg`, `+psycopg2`) no se toca.
    @field_validator("DATABASE_URL")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        return cls._with_driver(v, "asyncpg")

    @field_validator("DATABASE_URL_SYNC")
    @classmethod
    def _sync_driver(cls, v: str) -> str:
        return cls._with_driver(v, "psycopg2")

    @staticmethod
    def _with_driver(url: str, driver: str) -> str:
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return f"postgresql+{driver}://" + url[len(prefix):]
        return url

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
