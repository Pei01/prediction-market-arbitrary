import aiosqlite
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class SQLiteClient:
    def __init__(self, db_path: str = "data/polymarke.db"):
        self.db_path = db_path
        self.conn = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path)

        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self._create_tables()

        logger.info(f"💾 SQLite 連線成功: {self.db_path}")

    async def close(self):
        if self.conn:
            await self.conn.close()
            logger.info("🛑 SQLite 連線已關閉")

    async def _create_tables(self):
        # market table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS markets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE,
                title TEXT,
                created_at TEXT
            );
        """)

        # ticks table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id INTEGER NOT NULL,
                ts TEXT NOT NULL,
                buy_up_price REAL,
                buy_down_price REAL,
                buy_up_size REAL,
                buy_down_size REAL,
                FOREIGN KEY(market_id) REFERENCES markets(id)
            );
        """)

        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_market_ts ON ticks (market_id, ts);")
        await self.conn.commit()

    async def get_or_create_market(self, slug: str, title: str, created_at: str) -> Optional[int]:
        if not self.conn:
            return None

        try:
            async with self.conn.execute("SELECT id FROM markets WHERE slug = ?", (slug,)) as cursor:
                row = await cursor.fetchone()

                if row:
                    return row[0]
            
            cursor = await self.conn.execute("""
                INSERT INTO markets (slug, title, created_at)
                VALUES (?, ?, ?)
            """, (slug, title, created_at))

            await self.conn.commit()
            return cursor.lastrowid

        except Exception as e:
            logger.error(f"❌ 儲存 Market 失敗: {e}")
            return None

    async def save_ticks_batch(self, records: List[Tuple]):
        if not self.conn or not records:
            return

        try:
            await self.conn.executemany("""
                INSERT INTO ticks (ts, market_id, buy_up_price, buy_down_price, buy_up_size, buy_down_size)
                VALUES (?, ?, ?, ?, ?, ?)
            """, records)

            await self.conn.commit()
            logger.debug(f"💾 成功寫入 {len(records)} 筆資料")

        except Exception as e:
            logger.error(f"❌ 批次寫入失敗: {e}")
