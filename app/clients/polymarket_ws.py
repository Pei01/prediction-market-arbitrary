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
                logger.info("正在連接 Polymarket websocket")
                async with websockets.connect(url) as ws:
                    self.ws = ws
                    logger.info("連線成功")

                    if self.current_subscriptions:
                        logger.info("偵測到 Polymarket websocket 重新連線，自動補訂閱")
                        await self.subscribe(self.current_subscriptions)

                    async for message in ws:
                        if self.callback:
                            asyncio.create_task(self.callback(message))

            except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError):
                logger.warning("Polymarket websocket 連線中斷，準備重新連線")
                self.ws = None

            except Exception as e:
                logger.error(f"websocket 錯誤: {e}")
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

        logger.info("訂閱 token")
        await self._send_json(msg)

    async def _send_json(self, payload: dict):
        async with self.lock:
            if self.ws:
                try:
                    await self.ws.send(json.dumps(payload))

                except Exception as e:
                    logger.error(f"發送失敗: {e}")

            else:
                logger.warning("Websocket 未連線，無法發送訊息")

