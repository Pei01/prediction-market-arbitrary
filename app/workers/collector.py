import logging
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional

from app.clients.polymarket import PolymarketClient
from app.clients.polymarket_ws import PolymarketWSClient
from app.storage.sqlite import SQLiteClient
from app.utils.time import get_current_window_timestamp

logger = logging.getLogger(__name__)


class Collector:
    def __init__(self, asset: str):
        self.asset = asset
        self.client = PolymarketClient()
        self.ws_client = PolymarketWSClient()
        self.db = SQLiteClient("data/polymarket.db")

        self.queue = asyncio.Queue(maxsize=10000)
        self.batch_buffer: List[Dict] = []
        self.BATCH_SIZE = 50

        self.running = False
        self.current_window_timestamp = None

        self.token_map = {}
        self.price_snapshots = {}

        self.active_tokens: List[str] = []

    async def start(self):
        logger.info(f"🚀 Collector 啟動 (Asset: {self.asset})")
        self.running = True

        await self.db.connect()

        asyncio.create_task(self.ws_client.start(self.on_message))
        db_task = asyncio.create_task(self._db_worker())

        try:
            while self.running:
                target_timestamp = get_current_window_timestamp()

                if target_timestamp != self.current_window_timestamp:
                    logger.info(f"⚡ 偵測到新時段目標: {target_timestamp}")

                    success = await self._switch_to_new_market(target_timestamp)

                    if success:
                        self.current_window_timestamp = target_timestamp
                        await asyncio.sleep(0.1)

                    else:
                        logger.warning("⏳ 訂閱未成功，5秒後重試...")
                        await asyncio.sleep(5)

                else:
                    await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            logger.info("🛑 Collector 收到停止訊號")

        except Exception as e:
            logger.error(f"❌ 發生錯誤: {e}")

        finally:
            logger.info("⏳ 等待剩餘資料寫入...")

            self.running = False

            await db_task
            await self.db.close()

    async def on_message(self, raw_msg: str):
        try:
            data = json.loads(raw_msg)
            event_type = data.get("event_type")

            if event_type == "book":
                asset_id = data.get("asset_id")
                token_info = self.token_map.get(asset_id)

                if not token_info:
                    return

                market_id = token_info.get("market_id")
                token_type = token_info.get("type")

                timestamp = data.get("timestamp")

                bids = data.get("bids", [])

                if not bids:
                    return

                best_bid = max(bids, key=lambda bid: float(bid["price"]))

                new_price = best_bid.get("price")
                new_size = best_bid.get("size")

                # update snapshot
                snapshot = self.price_snapshots.get(market_id)

                if token_type == "UP":
                    snapshot["buy_up_price"] = new_price
                    snapshot["buy_up_size"] = new_size

                else:
                    snapshot["buy_down_price"] = new_price
                    snapshot["buy_down_size"] = new_size

                # queue
                row_data = {
                    "ts": timestamp,
                    "market_id": market_id,
                    **snapshot
                }

                try:
                    self.queue.put_nowait(row_data)

                except:
                    logger.warning("⚠️ Queue 已滿，正在丟棄資料...")

        except Exception as e:
            logger.debug(f"處理訊息略過: {e}")

    async def _switch_to_new_market(self, timestamp: int) -> bool:

        market_data = await self._prepare_market_metadata(timestamp)

        if not market_data:
            return False

        if self.active_tokens:
            logger.info(f"退訂舊市場 Tokens: {self.active_tokens}")
            await self.ws_client.unsubscribe(self.active_tokens)
            
            for token in self.active_tokens:
                self.token_map.pop(token, None)

        self._update_local_state(market_data)

        up_token = market_data.get("up_token")
        down_token = market_data.get("down_token")

        token_ids = [up_token, down_token]
        await self.ws_client.subscribe(token_ids)

        self.active_tokens = token_ids

        market_id = market_data.get("market_id")
        logger.info(f"✅ 成功切換至市場 ID: {market_id}")

        return True

    async def _prepare_market_metadata(self, timestamp: int) -> Optional[Dict]:
        logger.info(f"🔍 開始尋找市場資料 (TS: {timestamp})")

        # gamma api
        market_data = self.client.get_market(self.asset, timestamp)

        if not market_data:
            return False

        title = market_data.get("title")
        up_token = market_data.get("up")
        down_token = market_data.get("down")

        asset = self.asset.lower()
        slug = f"{asset}-updown-15m-{timestamp}"

        current_time = datetime.now().isoformat()

        # DB
        market_id = await self.db.get_or_create_market(
            slug=slug,
            title=title,
            created_at=current_time
        )

        if not market_id:
            logger.error("❌ 無法取得 Market ID")
            return None

        result = {
            "market_id": market_id,
            "up_token": up_token,
            "down_token": down_token,
            "slug": slug
        }

        return result

    def _update_local_state(self, data: Dict):
        market_id = data.get("market_id")
        up_token = data.get("up_token")
        down_token = data.get("down_token")

        self.token_map[up_token] = {"market_id": market_id, "type": "UP"}
        self.token_map[down_token] = {"market_id": market_id, "type": "DOWN"}

        if market_id not in self.price_snapshots:
            self.price_snapshots[market_id] = {
                "buy_up_price": None,
                "buy_down_price": None,
                "buy_up_size": None,
                "buy_down_size": None,
            }

    async def _db_worker(self):
        logger.info("💾 DB 寫入工兵啟動")

        while self.running or not self.queue.empty():
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=1)
                self.batch_buffer.append(item)

                if len(self.batch_buffer) >= self.BATCH_SIZE:
                    await self._flush_to_db()

                self.queue.task_done()

            except asyncio.TimeoutError:
                if self.batch_buffer:
                    await self._flush_to_db()

                continue

            except Exception as e:
                logger.error(f"❌ DB Worker 錯誤: {e}")

    async def _flush_to_db(self):
        if not self.batch_buffer:
            return
        
        data = self.batch_buffer[:]
        self.batch_buffer.clear()

        record = []

        for item in data:
            record.append((
                item["ts"],
                item["market_id"],
                item["buy_up_price"],
                item["buy_down_price"],
                item["buy_up_size"],
                item["buy_down_size"]
            ))

        await self.db.save_ticks_batch(record)
