import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from storage import InMemoryStore, PostgresStore

APP_PORT = int(os.environ.get("PORT", os.environ.get("APP_PORT", "8080")))
APP_STORAGE_MODE = os.environ.get("APP_STORAGE_MODE", "memory").lower()
DATABASE_URL = os.environ.get("DATABASE_URL", "")

MARKETS = [
    {"market_id":"dtw-high-50-54","label":"DTW High 50–54°F","market_family":"weather","market_type":"temperature","category":"Detroit Weather","price":48,"bid":47,"ask":49,"volume":1240,"status":"open","updated_at":"2026-03-09T14:00:00Z"},
    {"market_id":"dtw-high-55-59","label":"DTW High 55–59°F","market_family":"weather","market_type":"temperature","category":"Detroit Weather","price":35,"bid":34,"ask":36,"volume":980,"status":"open","updated_at":"2026-03-09T14:00:00Z"},
    {"market_id":"dtw-low-31-35","label":"DTW Low 31–35°F","market_family":"weather","market_type":"temperature","category":"Detroit Weather","price":52,"bid":51,"ask":53,"volume":860,"status":"open","updated_at":"2026-03-09T14:00:00Z"},
    {"market_id":"dtw-precip-0-00-0-24","label":"Detroit precipitation 0.00 to 0.24 in","market_family":"weather","market_type":"detroit_precipitation","category":"Detroit Precipitation","price":22,"bid":21,"ask":23,"volume":740,"status":"open","updated_at":"2026-03-09T14:00:00Z"},
    {"market_id":"dtw-precip-0-25-0-99","label":"Detroit precipitation 0.25 to 0.99 in","market_family":"weather","market_type":"detroit_precipitation","category":"Detroit Precipitation","price":44,"bid":43,"ask":45,"volume":1310,"status":"open","updated_at":"2026-03-09T14:00:00Z"},
    {"market_id":"dtw-precip-1-00-1-99","label":"Detroit precipitation 1.00 to 1.99 in","market_family":"weather","market_type":"detroit_precipitation","category":"Detroit Precipitation","price":28,"bid":27,"ask":29,"volume":620,"status":"open","updated_at":"2026-03-09T14:00:00Z"},
    {"market_id":"tor-ef1","label":"Strongest Tornado 2026 EF1","market_family":"tornado","market_type":"tornado","category":"Tornado","price":26,"bid":25,"ask":27,"volume":1550,"status":"open","updated_at":"2026-03-09T14:00:00Z"},
    {"market_id":"tor-ef2","label":"Strongest Tornado 2026 EF2","market_family":"tornado","market_type":"tornado","category":"Tornado","price":41,"bid":40,"ask":42,"volume":1780,"status":"open","updated_at":"2026-03-09T14:00:00Z"},
    {"market_id":"tor-ef3","label":"Strongest Tornado 2026 EF3","market_family":"tornado","market_type":"tornado","category":"Tornado","price":54,"bid":53,"ask":55,"volume":1495,"status":"open","updated_at":"2026-03-09T14:00:00Z"},
    {"market_id":"ancestry-update-spring","label":"Ancestry update announced by Spring 2026","market_family":"ancestry","market_type":"ancestry_update_date","category":"Ancestry","price":31,"bid":30,"ask":32,"volume":540,"status":"open","updated_at":"2026-03-09T14:00:00Z"},
    {"market_id":"ancestry-update-fall","label":"Ancestry update announced by Fall 2026","market_family":"ancestry","market_type":"ancestry_update_date","category":"Ancestry","price":57,"bid":56,"ask":58,"volume":820,"status":"open","updated_at":"2026-03-09T14:00:00Z"},
    {"market_id":"ancestry-new-regions-3plus","label":"Ancestry adds 3 or more new regions","market_family":"ancestry","market_type":"ancestry_regions","category":"Ancestry","price":46,"bid":45,"ask":47,"volume":690,"status":"open","updated_at":"2026-03-09T14:00:00Z"}
]

READINESS = {
    "launch_readiness": "beta_ready",
    "storage_mode": APP_STORAGE_MODE,
    "database_configured": bool(DATABASE_URL),
    "remaining_major_work": [
        "run schema.sql against Postgres if using postgres mode",
        "connect real live weather data providers",
        "add real authentication and sessions",
        "wire frontend paper-trading actions to backend persistence"
    ]
}

def build_store():
    if APP_STORAGE_MODE == "postgres":
        if not DATABASE_URL:
            raise RuntimeError("APP_STORAGE_MODE=postgres but DATABASE_URL is not set")
        return PostgresStore(DATABASE_URL)
    return InMemoryStore()

STORE = build_store()

def now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def get_market(market_id):
    for market in MARKETS:
        if market["market_id"] == market_id:
            return market
    return None

def compute_unrealized_pnl():
    total = 0.0
    for pos in STORE.get_open_positions():
        market = get_market(pos["market_id"])
        last_price = market["price"] if market else pos["avg_price_cents"]
        total += (pos["qty"] * last_price / 100.0) - (pos["qty"] * pos["avg_price_cents"] / 100.0)
    return round(total, 2)

def top_movers():
    return sorted(MARKETS, key=lambda m: abs(m["ask"] - m["bid"]), reverse=True)[:5]

