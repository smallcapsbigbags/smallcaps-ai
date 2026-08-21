from __future__ import annotations

from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
)
from database.product import ProductRepository
from market.pricing import YahooPriceClient
from market.reactions import DailyPriceReactionService
from settings import Settings


def main() -> None:
    settings = Settings.from_env()
    if not settings.market_data_enabled:
        print("Market data update skipped: MARKET_DATA_ENABLED=false")
        return

    engine = create_database_engine(settings.database_url)
    init_database(engine)
    repository = ProductRepository(create_session_factory(engine))
    service = DailyPriceReactionService(
        repository=repository,
        client=YahooPriceClient(
            timeout_seconds=settings.market_data_timeout_seconds
        ),
    )
    result = service.run()
    print(
        "Daily market reaction:",
        f"targets={result.target_count}",
        f"tickers={result.ticker_count}",
        f"updated={result.updated}",
        f"pending={result.pending}",
        f"failed={result.failed}",
    )
    for warning in result.warnings:
        print("WARNING:", warning)


if __name__ == "__main__":
    main()
