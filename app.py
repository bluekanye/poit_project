from flask import Flask, request, jsonify
import sqlite3
import os
from routes import register_routes

app = Flask(__name__)


pump_mode = {"mode": "auto"}  
pump_state = {"value": 0}     


system_state = {
    "initialized": False,
    "monitoring": False
}


app.current_session_id = 0
app.is_logging_active = False

#database
def init_db():
    if not os.path.exists('database.db'):
        open('database.db', 'w').close()

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

   
    c.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            soil INTEGER,
            pump INTEGER,
            session_id INTEGER DEFAULT 0
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value INTEGER
        )
    ''')
    c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ("threshold", 2000))
    conn.commit()

    # next session id
    c.execute('SELECT MAX(session_id) FROM sensor_data')
    result = c.fetchone()
    app.current_session_id = (result[0] ) if result and result[0] is not None else 0

    conn.close()

# threshold
def get_threshold():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', ("threshold",))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 2000

# pump control
def auto_control_pump(soil_value, threshold=None):
    if threshold is None:
        threshold = get_threshold()
    if soil_value > threshold:
        pump_state["value"] = 1
    else:
        pump_state["value"] = 0
   


app.config['system_state'] = system_state
app.config['init_db'] = init_db
app.config['get_threshold'] = get_threshold
app.config['pump_mode'] = pump_mode
app.config['pump_state'] = pump_state
app.config['auto_control_pump'] = auto_control_pump

# start
if __name__ == '__main__':
    init_db()
    register_routes(app)
    app.run(host='0.0.0.0', port=5000)
