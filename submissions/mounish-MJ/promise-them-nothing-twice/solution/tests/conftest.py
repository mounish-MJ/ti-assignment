from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from app.storage.redis_store import RedisQuotaStore

@pytest.fixture(autouse=True)
def flush_redis():
    # Flush db 0 (default db used in tests)
    store_db0 = RedisQuotaStore(host="localhost", port=6379, db=0)
    if store_db0.backend_mode == "redis":
        store_db0._client.flushdb()

    # Flush db 15 (used in concurrent atomic tests)
    store_db15 = RedisQuotaStore(host="localhost", port=6379, db=15)
    if store_db15.backend_mode == "redis":
        store_db15._client.flushdb()

