import asyncio
import websockets
import json
import logging
from app.config import settings
from typing import List, Callable, Awaitable

logger = logging.getLogger(__name__)


class PolymarketWSClient:
    def __init__(self):
        self.ws_url = settings.WS_URL
        self.ws = None

        self.callback = None
        self.keep_running = False

        self.current_subscriptions = set()
        self.lock = asyncio.Lock()

    async def start(self, callback: Callable[[str], Awaitable[None]]):
        url = f"{self.ws_url}/ws/market"

        self.callback = callback
        self.keep_running = True

        while self.keep_running:
            try:
                logger.info(f"🔌 [WS] 正在連接: {url}")

                async with websockets.connect(url, ping_interval=20) as ws:
                    self.ws = ws
                    logger.info(f"✅ [WS] 連線成功")

                    keep_alive_task = asyncio.create_task(
                        self._keep_alive_loop())

                    if self.current_subscriptions:
                        logger.info(
                            f"🔄 [WS] 偵測到重連，自動補訂閱 {len(self.current_subscriptions)} 筆")

                        subscriptions_list = list(self.current_subscriptions)
                        await self.subscribe(subscriptions_list)

                    try:
                        async for message in ws:
                            if self.callback:
                                asyncio.create_task(self.callback(message))

                    finally:
                        if keep_alive_task:
                            keep_alive_task.cancel()

                            try:
                                await keep_alive_task

                            except asyncio.CancelledError:
                                pass

                        self.ws = None

            except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError):
                logger.warning("⚠️ [WS] 連線中斷，5秒後準備重新連線...")
                self.ws = None

            except Exception as e:
                logger.error(f"❌ [WS] 發生錯誤: {e}", exc_info=True)
                self.ws = None

            # 重新連線
            if self.keep_running:
                await asyncio.sleep(5)

    async def subscribe(self, asset_ids: List[str]):
        self.current_subscriptions.update(asset_ids)

        msg = {
            "assets_ids": asset_ids,
            "operation": "subscribe"
        }

        logger.debug(f"📤 [WS] 發送訂閱封包: {msg}")
        await self._send_json(msg)

    async def unsubscribe(self, asset_ids: List[str]):
        msg = {
            "assets_ids": asset_ids,
            "operation": "unsubscribe"
        }

        logger.debug(f"📤 [WS] 發送取消訂閱: {msg}")
        await self._send_json(msg)

        self.current_subscriptions.difference_update(asset_ids)

    async def _send_json(self, payload: dict):
        async with self.lock:
            if self.ws:
                try:
                    await self.ws.send(json.dumps(payload))

                except Exception as e:
                    logger.error(f"❌ [WS] 發送失敗: {e}")

            else:
                logger.warning("⚠️ [WS] 未連線，無法發送訊息")

    async def _keep_alive_loop(self):
        try:
            while self.keep_running:
                await asyncio.sleep(30)

                if self.ws:
                    try:
                        payload = {"type": "ping"}

                        logger.debug("[WS] 發送 Ping")
                        await self.ws.send(json.dumps(payload))

                    except Exception as e:
                        logger.debug(f"[WS] Ping 失敗: {e}")
                        break

        except asyncio.CancelledError:
            pass
