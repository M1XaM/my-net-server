import os
import subprocess
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/run-code', methods=['POST'])
def run_code_executor():
    data = request.get_json(silent=True)
    if not data or 'code' not in data:
        return jsonify({'error': 'missing code'}), 400

    code = data['code']

    try:
        # Use the same Python interpreter that's running this process
        python_exe = os.environ.get("PYTHON_EXECUTABLE", "python3")

        result = subprocess.run(
            [python_exe, "-c", code],
            capture_output=True,
            text=True,
            timeout=3  # seconds
        )

        return jsonify({
            'stdout': result.stdout,
            'stderr': result.stderr,
            'return_code': result.returncode
        }), 200

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'execution timed out'}), 408

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT', '8080'))
