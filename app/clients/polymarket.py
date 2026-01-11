import requests
import json
import logging
from app.config import settings
from py_clob_client.client import ClobClient

logger = logging.getLogger(__name__)


class PolymarketClient:
    def __init__(self):
        self.gamma_url = settings.GAMMA_URL

        HOST = settings.CLOB_URL
        PRIVATE_KEY = settings.PRIVATE_KEY
        CHAIN_ID = settings.CHAIN_ID
        FUNDER = settings.FUNDER

        self.client = ClobClient(
            HOST,
            key=PRIVATE_KEY,
            chain_id=CHAIN_ID,
            signature_type=1,
            funder=FUNDER
        )

        creds = self.client.create_or_derive_api_creds()
        self.client.set_api_creds(creds)

    # ==========================================
    # 1. Public Data
    # ==========================================
    def get_market(self, asset: str, start_timestamp: int):

        slug = f"{asset.lower()}-updown-15m-{start_timestamp}"
        url = f"{self.gamma_url}/markets/slug/{slug}"

        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            data = response.json()

            if not data:
                logger.warning(f"⚠️ 找不到市場 (Data Empty): {slug}")
                return None

            outcomes_str = data.get("outcomes", "[]")
            token_ids_str = data.get("clobTokenIds", "[]")

            outcomes = json.loads(outcomes_str)
            token_ids = json.loads(token_ids_str)

            if len(outcomes) != 2 or len(token_ids) != 2:
                logger.warning(f"⚠️ Outcomes 與 Token IDs 數量不符: {slug}")
                return None

            result = {}

            for token_id, outcome in zip(token_ids, outcomes):
                result[outcome.lower()] = token_id

            title = data.get("question")
            result["title"] = title

            logger.info(f"✅ 成功鎖定: {title}")

            return result

        except Exception as e:
            logger.error(f"❌ 取得市場失敗({slug}): {e}")
            return None

        # ==========================================
        # 2. Private Data
        # ==========================================

        # ==========================================
        # 3. Trading Actions
        # ==========================================
