from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.delta_service import DeltaService
from app.option_resolver import resolve_custom_option
from app.order_parallel import place_order_safe, run_parallel


@dataclass
class StrategyState:
    strategy_id: str
    status: str = "idle"
    started_at: datetime | None = None
    last_run: datetime | None = None
    logs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def log(self, message: str) -> None:
        ts = datetime.utcnow().strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {message}")
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]


class BaseStrategy(ABC):
    id: str = "base"
    name: str = "Base Strategy"
    description: str = ""

    def __init__(self, delta: DeltaService, params: dict[str, Any]):
        self.delta = delta
        self.params = params
        self.state = StrategyState(strategy_id=self.id)

    @abstractmethod
    def run_once(self, expiry_date: str) -> dict[str, Any]:
        pass

    def start(self, expiry_date: str) -> StrategyState:
        self.state.status = "running"
        self.state.started_at = datetime.utcnow()
        self.state.log(f"Started {self.name} for expiry {expiry_date}")
        return self.state

    def stop(self) -> StrategyState:
        self.state.status = "stopped"
        self.state.log("Strategy stopped")
        return self.state


class ShortStraddleStrategy(BaseStrategy):
    """Sell ATM call + put when combined premium exceeds threshold."""

    id = "short_straddle"
    name = "Short Straddle (ATM)"
    description = "Sells at-the-money call and put when mark premium sum meets min_premium."

    def run_once(self, expiry_date: str) -> dict[str, Any]:
        min_premium = float(self.params.get("min_premium", 500))
        size = int(self.params.get("size", 1))

        spot = self.delta.get_btc_spot()
        spot_price = float(spot.get("mark_price") or spot.get("spot_price") or 0)
        if spot_price <= 0:
            raise ValueError("Could not fetch BTC spot price")

        chain = self.delta.get_option_chain(expiry_date)
        if not chain:
            raise ValueError(f"No options for expiry {expiry_date}")

        strikes: dict[float, dict[str, Any]] = {}
        for t in chain:
            strike = float(t.get("strike_price") or 0)
            if strike <= 0:
                continue
            kind = "call" if t.get("contract_type") == "call_options" else "put"
            if strike not in strikes:
                strikes[strike] = {}
            strikes[strike][kind] = t

        atm_strike = min(strikes.keys(), key=lambda s: abs(s - spot_price))
        legs = strikes.get(atm_strike, {})
        call = legs.get("call")
        put = legs.get("put")
        if not call or not put:
            raise ValueError(f"ATM straddle incomplete at strike {atm_strike}")

        call_premium = float(call.get("mark_price") or 0)
        put_premium = float(put.get("mark_price") or 0)
        total_premium = call_premium + put_premium

        self.state.log(f"Spot {spot_price:.0f}, ATM {atm_strike}, premium {total_premium:.2f}")

        orders = []
        if total_premium >= min_premium:
            for leg, label in [(call, "call"), (put, "put")]:
                order = self.delta.place_order(
                    product_id=int(leg["product_id"]),
                    size=size,
                    side="sell",
                    order_type="market_order",
                )
                orders.append({"leg": label, "order": order})
                self.state.log(f"Sold {label} {leg.get('symbol')}")
        else:
            self.state.log(f"Premium {total_premium:.2f} below threshold {min_premium}")

        self.state.last_run = datetime.utcnow()
        self.state.metadata = {
            "spot_price": spot_price,
            "atm_strike": atm_strike,
            "total_premium": total_premium,
            "orders_placed": len(orders),
        }
        return {"orders": orders, "metadata": self.state.metadata}


class IronCondorStrategy(BaseStrategy):
    """Placeholder: sell OTM call spread + put spread."""

    id = "iron_condor"
    name = "Iron Condor"
    description = "Sells OTM call and put spreads (requires wing width params)."

    def run_once(self, expiry_date: str) -> dict[str, Any]:
        wing_width = float(self.params.get("wing_width", 2000))
        size = int(self.params.get("size", 1))

        spot = self.delta.get_btc_spot()
        spot_price = float(spot.get("mark_price") or spot.get("spot_price") or 0)
        chain = self.delta.get_option_chain(expiry_date)

        calls = [t for t in chain if t.get("contract_type") == "call_options"]
        puts = [t for t in chain if t.get("contract_type") == "put_options"]
        if not calls or not puts:
            raise ValueError("Insufficient option chain data")

        short_call_strike = min(calls, key=lambda t: abs(float(t["strike_price"]) - (spot_price + wing_width)))
        short_put_strike = min(puts, key=lambda t: abs(float(t["strike_price"]) - (spot_price - wing_width)))

        self.state.log(
            f"Iron condor preview: short call {short_call_strike.get('symbol')}, "
            f"short put {short_put_strike.get('symbol')}"
        )
        self.state.last_run = datetime.utcnow()
        self.state.metadata = {"spot_price": spot_price, "size": size, "mode": "preview_only"}
        return {"metadata": self.state.metadata, "note": "Configure full 4-leg execution in production"}