class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def read_json_body(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length).decode()
        return json.loads(raw) if raw else {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            return self.send_json(200, {
                "service": "weather-markets-backend",
                "phase": 70,
                "mode": "postgres_store_implementation",
                "storage_mode": APP_STORAGE_MODE
            })

        if path == "/api/health":
            return self.send_json(200, {
                "ok": True,
                "phase": 70,
                "mode": "backend_postgres_store_implementation",
                "storage_mode": APP_STORAGE_MODE,
                "timestamp": now_iso()
            })

        if path == "/api/markets":
            return self.send_json(200, {"markets": MARKETS, "count": len(MARKETS), "timestamp": now_iso()})

        if path == "/api/readiness-summary":
            return self.send_json(200, READINESS)

        if path == "/api/top-movers":
            return self.send_json(200, {"top_movers": top_movers(), "timestamp": now_iso()})

        if path == "/api/activity-feed":
            return self.send_json(200, {"activity": STORE.get_activity(), "timestamp": now_iso()})

        if path == "/api/wallet":
            wallet = dict(STORE.get_wallet())
            wallet["unrealized_pnl"] = compute_unrealized_pnl()
            return self.send_json(200, wallet)

        if path == "/api/portfolio":
            return self.send_json(200, {
                "wallet": {
                    **STORE.get_wallet(),
                    "unrealized_pnl": compute_unrealized_pnl()
                },
                "open_positions": STORE.get_open_positions(),
                "closed_positions": STORE.get_closed_positions(),
                "orders": STORE.get_orders(),
                "fills": STORE.get_fills(),
                "timestamp": now_iso()
            })

        return self.send_json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self.read_json_body()

        if path == "/api/reset-paper-trading":
            STORE.reset()
            STORE.add_activity("Paper trading state reset.")
            return self.send_json(200, {"ok": True, "message": "Paper trading state reset.", "timestamp": now_iso()})

        if path == "/api/paper-order":
            market_id = body.get("market_id")
            side = body.get("side", "BUY_YES")
            quantity = int(body.get("qty", 0))
            limit_price_cents = int(body.get("limit_price_cents", 0))

            market = get_market(market_id)
            if not market:
                return self.send_json(400, {"error": "market not found"})
            if quantity <= 0 or limit_price_cents <= 0:
                return self.send_json(400, {"error": "quantity and price must be positive"})

            cost = round(quantity * limit_price_cents / 100.0, 2)
            wallet = STORE.get_wallet()
            if cost > wallet["fake_cash_balance"]:
                return self.send_json(400, {"error": "insufficient fake cash", "required": cost, "available": wallet["fake_cash_balance"]})

            STORE.update_wallet(
                fake_cash_balance=round(wallet["fake_cash_balance"] - cost, 2),
                buying_power=round(wallet["fake_cash_balance"] - cost, 2)
            )

            order = STORE.create_order({
                "market_id": market_id,
                "label": market["label"],
                "side": side,
                "qty": quantity,
                "price_cents": limit_price_cents,
                "status": "filled",
                "cost_dollars": cost,
                "timestamp": now_iso()
            })
            fill = STORE.create_fill({
                "order_id": order["id"],
                "market_id": market_id,
                "qty": quantity,
                "fill_price_cents": limit_price_cents,
                "timestamp": now_iso()
            })
            position = STORE.create_open_position({
                "market_id": market_id,
                "label": market["label"],
                "side": side,
                "qty": quantity,
                "avg_price_cents": limit_price_cents,
                "opened_cost_dollars": cost,
                "opened_at": now_iso()
            })
            STORE.add_activity(f"Paper order filled for {market['label']} at {limit_price_cents}¢ x {quantity}.")
            return self.send_json(200, {
                "ok": True,
                "order": order,
                "fill": fill,
                "position": position,
                "wallet": {**STORE.get_wallet(), "unrealized_pnl": compute_unrealized_pnl()}
            })

        if path == "/api/close-position":
            position_id = body.get("position_id")
            pos = STORE.remove_open_position(position_id)
            if not pos:
                return self.send_json(400, {"error": "position not found"})

            market = get_market(pos["market_id"])
            exit_price_cents = market["price"] if market else pos["avg_price_cents"]
            proceeds = round(pos["qty"] * exit_price_cents / 100.0, 2)
            cost = round(pos["qty"] * pos["avg_price_cents"] / 100.0, 2)
            realized = round(proceeds - cost, 2)

            wallet = STORE.get_wallet()
            STORE.update_wallet(
                fake_cash_balance=round(wallet["fake_cash_balance"] + proceeds, 2),
                buying_power=round(wallet["fake_cash_balance"] + proceeds, 2),
                realized_pnl=round(wallet["realized_pnl"] + realized, 2)
            )
            closed = STORE.create_closed_position({
                **pos,
                "exit_price_cents": exit_price_cents,
                "realized_pnl_dollars": realized,
                "closed_at": now_iso()
            })
            STORE.add_activity(f"Position closed for {pos['label']} with realized PnL {realized:.2f}.")
            return self.send_json(200, {
                "ok": True,
                "closed_position": closed,
                "wallet": {**STORE.get_wallet(), "unrealized_pnl": compute_unrealized_pnl()}
            })

        return self.send_json(404, {"error": "not found"})

if __name__ == "__main__":
    print("Phase 70 backend running on", APP_PORT, "storage mode:", APP_STORAGE_MODE)
    HTTPServer(("0.0.0.0", APP_PORT), Handler).serve_forever()
