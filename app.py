import os
import threading

from env_utils import load_local_env
load_local_env()

import agent
import dashboard

app = dashboard.app

if __name__ == "__main__":
    t = threading.Thread(target=agent.run_news_pulse_agent, daemon=True)
    t.start()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").strip().lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
