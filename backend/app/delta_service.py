import math
from typing import Any

from delta_rest_client import DeltaRestClient, OrderType, TimeInForce

from app.api_config_store import load_credentials, save_credentials
from app.config import settings


class DeltaService:
    """Wrapper around Delta Exchange India REST client."""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        env: str | None = None,
    ):
        self._env = env or settings.delta_env
        self._base_url = (
            "https://api.india.delta.exchange"
            if self._env == "production"
            else "https://cdn-ind.testnet.deltaex.org"
        )
        self._api_key = api_key or settings.delta_api_key
        self._api_secret = api_secret or settings.delta_api_secret
        self._client: DeltaRestClient | None = None

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._api_secret)

    @property
    def env(self) -> str:
        return self._env

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def client(self) -> DeltaRestClient:
        if self._client is None:
            self._client = DeltaRestClient(
                base_url=self._base_url,
                api_key=self._api_key or None,
                api_secret=self._api_secret or None,
            )
        return self._client

    def require_auth(self) -> DeltaRestClient:
        if not self.configured:
            raise ValueError("Delta API credentials not configured. Set DELTA_API_KEY and DELTA_API_SECRET.")
        return self.client

    def reset_client(self) -> None:
        self._client = None

    def get_btc_futures(self) -> dict[str, Any]:
        """BTCUSD perpetual futures ticker on Delta India."""
        return self.client.get_ticker("BTCUSD")

    def get_btc_spot(self) -> dict[str, Any]:
        return self.get_btc_futures()

    def get_option_expiries(self) -> list[str]:
        from datetime import datetime

        products = self.client.get_products(
            query={"contract_types": "call_options,put_options", "states": "live"}
        )
        expiries: set[str] = set()
        for p in products:
            if p.get("underlying_asset", {}).get("symbol") == "BTC" and p.get("settlement_time"):
                dt = datetime.fromisoformat(p["settlement_time"].replace("Z", "+00:00"))
                expiries.add(dt.strftime("%d-%m-%Y"))
        return sorted(expiries, key=lambda x: datetime.strptime(x, "%d-%m-%Y"))

    def get_option_chain(self, expiry_date: str) -> list[dict[str, Any]]:
        return self.client.option_chain("BTC", expiry_date)

    def get_products(self, **query: Any) -> list[dict[str, Any]]:
        return self.client.get_products(query=query or None)

    def get_ticker(self, symbol: str) -> dict[str, Any]:
        return self.client.get_ticker(symbol)

    def get_orderbook(self, symbol: str) -> dict[str, Any]:
        return self.client.get_l2_orderbook(symbol)

    def get_balances(self) -> list[dict[str, Any]]:
        return self.require_auth().get_all_wallet_balances()

    def get_positions(self, product_id: int | None = None, symbol: str | None = None) -> list[dict[str, Any]]:
        """
        Delta docs: GET /v2/positions/margined with empty params for all open positions.
        Per-product: GET /v2/positions?product_id=... (size/entry only — pass symbol for mark).
        """
        from delta_rest_client.delta_rest_client import parseResponse

        client = self.require_auth()
        if product_id is not None:
            result = client.request(
                "GET",
                "/v2/positions",
                query={"product_id": product_id},
                auth=True,
            )
        else:
            # query must be None (not {}) — empty dict adds "?" to signature and causes mismatch
            result = client.request(
                "GET",
                "/v2/positions/margined",
                query=None,
                auth=True,
            )
        parsed = parseResponse(result)
        positions = self._normalize_positions(parsed, product_id=product_id)
        return [
            _sanitize_for_json(self._map_position_row(p, product_id=product_id, symbol=symbol))
            for p in positions
            if isinstance(p, dict)
        ]

    def fetch_mark_price(self, symbol: str) -> float | None:
        try:
            ticker = self.client.get_ticker(symbol)
            mark = self._parse_amount(ticker.get("mark_price") or ticker.get("spot_price"))
            return mark if mark > 0 else None
        except Exception:
            return None

    def _map_position_row(
        self,
        pos: dict[str, Any],
        product_id: int | None = None,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        row = dict(pos)
        if product_id is not None and not row.get("product_id"):
            row["product_id"] = product_id
        sym = symbol or row.get("product_symbol") or row.get("symbol")
        if sym:
            row.setdefault("product", {"symbol": sym})
            row.setdefault("product_symbol", sym)
        try:
            row["size"] = int(float(row.get("size") or 0))
        except (TypeError, ValueError):
            row["size"] = 0

        realized = self._parse_amount(row.get("realized_cashflow"))
        unrealized = self._parse_amount(row.get("unrealized_cashflow"))
        row["realized_cashflow"] = str(realized)
        row["unrealized_cashflow"] = str(unrealized)
        row["total_cashflow"] = str(realized + unrealized)

        mark = self._parse_amount(row.get("mark_price"))
        if sym and row["size"] != 0 and mark <= 0:
            fetched = self.fetch_mark_price(sym)
            if fetched is not None:
                mark = fetched
        row["mark_price"] = str(mark) if mark > 0 else ""
        return row

    @staticmethod
    def _parse_amount(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _normalize_positions(parsed: Any, product_id: int | None = None) -> list[dict[str, Any]]:
        if not parsed:
            return []
        if isinstance(parsed, list):
            return [p for p in parsed if isinstance(p, dict)]
        if isinstance(parsed, dict):
            if "running" in parsed and isinstance(parsed["running"], list):
                return [p for p in parsed["running"] if isinstance(p, dict)]
            if "size" in parsed or "entry_price" in parsed or product_id is not None:
                return [parsed]
            values = [v for v in parsed.values() if isinstance(v, dict)]
            if values:
                return values
        return []

    def get_open_orders(self, product_id: int | None = None) -> list[dict[str, Any]]:
        query = {"product_id": product_id, "state": "open"} if product_id else {"state": "open"}
        return self.require_auth().get_live_orders(query=query)

    def place_order(
        self,
        product_id: int,
        size: int,
        side: str,
        limit_price: str | None = None,
        order_type: str = "limit_order",
        post_only: str = "false",
        reduce_only: str = "false",
    ) -> dict[str, Any]:
        ot = OrderType.MARKET if order_type == "market_order" else OrderType.LIMIT
        return self.require_auth().place_order(
            product_id=product_id,
            size=size,
            side=side,
            limit_price=limit_price,
            order_type=ot,
            post_only=post_only,
            reduce_only=reduce_only,
        )

    def cancel_order(self, product_id: int, order_id: int) -> dict[str, Any]:
        return self.require_auth().cancel_order(product_id, order_id)

    def cancel_all_orders(self) -> dict[str, Any]:
        return self.require_auth().cancel_all_orders()

    def get_order_history(self, **query: Any) -> dict[str, Any]:
        return self.require_auth().order_history(query=query)


_delta_service: DeltaService | None = None


def _sanitize_for_json(value: Any) -> Any:
    """Ensure values are JSON-serializable (Starlette rejects NaN/Inf)."""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, str):
        try:
            parsed = float(value)
            if math.isnan(parsed) or math.isinf(parsed):
                return None
        except ValueError:
            pass
        return value
    if isinstance(value, dict):
        return {str(k): _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_json(v) for v in value]
    return value


def get_delta_service() -> DeltaService:
    global _delta_service
    if _delta_service is None:
        creds = load_credentials()
        if creds:
            _delta_service = DeltaService(**creds)
        else:
            _delta_service = DeltaService()
    return _delta_service


def update_delta_service(api_key: str, api_secret: str, env: str) -> DeltaService:
    global _delta_service
    save_credentials(api_key, api_secret, env)
    _delta_service = DeltaService(api_key=api_key, api_secret=api_secret, env=env)
    return _delta_service
