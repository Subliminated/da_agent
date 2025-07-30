# FLASK app to create a service to execute code
from flask import Flask, request, jsonify
import subprocess
import tempfile
import os
import sys

app = Flask(__name__)

@app.route("/run", methods=["POST"])
def run_code():
    # `code` should be a string containing Python code
    code = request.json.get("code", "")
    try:
        # Create a temporary file to hold the code
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(code.encode())
            f.flush()
            script_path = f.name

        # Install pip dependencies first if any
        for line in code.splitlines():
            if "pip install" in line:
                subprocess.run(line.strip().split(), check=True, timeout=10)

        # Run the script
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        return jsonify({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Code execution timed out"}), 408

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if os.path.exists(script_path):
            os.remove(script_path)

@app.route("/")
def health():
    return "Code Runner API is up!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=True)
