from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    app_host: str = "0.0.0.0"
    app_port: int = 8577
    api_token: str = ""
    apprise_url: str = ""
    apprise_tag: str = ""
    puid: int = 1000
    guid: int = 1000
    node_name: str = ""
    node_id: str = ""
    node_listener: str = ""
    node_listener_port: int = 5053
    upgrades_dir: str = "./upgrades"
    repo_scan_interval_minutes: int = 10
    base_url: str = ""
    sl_statisiv: str = ""
    sl_ivkey: str = ""
    sl_datakey: str = ""
    sl_passphrase: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
