from flask import render_template, request, redirect, jsonify
import sqlite3
from datetime import datetime


pump_mode = {"mode": "auto"}  
pump_state = {"value": 0}     

def auto_control_pump(soil_value, threshold=1800):
    if soil_value > threshold:
        pump_state["value"] = 1
    else:
        pump_state["value"] = 0

#routes
def register_routes(app):
    @app.route('/')
    def index():
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT timestamp, soil, pump FROM sensor_data ORDER BY id DESC LIMIT 10')
        rows = c.fetchall()
        conn.close()
        return render_template(
            'index.html',
            state=app.config['system_state'],
            data=rows,
            threshold=app.config['get_threshold'](),
            current_session_id=app.current_session_id
        )

    @app.route('/config', methods=['POST'])
    def config():
        new_threshold = int(request.form['threshold'])
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('UPDATE settings SET value = ? WHERE key = ?', (new_threshold, "threshold"))
        conn.commit()
        conn.close()
        return redirect('/')

    @app.route('/threshold')
    def threshold_value():
        return {"threshold": app.config['get_threshold']()}

    @app.route('/open', methods=['POST'])
    def open_system():
        app.config['system_state']['initialized'] = True
        return redirect('/')

    @app.route('/start', methods=['POST'])
    def start_monitoring():
        if app.config['system_state']['initialized']:
            app.config['system_state']['monitoring'] = True
            app.is_logging_active = True
            app.current_session_id += 1
        return redirect('/')

    @app.route('/stop', methods=['POST'])
    def stop_monitoring():
        app.config['system_state']['monitoring'] = False
        app.is_logging_active = False
        return redirect('/')

    @app.route('/close', methods=['POST'])
    def close_system():
        app.config['system_state']['monitoring'] = False
        app.config['system_state']['initialized'] = False
        app.is_logging_active = False
        return redirect('/')

    @app.route('/status')
    def get_status():
        return {
            "initialized": app.config['system_state']['initialized'],
            "monitoring": app.config['system_state']['monitoring'],
            "threshold": app.config['get_threshold'](),
            "mode": pump_mode["mode"],         
            "pump": pump_state["value"]       
        }


    @app.route('/data', methods=['POST'])
    def receive_data():
        if app.config['system_state']['monitoring']:
            data = request.get_json()
            soil = int(data.get('soil'))

            
            if pump_mode["mode"] == "auto":
                auto_control_pump(soil, threshold=app.config['get_threshold']())

            pump = pump_state["value"]

            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('''
                INSERT INTO sensor_data (timestamp, soil, pump, session_id)
                VALUES (?, ?, ?, ?)
            ''', (datetime.now().isoformat(), soil, pump, app.current_session_id))
            conn.commit()
            conn.close()
            return "OK", 200
        else:
            return "Monitoring not active", 403

    @app.route('/chart')
    def chart_page():
        session = request.args.get('session', type=int)
        return render_template('chart.html', session=session)

    @app.route('/view')
    def view_session():
        session = request.args.get('session', type=int)
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT id, timestamp, soil, pump FROM sensor_data WHERE session_id = ? ORDER BY id DESC', (session,))
        rows = c.fetchall()
        conn.close()
        return render_template('view.html', data=rows, session=session)

    @app.route('/download')
    def download_csv():
        session = request.args.get('session', type=int)
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT timestamp, soil, pump FROM sensor_data WHERE session_id = ?', (session,))
        rows = c.fetchall()
        conn.close()

        csv_data = ["Timestamp,Soil,Pump"] + [f"{r[0]},{r[1]},{r[2]}" for r in rows]
        response = app.response_class("\n".join(csv_data), mimetype='text/csv')
        response.headers['Content-Disposition'] = f'attachment; filename=session_{session}.csv'
        return response

    @app.route('/api/set-mode', methods=['POST'])
    def set_mode():
        mode = request.json.get("mode")
        if mode in ["auto", "manual"]:
            pump_mode["mode"] = mode
            return jsonify({"status": "ok", "mode": mode})
        return jsonify({"status": "error", "message": "Invalid mode"}), 400

    @app.route('/api/set-pump', methods=['POST'])
    def set_pump():
        if pump_mode["mode"] != "manual":
            return jsonify({"status": "error", "message": "ssak kezi modban engedelyezett"}), 400
        value = request.json.get("value")
        if value in [0, 1]:
            pump_state["value"] = value
            return jsonify({"status": "ok", "pump": value})
        return jsonify({"status": "error", "message": "ervenytelen ertek"}), 400

    @app.route('/api/pump-status')
    def get_pump_status():
        return jsonify({"mode": pump_mode["mode"], "pump": pump_state["value"]})

    @app.route('/api/latest-data')
    def latest_data():
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT soil, pump FROM sensor_data ORDER BY id DESC LIMIT 1')
        row = c.fetchone()
        conn.close()
        if row:
            return jsonify({'soil': row[0], 'pump': row[1]})
        else:
            return jsonify({'soil': None, 'pump': None})

    @app.route('/api/latest-list')
    def latest_list():
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT timestamp, soil, pump FROM sensor_data ORDER BY id DESC LIMIT 10')
        rows = c.fetchall()
        conn.close()
        data = [{"timestamp": r[0], "soil": r[1], "pump": r[2]} for r in rows[::-1]]
        return jsonify(data)

    @app.route('/api/session-data/<int:session_id>')
    def session_data(session_id):
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT id, timestamp, soil, pump FROM sensor_data WHERE session_id = ? ORDER BY id DESC LIMIT 20', (session_id,))
        rows = c.fetchall()
        conn.close()
        return jsonify([
            {"id": r[0], "timestamp": r[1], "soil": r[2], "pump": r[3]} for r in rows[::-1]
        ])

    @app.route('/chart-data')
    def chart_data():
        session = request.args.get('session', type=int)
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT timestamp, soil, pump FROM sensor_data WHERE session_id = ? ORDER BY id', (session,))
        rows = c.fetchall()
        conn.close()

        data = {
            "labels": [r[0][-8:] for r in rows],
            "soil": [r[1] for r in rows],
            "pump": [r[2] for r in rows]
        }
        return jsonify(data)
