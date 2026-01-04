import requests
import websockets
import asyncio
import time
import json
import threading
from datetime import datetime

class PolyMarketClient:
    def __init__(self, asset: str):
        self.asset = asset.lower()
        self.gamma_url = "https://gamma-api.polymarket.com"
        self.ws_url = "wss://ws-subscriptions-clob.polymarket.com"
        self.token_ids = {"up": None, "down": None}

        self.best_buy_up = {"price": 0, "size": 0}
        self.best_buy_down = {"price": 0, "size": 0}

        self.market_start_timestamp = 0
        self.current_timestamp = 0

    def _calculate_market_start_timestamp(self) -> int:
        now = time.time()
        interval = 900  # 15min

        market_start_timestamp = (now // interval) * interval

        self.market_start_timestamp = int(market_start_timestamp)

        return int(market_start_timestamp)

    def get_market(self):
        market_start_timestamp = self._calculate_market_start_timestamp()

        slug = f"{self.asset}-updown-15m-{market_start_timestamp}"

        url = f"{self.gamma_url}/markets/slug/{slug}"

        print(f"Fetching market data from URL: {url}")

        response = requests.get(url)
        data = response.json()

        title = data.get("question")
        print(title)

        raw_token_ids = data.get("clobTokenIds")
        token_ids_list = json.loads(raw_token_ids)

        up_token_id = token_ids_list[0]
        down_token_id = token_ids_list[1]

        token_ids = {"up": up_token_id, "down": down_token_id}

        self.token_ids = token_ids

        return token_ids
    
    def _update_best_up_down(self, data: dict):
        token_id = data.get("asset_id")

        self.current_timestamp = int(data.get("timestamp")) / 1000
        
        asks = data.get("asks")

        if not asks:
            print("No asks data available.")
            return

        if token_id == self.token_ids["up"]:
            best_buy_up = min(asks, key=lambda x: float(x["price"]))

            price = float(best_buy_up["price"])
            size = float(best_buy_up["size"])

            self.best_buy_up = {"price": price, "size": size}

        elif token_id == self.token_ids["down"]:
            best_buy_down = min(asks, key=lambda x: float(x["price"]))

            price = float(best_buy_down["price"])
            size = float(best_buy_down["size"])

            self.best_buy_down = {"price": price, "size": size}

        time = datetime.fromtimestamp(self.current_timestamp)
        formatted_time = time.strftime('%Y-%m-%d %H:%M:%S')

        print(f"{formatted_time} Up: {self.best_buy_up['price']: .2f} | Down: {self.best_buy_down['price']: .2f}")

    async def subscribe_orderbook(self, token_ids: dict):
        message = {
            "assets_ids": [token_ids["up"], token_ids["down"]],
        }

        url = f"{self.ws_url}/ws/market"

        async with websockets.connect(url) as ws:
            await ws.send(json.dumps(message))

            while True:
                if self.current_timestamp >= self.market_start_timestamp + 900:
                    print("Market interval ended. Exiting...")
                    break

                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(message)

                    if isinstance(data, list):
                        continue

                    if data.get("event_type") == "book":
                        self._update_best_up_down(data)

                except asyncio.TimeoutError:
                    print("No message received in the last 5 seconds, sending ping...")
                    ping_message = {
                        "type": "ping"
                    }
                    await ws.send(json.dumps(ping_message))


if __name__ == "__main__":
    client = PolyMarketClient("BTC")
    token_ids = client.get_market()
    asyncio.run(client.subscribe_orderbook(token_ids))

