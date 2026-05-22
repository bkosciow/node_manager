from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./sources.db"
    app_host: str = "0.0.0.0"
    app_port: int = 8577
    api_token: str = ""
    apprise_url: str = ""
    apprise_tag: str = ""
    transmission_url: str = ""
    transmission_username: str = ""
    transmission_password: str = ""
    download_dir: str = "/downloads"
    jellyfin_url: str = ""
    jellyfin_token: str = ""
    jellyfin_path: str = ""
    jellyfin_lib: str = ""
    puid: int = 1000
    guid: int = 1000

    class Config:
        env_file = ".env"


settings = Settings()
