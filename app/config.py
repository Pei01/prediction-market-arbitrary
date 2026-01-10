import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Polymarket API Endpoints
    CLOB_URL = os.getenv("CLOB_URL", "https://clob.polymarket.com")
    GAMMA_URL = os.getenv("GAMMA_URL", "https://gamma-api.polymarket.com")
    WS_URL = os.getenv("WS_URL", "wss://ws-subscriptions-clob.polymarket.com")

    # Polymarket wallet
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    FUNDER = os.getenv("FUNDER_ADDRESS")

    # Default to Polygon Mainnet
    CHAIN_ID = int(os.getenv("CHAIN_ID", 137))

    # Log 設定
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_MB", 10)) * 1024 * 1024
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))


settings = Settings()
