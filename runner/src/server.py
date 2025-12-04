import os
import subprocess
from flask import Flask, request, jsonify
from static_check import ast_static_check

app = Flask(__name__)

PYTHON_EXEC = os.environ.get("PYTHON_EXECUTABLE", "python3")
STATIC_CHECK = os.environ.get("STATIC_CHECK", "false").lower() == "true"
TIMEOUT = int(os.environ.get("TIMEOUT", "10"))

@app.route('/run-code', methods=['POST'])
def run_code_executor():
    data = request.get_json(silent=True)
    if not data or 'code' not in data:
        return jsonify({'error': 'missing code'}), 400

    code = data['code']

    if STATIC_CHECK:
        static_issues = ast_static_check(code)
        if static_issues:
            return jsonify({
                'error': 'forbidden constructs found',
                'details': static_issues
            }), 403

    try:
        result = subprocess.run(
            [PYTHON_EXEC, "-c", code],
            capture_output=True,
            text=True,
            timeout=TIMEOUT
        )

        return jsonify({
            'stdout': result.stdout,
            'stderr': result.stderr,
            'return_code': result.returncode,
        }), 200

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'execution timed out'}), 408

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))