class CustomStrategy(BaseStrategy):
    """User-defined option: call/put, ATM strike, today/tomorrow expiry."""

    id = "custom"
    name = "Custom"
    description = "Multi-leg custom trades — call/put, ATM, Today/Tomorrow per leg."

    def _resolve_configured_legs(self) -> list[dict[str, Any]]:
        leg_configs = self.params.get("legs")
        if not leg_configs and self.params.get("option_type"):
            leg_configs = [
                {
                    "option_type": self.params.get("option_type"),
                    "strike_type": self.params.get("strike_type", "ATM"),
                    "expiry_slot": self.params.get("expiry_slot", "today"),
                    "side": self.params.get("side", "buy"),
                    "size": self.params.get("size", 1),
                    "order_type": self.params.get("order_type", "limit_order"),
                    "limit_price": self.params.get("limit_price"),
                }
            ]
        if not leg_configs:
            return []

        resolved_list: list[dict[str, Any]] = []
        resolved_meta: list[dict[str, Any]] = []
        for i, leg_cfg in enumerate(leg_configs):
            if leg_cfg.get("symbol") or leg_cfg.get("product_id"):
                resolved_list.append(leg_cfg)
                continue
            if not leg_cfg.get("option_type"):
                raise ValueError(f"Leg {i + 1}: option_type required")
            resolved = resolve_custom_option(
                self.delta,
                option_type=leg_cfg.get("option_type", "call"),
                strike_type=leg_cfg.get("strike_type", "ATM"),
                expiry_slot=leg_cfg.get("expiry_slot", "today"),
            )
            resolved_meta.append(resolved)
            self.state.log(
                f"Leg {i + 1}: {resolved['option_type'].upper()} ATM {resolved['atm_strike']:.0f} "
                f"→ {resolved['symbol']}"
            )
            resolved_list.append(
                {
                    "symbol": resolved["symbol"],
                    "product_id": resolved["product_id"],
                    "side": leg_cfg.get("side", "buy"),
                    "size": leg_cfg.get("size", 1),
                    "order_type": leg_cfg.get("order_type", "limit_order"),
                    "limit_price": leg_cfg.get("limit_price"),
                }
            )
        if resolved_meta:
            self.state.metadata["resolved_legs"] = resolved_meta
        return resolved_list

    def _build_legs_from_params(self) -> list[dict[str, Any]]:
        configured = self._resolve_configured_legs()
        if configured:
            return configured

        legs = self.params.get("legs")
        if legs:
            return legs
        return [
            {
                "symbol": self.params.get("symbol"),
                "product_id": self.params.get("product_id"),
                "side": self.params.get("side", "buy"),
                "size": self.params.get("size", 1),
                "order_type": self.params.get("order_type", "limit_order"),
                "limit_price": self.params.get("limit_price"),
            }
        ]

    def _resolve_leg(self, leg: dict[str, Any]) -> tuple[int, str]:
        product_id = leg.get("product_id")
        symbol = (leg.get("symbol") or "").strip()
        if product_id:
            pid = int(product_id)
            if not symbol:
                product = self.delta.client.get_product(pid)
                symbol = product.get("symbol", f"product_{pid}")
            return pid, symbol
        if not symbol:
            raise ValueError("Each leg needs a symbol or product_id")
        ticker = self.delta.get_ticker(symbol)
        pid = ticker.get("product_id")
        if not pid:
            raise ValueError(f"Could not resolve symbol: {symbol}")
        return int(pid), symbol

    def _place_configured_leg(self, leg: dict[str, Any], index: int) -> dict[str, Any]:
        product_id, symbol = self._resolve_leg(leg)
        side = leg.get("side", "buy")
        size = int(leg.get("size", 1))
        order_type = leg.get("order_type", "limit_order")
        limit_price = leg.get("limit_price")

        if order_type == "limit_order" and not limit_price:
            limit_price = leg.get("mark_price")
        if order_type == "limit_order" and not limit_price:
            ticker = self.delta.get_ticker(symbol)
            limit_price = ticker.get("mark_price")
        if order_type == "limit_order" and not limit_price:
            raise ValueError(f"Leg {index + 1}: limit_price required for limit orders")

        self.state.log(f"Placing {side} {size}x {symbol} ({order_type})")

        order = place_order_safe(
            self.delta,
            product_id=product_id,
            size=size,
            side=side,
            limit_price=str(limit_price) if order_type == "limit_order" else None,
            order_type=order_type,
        )
        self.state.log(f"Order placed for {symbol}")
        return {"symbol": symbol, "side": side, "size": size, "order": order}

    def run_once(self, expiry_date: str) -> dict[str, Any]:
        legs = self._build_legs_from_params()

        if len(legs) <= 1:
            orders = []
            for i, leg in enumerate(legs):
                orders.append(self._place_configured_leg(leg, i))
        else:
            orders = run_parallel(
                [lambda leg=leg, idx=i: self._place_configured_leg(leg, idx) for i, leg in enumerate(legs)]
            )

        self.state.last_run = datetime.utcnow()
        self.state.metadata = {
            **self.state.metadata,
            "expiry_date": expiry_date,
            "legs_executed": len(orders),
        }
        return {"orders": orders, "metadata": self.state.metadata}


class IndicatorsStrategy(CustomStrategy):
    """Indicator-based strategy — same leg controls as Custom."""

    id = "indicators"
    name = "Indicators"
    description = "Indicator-driven entries — Supertrend and more."
