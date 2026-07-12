from typing import Any

from app.delta_service import DeltaService
from app.strategies.base import (
    BaseStrategy,
    CustomStrategy,
    IndicatorsStrategy,
    IronCondorStrategy,
    ShortStraddleStrategy,
    StrategyState,
)

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    ShortStraddleStrategy.id: ShortStraddleStrategy,
    IronCondorStrategy.id: IronCondorStrategy,
    IndicatorsStrategy.id: IndicatorsStrategy,
    CustomStrategy.id: CustomStrategy,
}

class StrategyManager:
    def __init__(self, delta: DeltaService):
        self.delta = delta
        self._active: dict[str, BaseStrategy] = {}

    def list_strategies(self) -> list[dict[str, str]]:
        return [
            {"id": cls.id, "name": cls.name, "description": cls.description}
            for cls in STRATEGY_REGISTRY.values()
        ]

    def get_state(self, strategy_id: str) -> StrategyState | None:
        strat = self._active.get(strategy_id)
        return strat.state if strat else None

    def start(self, strategy_id: str, expiry_date: str, params: dict[str, Any]) -> StrategyState:
        if strategy_id not in STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy: {strategy_id}")
        cls = STRATEGY_REGISTRY[strategy_id]
        strat = cls(self.delta, params)
        strat.start(expiry_date)
        self._active[strategy_id] = strat
        return strat.state

    def run_once(self, strategy_id: str, expiry_date: str) -> dict[str, Any]:
        strat = self._active.get(strategy_id)
        if not strat:
            raise ValueError(f"Strategy {strategy_id} is not running")
        return strat.run_once(expiry_date)

    def stop(self, strategy_id: str) -> StrategyState:
        strat = self._active.get(strategy_id)
        if not strat:
            raise ValueError(f"Strategy {strategy_id} is not running")
        state = strat.stop()
        del self._active[strategy_id]
        return state

    def all_states(self) -> dict[str, dict[str, Any]]:
        return {
            sid: {
                "strategy_id": s.state.strategy_id,
                "status": s.state.status,
                "started_at": s.state.started_at.isoformat() if s.state.started_at else None,
                "last_run": s.state.last_run.isoformat() if s.state.last_run else None,
                "logs": s.state.logs[-20:],
                "metadata": s.state.metadata,
            }
            for sid, s in self._active.items()
        }
