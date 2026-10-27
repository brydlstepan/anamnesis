from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_LANGUAGES = ("cs", "en")


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (see .env.example)."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    secret_key: str = Field(validation_alias="ANAMNESIS_SECRET_KEY", min_length=32)
    public_url: str = Field("http://localhost:8080", validation_alias="ANAMNESIS_PUBLIC_URL")
    admin_username: str = Field("admin", validation_alias="ANAMNESIS_ADMIN_USERNAME")
    admin_password: str | None = Field(None, validation_alias="ANAMNESIS_ADMIN_PASSWORD")
    admin_path: str = Field("/admin", validation_alias="ANAMNESIS_ADMIN_PATH")
    default_language: str = Field("cs", validation_alias="ANAMNESIS_DEFAULT_LANGUAGE")
    data_dir: Path = Field(Path("/data"), validation_alias="ANAMNESIS_DATA_DIR")
    static_dir: Path | None = Field(None, validation_alias="ANAMNESIS_STATIC_DIR")
    database_url: str | None = Field(None, validation_alias="ANAMNESIS_DATABASE_URL")
    session_max_age_days: int = Field(14, validation_alias="ANAMNESIS_SESSION_MAX_AGE_DAYS")
    enable_api_docs: bool = Field(False, validation_alias="ANAMNESIS_ENABLE_API_DOCS")

    oidc_issuer: str | None = Field(None, validation_alias="OIDC_ISSUER")
    oidc_client_id: str | None = Field(None, validation_alias="OIDC_CLIENT_ID")
    oidc_client_secret: str | None = Field(None, validation_alias="OIDC_CLIENT_SECRET")
    oidc_scopes: str = Field("openid email profile", validation_alias="OIDC_SCOPES")
    oidc_display_name: str = Field("SSO", validation_alias="OIDC_DISPLAY_NAME")

    @field_validator("public_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("admin_path")
    @classmethod
    def _admin_path(cls, v: str) -> str:
        v = "/" + v.strip().strip("/")
        if v == "/" or v.startswith("/api") or v.startswith("/assets"):
            raise ValueError("ANAMNESIS_ADMIN_PATH must not be '/', '/api…' or '/assets…'")
        return v

    @field_validator("default_language")
    @classmethod
    def _lang(cls, v: str) -> str:
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"ANAMNESIS_DEFAULT_LANGUAGE must be one of {SUPPORTED_LANGUAGES}")
        return v

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'anamnesis.db'}"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def oidc_enabled(self) -> bool:
        return bool(self.oidc_issuer and self.oidc_client_id and self.oidc_client_secret)

    @property
    def secure_cookies(self) -> bool:
        return self.public_url.startswith("https://")
