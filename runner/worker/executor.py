"""
Worker executor - runs inside isolated containers.
Receives code via HTTP POST and executes it, returning stdout/stderr.
"""
import subprocess
import sys
from flask import Flask, request, jsonify

app = Flask(__name__)

TIMEOUT = 10  # seconds


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


@app.route("/execute", methods=["POST"])
def execute():
    """Execute Python code and return the result."""
    data = request.get_json()
    
    if not data or "code" not in data:
        return jsonify({"error": "missing 'code' field"}), 400
    
    code = data["code"]
    timeout = data.get("timeout", TIMEOUT)
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return jsonify({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        })
    
    except subprocess.TimeoutExpired:
        return jsonify({"error": "execution timed out"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
