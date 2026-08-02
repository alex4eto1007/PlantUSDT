import os
from flask import Flask, send_from_directory

app = Flask(__name__, static_folder='webapp')

@app.route('/')
def index():
    return send_from_directory('webapp', 'index.html')

@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('webapp', path)

# Vercel requires this
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=5000)
