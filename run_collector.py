import asyncio
import logging
import argparse
from app.workers.collector import Collector
from app.core.logger import setup_logger 

setup_logger()
logger = logging.getLogger("Main")

async def main(asset: str):
    logger.info(f"🔥 準備啟動 Collector: {asset}")
    
    collector = Collector(asset)
    
    try:
        await collector.start()

    except asyncio.CancelledError:
        logger.info("🛑 任務被取消")

    except Exception as e:
        logger.error(f"❌ 程式發生錯誤: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="啟動 Polymarket 資料收集器")
    parser.add_argument(
        "--asset", 
        type=str, 
        default="BTC", 
        help="指定要監控的資產 (例如: BTC, ETH, SOL)"
    )
    
    args = parser.parse_args()

    try:
        asyncio.run(main(asset=args.asset))

    except KeyboardInterrupt:
        logger.info("👋 使用者手動停止 (KeyboardInterrupt)")