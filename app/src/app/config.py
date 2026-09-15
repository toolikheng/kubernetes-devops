from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    app_name: str = "DevOps Platform API"
    debug: bool = False
    database_url: str = "sqlite:///./app.db"


settings = Settings()
