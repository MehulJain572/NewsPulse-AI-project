import json
import os
from urllib import error, request
#this code pushes headlines to groq ai and brings json files from there
from env_utils import load_local_env

load_local_env()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _normalize_action(raw_action):
    action = (raw_action or "").strip().upper()
    if action == "HOLD":
        return "IGNORE"
    if action not in {"SELL", "BUY", "IGNORE"}:
        return "IGNORE"
    return action


def _normalize_analysis(payload):
    panic_score = payload.get("panic_score", 0)

    try:
        panic_score = int(round(float(panic_score)))
    except (TypeError, ValueError):
        panic_score = 0

    panic_score = max(0, min(100, panic_score))

    return {
        "company": str(payload.get("company", "Market")).strip() or "Market",
        "panic_score": panic_score,
        "impact": str(payload.get("impact", "NEUTRAL")).strip().upper(),
        "action": _normalize_action(payload.get("action") or payload.get("recommendation")),
        "reason": str(payload.get("reason", "")).strip() or "No reason provided.",
    }


def analyze_news(news_item):
    headline = news_item["headline"].strip()[:300]
    source = news_item["source"]
    groq_api_key = os.getenv("GROQ_API_KEY")

    if not groq_api_key:
        print("[AI ERROR] GROQ_API_KEY is missing.")
        return None

    system_prompt = (
        "You analyze financial headlines for Indian market trading. "
        "Return only minified JSON with keys: company, panic_score, impact, action, reason. "
        "impact must be NEGATIVE, POSITIVE, or NEUTRAL. "
        "action must be SELL, BUY, or IGNORE. "
        "panic_score must be an integer from 0 to 100."
    )

    user_prompt = (
        f"Source: {source}\n"
        f"Headline: {headline}\n"
        "Decide the most affected company. If none is specific, use Market."
    )

    try:
        req = request.Request(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "NewsPulseAI/1.0 (+local-debug)",
            },
            data=json.dumps({
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "max_tokens": 120,
            }).encode("utf-8"),
            method="POST",
        )
        with request.urlopen(req, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        payload = json.loads(content)
        return _normalize_analysis(payload)
    except error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = "<unable to read response body>"
        print(f"[AI ERROR] HTTP {exc.code}: {exc.reason} | body={body[:500]}")
        return None
    except Exception as exc:
        print(f"[AI ERROR] {exc}")
        return None


if __name__ == "__main__":
    test_item = {
        "source": "manual",
        "headline": "Hindenburg report claims massive financial fraud in Adani Group",
    }
    print(json.dumps(analyze_news(test_item), indent=2))
