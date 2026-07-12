from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _strip_env_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1].strip()
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    delta_api_key: str = ""
    delta_api_secret: str = ""
    delta_env: str = "testnet"
    cors_origins: str = "http://localhost:5173"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_ssl: bool = False
    alert_email_to: str = ""
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_claims_email: str = "mailto:admin@example.com"

    @field_validator(
        "smtp_host",
        "smtp_user",
        "smtp_password",
        "alert_email_to",
        "vapid_public_key",
        "vapid_private_key",
        "vapid_claims_email",
        mode="before",
    )
    @classmethod
    def strip_wrapping_quotes(cls, value: object) -> object:
        if isinstance(value, str):
            return _strip_env_quotes(value)
        return value

    @property
    def smtp_password_normalized(self) -> str:
        pwd = self.smtp_password.strip()
        if "gmail.com" in self.smtp_host.lower():
            return pwd.replace(" ", "")
        return pwd

    @property
    def vapid_private_key_pem(self) -> str:
        return self.vapid_private_key.replace("\\n", "\n").strip()

    @property
    def base_url(self) -> str:
        if self.delta_env == "production":
            return "https://api.india.delta.exchange"
        return "https://cdn-ind.testnet.deltaex.org"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
