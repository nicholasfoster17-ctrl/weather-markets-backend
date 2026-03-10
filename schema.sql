from copy import deepcopy
import os

try:
    import psycopg
except ImportError:
    psycopg = None

class InMemoryStore:
    def __init__(self):
        self.reset()

    def reset(self):
        self.wallet = {
            "fake_cash_balance": 2500.00,
            "buying_power": 2500.00,
            "realized_pnl": 0.0
        }
        self.orders = []
        self.fills = []
        self.open_positions = []
        self.closed_positions = []
        self.activity = []

    def get_wallet(self):
        return deepcopy(self.wallet)

    def update_wallet(self, **kwargs):
        self.wallet.update(kwargs)

    def get_orders(self):
        return deepcopy(self.orders)

    def get_fills(self):
        return deepcopy(self.fills)

    def get_open_positions(self):
        return deepcopy(self.open_positions)

    def get_closed_positions(self):
        return deepcopy(self.closed_positions)

    def get_activity(self):
        return deepcopy(self.activity[:30])

    def create_order(self, order):
        item = {"id": f"ord_{len(self.orders)+1}", **order}
        self.orders.insert(0, item)
        return deepcopy(item)

    def create_fill(self, fill):
        item = {"id": f"fill_{len(self.fills)+1}", **fill}
        self.fills.insert(0, item)
        return deepcopy(item)

    def create_open_position(self, position):
        item = {"id": f"pos_{len(self.open_positions)+len(self.closed_positions)+1}", **position}
        self.open_positions.append(item)
        return deepcopy(item)

    def remove_open_position(self, position_id):
        for i, pos in enumerate(self.open_positions):
            if pos["id"] == position_id:
                return self.open_positions.pop(i)
        return None

    def create_closed_position(self, position):
        self.closed_positions.insert(0, position)
        return deepcopy(position)

    def add_activity(self, message):
        self.activity.insert(0, {"message": message})
        self.activity = self.activity[:30]


class PostgresStore:
    def __init__(self, database_url: str):
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgresStore but is not installed")
        self.database_url = database_url
        self._ensure_wallet_seed()

    def _conn(self):
        return psycopg.connect(self.database_url)

    def _ensure_wallet_seed(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM wallets")
                count = cur.fetchone()[0]
                if count == 0:
                    cur.execute(
                        "INSERT INTO wallets (fake_cash_balance, buying_power, realized_pnl) VALUES (%s, %s, %s)",
                        (2500.00, 2500.00, 0.0)
                    )
            conn.commit()

    def reset(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM fills")
                cur.execute("DELETE FROM orders")
                cur.execute("DELETE FROM open_positions")
                cur.execute("DELETE FROM closed_positions")
                cur.execute("DELETE FROM activity")
                cur.execute("UPDATE wallets SET fake_cash_balance=%s, buying_power=%s, realized_pnl=%s", (2500.00, 2500.00, 0.0))
            conn.commit()

    def get_wallet(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT fake_cash_balance, buying_power, realized_pnl FROM wallets ORDER BY id ASC LIMIT 1")
                row = cur.fetchone()
                return {
                    "fake_cash_balance": float(row[0]),
                    "buying_power": float(row[1]),
                    "realized_pnl": float(row[2])
                }

    def update_wallet(self, **kwargs):
        wallet = self.get_wallet()
        wallet.update(kwargs)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE wallets SET fake_cash_balance=%s, buying_power=%s, realized_pnl=%s",
                    (wallet["fake_cash_balance"], wallet["buying_power"], wallet["realized_pnl"])
                )
            conn.commit()

    def get_orders(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT external_id, market_id, label, side, qty, price_cents, status, cost_dollars, created_at FROM orders ORDER BY id DESC")
                rows = cur.fetchall()
                return [{
                    "id": r[0], "market_id": r[1], "label": r[2], "side": r[3],
                    "qty": r[4], "price_cents": r[5], "status": r[6],
                    "cost_dollars": float(r[7]), "timestamp": str(r[8])
                } for r in rows]

    def get_fills(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT external_id, order_external_id, market_id, qty, fill_price_cents, created_at FROM fills ORDER BY id DESC")
                rows = cur.fetchall()
                return [{
                    "id": r[0], "order_id": r[1], "market_id": r[2],
                    "qty": r[3], "fill_price_cents": r[4], "timestamp": str(r[5])
                } for r in rows]

    def get_open_positions(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT external_id, market_id, label, side, qty, avg_price_cents, opened_cost_dollars, opened_at FROM open_positions ORDER BY id ASC")
                rows = cur.fetchall()
                return [{
                    "id": r[0], "market_id": r[1], "label": r[2], "side": r[3],
                    "qty": r[4], "avg_price_cents": r[5], "opened_cost_dollars": float(r[6]),
                    "opened_at": str(r[7])
                } for r in rows]

    def get_closed_positions(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT external_id, market_id, label, side, qty, avg_price_cents, exit_price_cents, realized_pnl_dollars, closed_at FROM closed_positions ORDER BY id DESC")
                rows = cur.fetchall()
                return [{
                    "id": r[0], "market_id": r[1], "label": r[2], "side": r[3],
                    "qty": r[4], "avg_price_cents": r[5], "exit_price_cents": r[6],
                    "realized_pnl_dollars": float(r[7]), "closed_at": str(r[8])
                } for r in rows]

    def get_activity(self):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT message, created_at FROM activity ORDER BY id DESC LIMIT 30")
                rows = cur.fetchall()
                return [{"message": r[0], "timestamp": str(r[1])} for r in rows]

    def create_order(self, order):
        external_id = f"ord_{len(self.get_orders())+1}"
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO orders (external_id, market_id, label, side, qty, price_cents, status, cost_dollars) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (external_id, order["market_id"], order["label"], order["side"], order["qty"], order["price_cents"], order["status"], order["cost_dollars"])
                )
            conn.commit()
        return {"id": external_id, **order}

    def create_fill(self, fill):
        external_id = f"fill_{len(self.get_fills())+1}"
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO fills (external_id, order_external_id, market_id, qty, fill_price_cents) VALUES (%s,%s,%s,%s,%s)",
                    (external_id, fill["order_id"], fill["market_id"], fill["qty"], fill["fill_price_cents"])
                )
            conn.commit()
        return {"id": external_id, **fill}

    def create_open_position(self, position):
        external_id = f"pos_{len(self.get_open_positions()) + len(self.get_closed_positions()) + 1}"
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO open_positions (external_id, market_id, label, side, qty, avg_price_cents, opened_cost_dollars) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (external_id, position["market_id"], position["label"], position["side"], position["qty"], position["avg_price_cents"], position["opened_cost_dollars"])
                )
            conn.commit()
        return {"id": external_id, **position}

    def remove_open_position(self, position_id):
        positions = self.get_open_positions()
        target = next((p for p in positions if p["id"] == position_id), None)
        if not target:
            return None
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM open_positions WHERE external_id=%s", (position_id,))
            conn.commit()
        return target

    def create_closed_position(self, position):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO closed_positions (external_id, market_id, label, side, qty, avg_price_cents, exit_price_cents, realized_pnl_dollars) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (position["id"], position["market_id"], position["label"], position["side"], position["qty"], position["avg_price_cents"], position["exit_price_cents"], position["realized_pnl_dollars"])
                )
            conn.commit()
        return position

    def add_activity(self, message):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO activity (message) VALUES (%s)", (message,))
            conn.commit()
