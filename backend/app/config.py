from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    delta_api_key: str = ""
    delta_api_secret: str = ""
    delta_env: str = "testnet"
    cors_origins: str = "http://localhost:5173"

    @property
    def base_url(self) -> str:
        if self.delta_env == "production":
            return "https://api.india.delta.exchange"
        return "https://cdn-ind.testnet.deltaex.org"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
