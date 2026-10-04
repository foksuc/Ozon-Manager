from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    ozon_base_url: str = os.getenv("OZON_BASE_URL", "https://api-seller.ozon.ru")
    ozon_timeout: float = float(os.getenv("OZON_TIMEOUT", "20"))
    database_path: str = os.getenv("OZON_DB_PATH", "data/ozon_manager.sqlite3")
    batch_size: int = int(os.getenv("OZON_BATCH_SIZE", "100"))
    product_info_batch_size: int = int(os.getenv("OZON_PRODUCT_INFO_BATCH_SIZE", "1000"))

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise ValueError("OZON_BATCH_SIZE must be >= 1")
        if self.product_info_batch_size < 1:
            raise ValueError("OZON_PRODUCT_INFO_BATCH_SIZE must be >= 1")
