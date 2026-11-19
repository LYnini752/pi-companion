"""Small, dependency-free OpenAI-compatible Chat Completions client."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


class ProviderError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("Endpoint redirected; configure the final URL explicitly.")


def validate_model(spec):
    if not isinstance(spec, dict):
        raise ValueError("Model configuration must be an object")
    for field in ("name", "model", "base_url"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            raise ValueError(f"Missing model field: {field}")
    url = urllib.parse.urlsplit(spec["base_url"])
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("base_url must not contain credentials, query or fragment")
    if not url.hostname or (url.scheme != "https" and not (
        url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
    )):
        raise ValueError("Use HTTPS, or HTTP on localhost for a local model")
    if "api_key" in spec:
        raise ValueError("Use api_key_env, never a literal API key in config")
    key_env = spec.get("api_key_env", "")
    if not isinstance(key_env, str):
        raise ValueError("api_key_env must be a string")
    options = spec.get("request_options", {})
    if not isinstance(options, dict) or set(options) - {"chat_template_kwargs"}:
        raise ValueError("Only chat_template_kwargs is accepted in request_options")
    template = options.get("chat_template_kwargs", {})
    if not isinstance(template, dict) or set(template) - {"enable_thinking"} or any(
        not isinstance(v, bool) for v in template.values()
    ):
        raise ValueError("chat_template_kwargs accepts only boolean enable_thinking")


def chat(spec, messages, *, temperature=0.3, max_tokens=1500, timeout=120):
    validate_model(spec)
    key_env = spec.get("api_key_env")
    key = os.environ.get(key_env, "") if key_env else ""
    if key_env and not key:
        raise ProviderError(f"Missing environment variable: {key_env}")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = json.dumps({"model": spec["model"], "messages": messages,
                       "temperature": temperature, "max_tokens": max_tokens,
                       "stream": False, **spec.get("request_options", {})}).encode()
    request = urllib.request.Request(spec["base_url"].rstrip("/") + "/chat/completions",
                                     data=data, headers=headers)
    start = time.monotonic()
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ProviderError("Response exceeded 4 MB")
        result = json.loads(raw)
        choice = result["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ProviderError("Answer truncated; increase max_tokens or shorten the prompt")
        content = choice["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Model returned an empty or non-text answer")
        return {"text": content, "seconds": round(time.monotonic() - start, 3),
                "usage": result.get("usage", {}), "model": result.get("model", spec["model"])}
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"Model API returned HTTP {exc.code}; check credentials and model support") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProviderError("Cannot reach model API or request timed out") from None
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderError("Invalid Chat Completions response") from None


def parse_json(text):
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value
