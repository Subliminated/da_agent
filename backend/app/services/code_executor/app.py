# FLASK app to create a service to execute code
from flask import Flask, request, jsonify
import subprocess
import tempfile
import os
import sys
import errno

app = Flask(__name__)

DATA_MOUNT_PATH = os.getenv("DATA_MOUNT_PATH", "/data/raw_uploads")
ENFORCE_READ_ONLY_DATA = os.getenv("ENFORCE_READ_ONLY_DATA", "true").strip().lower() in {
    "1",
    "true",
    "yes",
}


def _validate_data_mount() -> dict[str, object]:
    if not os.path.isdir(DATA_MOUNT_PATH):
        raise RuntimeError(f"Data mount path is missing or not a directory: {DATA_MOUNT_PATH}")

    if not os.access(DATA_MOUNT_PATH, os.R_OK):
        raise RuntimeError(f"Data mount path is not readable: {DATA_MOUNT_PATH}")

    probe_path = os.path.join(DATA_MOUNT_PATH, ".write_probe")
    writable = False
    try:
        with open(probe_path, "x", encoding="utf-8") as probe:
            probe.write("probe")
        writable = True
    except OSError as exc:
        if exc.errno not in (errno.EROFS, errno.EACCES, errno.EPERM):
            raise RuntimeError(f"Unexpected mount check error at {DATA_MOUNT_PATH}: {exc}") from exc
    finally:
        if os.path.exists(probe_path):
            os.remove(probe_path)

    if ENFORCE_READ_ONLY_DATA and writable:
        raise RuntimeError(
            f"Data mount path is writable but must be read-only: {DATA_MOUNT_PATH}. "
            "Run container with a :ro bind mount."
        )

    return {
        "path": DATA_MOUNT_PATH,
        "readable": True,
        "read_only": not writable,
    }


MOUNT_STATUS = _validate_data_mount()

@app.route("/run", methods=["POST"])
def run_code():
    # `code` should be a string containing Python code
    code = request.json.get("code", "")
    script_path = ""
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

@app.route("/health")
def health():
    return jsonify({"status": "ok", "mount": MOUNT_STATUS})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=True)
