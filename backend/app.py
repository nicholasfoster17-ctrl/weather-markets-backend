import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

APP_PORT = int(os.environ.get("PORT", os.environ.get("APP_PORT", "8080")))

MARKETS = [
    {"market_id":"dtw-high-50-54","label":"DTW High 50–54°F","market_family":"weather","market_type":"temperature","price":48,"bid":47,"ask":49},
    {"market_id":"dtw-monthly-precip-2-50-to-3-49","label":"Detroit monthly precipitation 2.50 to 3.49 in","market_family":"weather","market_type":"detroit_precipitation","price":31,"bid":30,"ask":32},
    {"market_id":"tor-ef3","label":"Strongest Tornado 2026 EF3","market_family":"tornado","market_type":"tornado","price":54,"bid":53,"ask":55},
    {"market_id":"ancestry-update-date-2026-09-16-to-2026-10-15","label":"Ancestry update announced Sep 16 to Oct 15 2026","market_family":"ancestry","market_type":"ancestry_update_date","price":38,"bid":37,"ask":39}
]

READINESS = {
    "launch_readiness": "beta_ready",
    "remaining_major_work": [
        "replace SQLite/demo persistence with managed Postgres",
        "wire auth, KYC, and payments for real users",
        "connect production weather provider",
        "configure production monitoring and alerts"
    ]
}

class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_GET(self):
        if self.path == "/api/health":
            return self.send_json(200, {"ok": True, "phase": 51, "mode": "production_deployment_setup"})
        if self.path == "/api/markets":
            return self.send_json(200, {"markets": MARKETS})
        if self.path == "/api/readiness-summary":
            return self.send_json(200, READINESS)
        return self.send_json(404, {"error": "not found"})

if __name__ == "__main__":
    print("Phase 51 backend running on", APP_PORT)
    HTTPServer(("0.0.0.0", APP_PORT), Handler).serve_forever()
