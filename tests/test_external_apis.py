import os
import requests

DEEPSEEK_URL = os.getenv("DEEPSEEK_API_URL")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENROUTER_URL = os.getenv("OPENROUTER_API_URL")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")


def assert_env(var, name):
    if not var:
        raise RuntimeError(f"Missing environment variable: {name}")


def test_deepseek_health_and_query():
    assert_env(DEEPSEEK_URL, "DEEPSEEK_API_URL")
    assert_env(DEEPSEEK_KEY, "DEEPSEEK_API_KEY")

    # Health / ping (adjust path as your API expects)
    r = requests.get(f"{DEEPSEEK_URL}/health", headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"}, timeout=10)
    assert r.status_code in (200, 204), f"Deepseek health check failed: {r.status_code} {r.text}"

    # Small example query (adjust endpoint/payload to match API)
    payload = {"query": "test"}
    r = requests.post(f"{DEEPSEEK_URL}/search", json=payload, headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"}, timeout=10)
    assert r.status_code == 200, f"Deepseek search failed: {r.status_code} {r.text}"
    data = r.json()
    assert isinstance(data, (dict, list)), "Deepseek returned unexpected body"


def test_openrouter_health_and_inference():
    assert_env(OPENROUTER_URL, "OPENROUTER_API_URL")
    assert_env(OPENROUTER_KEY, "OPENROUTER_API_KEY")

    # Health
    r = requests.get(f"{OPENROUTER_URL}/health", headers={"Authorization": f"Bearer {OPENROUTER_KEY}"}, timeout=10)
    assert r.status_code in (200, 204), f"OpenRouter health check failed: {r.status_code} {r.text}"

    # Example inference / route request (adjust to real endpoint)
    payload = {"text": "hello"}
    r = requests.post(f"{OPENROUTER_URL}/v1/route", json=payload, headers={"Authorization": f"Bearer {OPENROUTER_KEY}"}, timeout=15)
    assert r.status_code == 200, f"OpenRouter request failed: {r.status_code} {r.text}"
    data = r.json()
    assert data, "OpenRouter returned empty response"
