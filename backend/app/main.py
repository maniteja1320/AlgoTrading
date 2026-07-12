from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.delta_service import get_delta_service
from app.routers import account, market, my_strategies, notifications, strategies, trading
from app.saved_strategy_runner import lifespan as runner_lifespan
from app.strategies.manager import StrategyManager

_strategy_manager: StrategyManager | None = None


def get_strategy_manager() -> StrategyManager:
    global _strategy_manager
    if _strategy_manager is None:
        _strategy_manager = StrategyManager(get_delta_service())
    return _strategy_manager


def reset_strategy_manager() -> None:
    global _strategy_manager
    _strategy_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_strategy_manager()
    async with runner_lifespan(app):
        yield


app = FastAPI(title="Delta BTC Options Algo", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(account.router, prefix="/api/account", tags=["account"])
app.include_router(trading.router, prefix="/api/trading", tags=["trading"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(my_strategies.router, prefix="/api/my-strategies", tags=["my-strategies"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
