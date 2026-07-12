from pydantic import BaseModel, Field, model_validator


class ApiConfigUpdate(BaseModel):
    api_key: str = Field(..., min_length=1)
    api_secret: str = Field(..., min_length=1)
    env: str = Field(default="testnet", pattern="^(testnet|production)$")


class PlaceOrderRequest(BaseModel):
    product_id: int
    size: int = Field(..., gt=0)
    side: str = Field(..., pattern="^(buy|sell)$")
    order_type: str = Field(default="limit_order", pattern="^(limit_order|market_order)$")
    limit_price: str | None = None
    post_only: str = "false"
    reduce_only: str = "false"
    pnl_amount: float | None = None
    pnl_pct: float | None = None


class CancelOrderRequest(BaseModel):
    product_id: int
    order_id: int


class StrategyStartRequest(BaseModel):
    strategy_id: str
    expiry_date: str
    params: dict = Field(default_factory=dict)


class StrategyRunRequest(BaseModel):
    strategy_id: str
    expiry_date: str


class StrategyStopRequest(BaseModel):
    strategy_id: str


class StrategyLeg(BaseModel):
    option_type: str = Field(..., pattern="^(call|put)$")
    strike_type: str = Field(default="ATM")
    expiry_slot: str = Field(..., pattern="^(today|tomorrow|slot_\\d+)$")
    side: str = Field(default="buy", pattern="^(buy|sell)$")
    order_type: str = Field(default="limit_order", pattern="^(limit_order|market_order)$")
    limit_price: str | None = None
    size: int = Field(default=1, gt=0)
    exit_if_enabled: bool = False


class TrailingProfitRule(BaseModel):
    profit_pct: float = Field(..., gt=0, description="Exit partial size when combined P&L reaches this %")
    size: int = Field(..., gt=0, description="Lots to exit on each leg at this profit level")


class SavedStrategyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    strategy_template: str = Field(default="custom", pattern="^(custom|indicators)$")
    indicator: str = Field(default="none", pattern="^(none|supertrend)$")
    supertrend_length: int | None = Field(default=None, ge=1, le=100)
    supertrend_factor: float | None = Field(default=None, gt=0, le=20)
    supertrend_timeframe: str | None = Field(default=None, pattern="^(5m|15m|1h|4h)$")
    entry_condition: str = Field(default="close_below", pattern="^(close_below|close_above)$")
    entry_days: list[str] = Field(default_factory=list, min_length=0)
    entry_time: str = Field(default="09:30 AM", description="e.g. 09:30 AM")
    end_time: str = Field(..., description="e.g. 03:30 PM")
    legs: list[StrategyLeg] = Field(..., min_length=1)
    entry_if_enabled: bool = False
    entry_if_low: float | None = Field(default=None, gt=0)
    entry_if_high: float | None = Field(default=None, gt=0)
    total_profit_pct: float | None = Field(default=None, gt=0, description="Exit when combined profit reaches this %")
    total_loss_pct: float | None = Field(default=None, gt=0, description="Exit when combined loss reaches this %")
    trailing_profits: list[TrailingProfitRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_trailing_profits(self) -> "SavedStrategyCreate":
        seen: set[float] = set()
        for rule in self.trailing_profits:
            key = float(rule.profit_pct)
            if key in seen:
                raise ValueError("Trailing profit levels must be unique")
            seen.add(key)
        if self.trailing_profits and self.legs:
            min_leg = min(leg.size for leg in self.legs)
            total_trail = sum(rule.size for rule in self.trailing_profits)
            if total_trail > min_leg:
                raise ValueError(
                    "Trailing profit total size cannot exceed the smallest leg size"
                )
        return self

    @model_validator(mode="after")
    def validate_entry_mode(self) -> "SavedStrategyCreate":
        if self.strategy_template == "indicators":
            self.entry_if_enabled = False
            self.entry_days = []
            if self.indicator == "supertrend":
                if self.supertrend_length is None or self.supertrend_factor is None or not self.supertrend_timeframe:
                    raise ValueError("Supertrend length, factor, and timeframe are required")
                if self.entry_condition not in ("close_below", "close_above"):
                    raise ValueError("Entry condition is required for Supertrend")
            return self

        if self.entry_if_enabled:
            if (
                self.entry_if_low is not None
                and self.entry_if_high is not None
                and self.entry_if_low >= self.entry_if_high
            ):
                raise ValueError("Entry if lower must be less than upper when both are set")
        else:
            from app.time_utils import validate_entry_days

            self.entry_days = validate_entry_days(self.entry_days)
        return self
