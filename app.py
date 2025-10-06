import os
import threading
import time
from flask import Flask, jsonify, render_template, request
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

app = Flask(__name__)

# Initialize Firebase
cred = credentials.Certificate('firebase-key.json')
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Global variables for background service
trades_data = []
last_check_time = datetime.now()

class OnlineFirebaseService:
    def __init__(self):
        self.trades_collection = 'trades'
        
    def process_uploaded_trades(self, trades_list):
        """Process trades uploaded via API"""
        uploaded_count = 0
        
        for trade_data in trades_list:
            try:
                # Create unique trade ID
                trade_id = f"{trade_data['symbol']}_{trade_data['timestamp'].replace(' ', '_').replace(':', '-').replace('.', '_')}"
                
                # Check if trade already exists
                doc_ref = db.collection(self.trades_collection).document(trade_id)
                if not doc_ref.get().exists:
                    trade_data['firebase_timestamp'] = firestore.SERVER_TIMESTAMP
                    doc_ref.set(trade_data)
                    uploaded_count += 1
                    print(f"✅ Uploaded: {trade_data['symbol']} {trade_data['trade_type']} - ${trade_data['profit']}")
                    
            except Exception as e:
                print(f"Error processing trade: {e}")
                continue
                
        return uploaded_count

# Initialize service
firebase_service = OnlineFirebaseService()

class ForexDashboard:
    def __init__(self):
        self.trades_collection = 'trades'
    
    def get_trades_from_firebase(self, limit=50):
        try:
            trades_ref = db.collection(self.trades_collection)
            trades_ref = trades_ref.order_by('timestamp', direction=firestore.Query.DESCENDING)
            trades_ref = trades_ref.limit(limit)
            
            trades = []
            for doc in trades_ref.stream():
                trade_data = doc.to_dict()
                if 'firebase_timestamp' in trade_data:
                    del trade_data['firebase_timestamp']
                trades.append(trade_data)
            
            return trades
            
        except Exception as e:
            print(f"Error getting trades: {e}")
            return []
    
    def calculate_stats(self, trades):
        if not trades:
            return {
                'total_trades': 0,
                'total_profit': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'avg_profit': 0,
                'last_trade_time': 'No trades yet'
            }
        
        total_trades = len(trades)
        total_profit = sum(float(trade.get('profit', 0)) for trade in trades)
        winning_trades = sum(1 for trade in trades if float(trade.get('profit', 0)) > 0)
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        avg_profit = total_profit / total_trades if total_trades > 0 else 0
        
        last_trade_time = 'No trades yet'
        if trades:
            try:
                last_trade_time = trades[0]['timestamp']
            except:
                last_trade_time = 'Unknown'
        
        return {
            'total_trades': total_trades,
            'total_profit': round(total_profit, 2),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'avg_profit': round(avg_profit, 2),
            'last_trade_time': last_trade_time
        }

dashboard = ForexDashboard()

# Routes
@app.route('/')
def home():
    return render_template('dashboard.html')

@app.route('/api/stats')
def get_stats():
    try:
        trades = dashboard.get_trades_from_firebase(1000)
        stats = dashboard.calculate_stats(trades)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/trades')
def get_trades():
    try:
        limit = request.args.get('limit', 50, type=int)
        trades = dashboard.get_trades_from_firebase(limit)
        return jsonify(trades)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/upload-trades', methods=['POST'])
def upload_trades():
    """API endpoint to receive trades from local EA system"""
    try:
        trade_data = request.json
        
        if isinstance(trade_data, list):
            uploaded_count = firebase_service.process_uploaded_trades(trade_data)
        else:
            uploaded_count = firebase_service.process_uploaded_trades([trade_data])
            
        return jsonify({
            'success': True,
            'uploaded_count': uploaded_count,
            'message': f'Successfully uploaded {uploaded_count} trades'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to upload trades'
        })

@app.route('/api/test')
def test_firebase():
    try:
        trades = dashboard.get_trades_from_firebase(1)
        trade_count = len(dashboard.get_trades_from_firebase(1000))
        
        return jsonify({
            'firebase_connected': True,
            'trade_count': trade_count,
            'sample_trade': trades[0] if trades else None,
            'message': 'Firebase connection successful',
            'server_time': datetime.now().isoformat(),
            'status': 'Online and running'
        })
        
    except Exception as e:
        return jsonify({
            'firebase_connected': False,
            'error': str(e),
            'message': 'Firebase connection failed'
        })

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'message': 'Forex Dashboard is running'
    })

# Run the app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting Forex Dashboard on port {port}")
    print("🔥 Firebase integration enabled")
    print("📊 Dashboard ready for live trading data")
    app.run(host='0.0.0.0', port=port, debug=False)