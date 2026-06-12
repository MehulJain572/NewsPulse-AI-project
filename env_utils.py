import os
from pathlib import Path


def load_local_env(path=".env"):
    env_path = Path(path)
    if not env_path.exists():
        return False

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value

    return True


def env_status(name):
    value = os.getenv(name)
    if not value:
        return "missing"
    if len(value) <= 8:
        return "loaded"
    return f"loaded ({value[:4]}...{value[-4:]})"
