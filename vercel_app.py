from flask import Flask, send_from_directory, jsonify, request
import os
import sys

app = Flask(__name__, static_folder='webapp')

@app.route('/')
def index():
    return send_from_directory('webapp', 'index.html')

@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('webapp', path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=5000)
