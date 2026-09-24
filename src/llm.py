import os, json, time
from openai import OpenAI   # pip install openai  (works for ALL providers below)

# Order = priority. Providers with no key in .env are skipped automatically.
# Model names change over time, so check each provider's model list if one errors.
PROVIDERS = [
    {"name": "groq",
    "base_url": "https://api.groq.com/openai/v1",
    "key_env": "GROQ_API_KEY",
    "model": "openai/gpt-oss-120b"},
    {"name": "gemini",
     "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
     "key_env": "GEMINI_API_KEY",
     "model": "gemini-2.5-flash"},
    {"name": "openrouter",
     "base_url": "https://openrouter.ai/api/v1",
     "key_env": "OPENROUTER_API_KEY",
     "model": "meta-llama/llama-3.3-70b-instruct:free"},
    {"name": "ollama",                       # local, no key needed
     "base_url": "http://localhost:11434/v1",
     "key_env": None,
     "model": "qwen2.5-coder:7b"},
]

def _available():
    for p in PROVIDERS:
        if p["key_env"] is None:
            # only use ollama if you explicitly enable it
            if os.getenv("USE_OLLAMA") == "1":
                yield p, "ollama"
        elif os.getenv(p["key_env"]):
            yield p, os.getenv(p["key_env"])

def call_llm(system: str, user: str, retries: int = 2) -> str:
    last_err = None
    for provider, key in _available():
        client = OpenAI(base_url=provider["base_url"], api_key=key)
        for attempt in range(retries):
            try:
                resp = client.chat.completions.create(
                    model=provider["model"],
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}],
                    temperature=0.2,
                )
                return resp.choices[0].message.content
            except Exception as e:          # rate limit, network, bad model name...
                last_err = e
                print(f"[llm] {provider['name']} failed: {e}")
                time.sleep(2 * (attempt + 1))   # wait, retry, then next provider
    raise RuntimeError(f"All LLM providers failed. Last error: {last_err}")

def call_llm_json(system: str, user: str) -> dict:
    text = call_llm(system + "\nReturn ONLY valid JSON. No markdown, no explanation.", user)
    # free models often add extra text, so grab just the {...} part
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in: {text[:200]}")
    return json.loads(text[start:end + 1])
