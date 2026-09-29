"""Bounded, provider-agnostic episode generation gateway.

The gateway follows the horror repository's provider/validation pattern while
keeping the Islamic generator's own schema, prompt, and semantic checks local.
Every outbound API request consumes one slot from LLM_MAX_CALLS.
"""
from __future__ import annotations

import json
import os
import random
import re
import time
from dataclasses import dataclass
from typing import Callable


LLM_RETRIES = max(1, int(os.getenv("LLM_RETRIES", "2")))
LLM_INVALID_RETRIES = max(1, int(os.getenv("LLM_INVALID_RETRIES", "2")))
LLM_MAX_CALLS = max(1, int(os.getenv("LLM_MAX_CALLS", "6")))
LLM_DEADLINE_SECONDS = max(30, int(os.getenv("LLM_DEADLINE_SECONDS", "300")))
LLM_REQUEST_TIMEOUT = max(10, int(os.getenv("LLM_REQUEST_TIMEOUT", "90")))
LLM_INITIAL_BUDGET = max(256, int(os.getenv("LLM_INITIAL_BUDGET", "9000")))
LLM_MAX_BUDGET = max(LLM_INITIAL_BUDGET, int(os.getenv("LLM_MAX_BUDGET", "12000")))
LLM_BUDGET_STEP = max(1.1, float(os.getenv("LLM_BUDGET_STEP", "1.5")))
LLM_BACKOFF_BASE = max(0.1, float(os.getenv("LLM_BACKOFF_BASE", "2")))
LLM_BACKOFF_MAX = max(LLM_BACKOFF_BASE, float(os.getenv("LLM_BACKOFF_MAX", "12")))
GEMINI_THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "0"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.75"))
MAX_RESPONSE_CHARS = max(1000, int(os.getenv("LLM_MAX_RESPONSE_CHARS", "50000")))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
GEMINI_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash,gemini-2.5-flash-lite").split(",")
    if model.strip()
]
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODELS = [
    model.strip()
    for model in os.getenv("OPENROUTER_MODEL", "").split(",")
    if model.strip()
]

MODEL_CALL_COUNT = 0


class OutputError(Exception):
    """A provider returned content that is malformed or fails local validation."""

    def __init__(self, problem: str, truncated: bool = False):
        super().__init__(problem)
        self.problem = problem
        self.truncated = truncated


class ModelCallLimitExceeded(RuntimeError):
    """The process-wide outbound model request budget has been exhausted."""


def reset_model_call_count() -> None:
    """Reset the counter for isolated unit tests and explicit local reruns."""
    global MODEL_CALL_COUNT
    MODEL_CALL_COUNT = 0


def record_model_call(label: str) -> None:
    """Reserve a call before sending an API request; never exceed the cap."""
    global MODEL_CALL_COUNT
    if MODEL_CALL_COUNT >= LLM_MAX_CALLS:
        raise ModelCallLimitExceeded(
            f"تم بلوغ سقف نداءات النماذج ({MODEL_CALL_COUNT}/{LLM_MAX_CALLS}) قبل {label}"
        )
    MODEL_CALL_COUNT += 1
    print(f"📡 نداء نموذج {MODEL_CALL_COUNT}/{LLM_MAX_CALLS}: {label}", flush=True)


def parse_episode_json(raw: str) -> dict:
    """Extract the first JSON object, tolerating fences, preambles and think tags."""
    text = (raw or "").strip()
    if not text:
        raise OutputError("رد المزوّد فارغ", truncated=True)
    if len(text) > MAX_RESPONSE_CHARS:
        raise OutputError(
            f"الرد أطول من حد الاستجابة ({len(text)} حرفًا؛ الحد {MAX_RESPONSE_CHARS})"
        )
    if re.search(r"<think>(?!.*?</think>)", text, flags=re.I | re.S):
        raise OutputError("الرد انقطع داخل كتلة التفكير", truncated=True)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S).strip()
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text, flags=re.I).strip()
    start = text.find("{")
    if start < 0:
        raise OutputError("الرد لا يحتوي كائن JSON")
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        likely_cut = (
            exc.pos >= max(0, len(text[start:]) - 2)
            or "Unterminated string" in exc.msg
            or text.count("{") > text.count("}")
        )
        raise OutputError(
            f"JSON غير صالح عند الموضع {exc.pos}: {exc.msg}", truncated=likely_cut
        ) from exc
    if not isinstance(value, dict):
        raise OutputError("يجب أن يكون الرد كائن JSON وليس قائمة أو قيمة منفردة")
    return value


QUOTA_MARKERS = (
    "perday", "per-day", "free-models-per-day", "daily quota", "daily limit",
    "quota exceeded", "exceeded your current quota", "insufficient_quota",
)
RATE_MARKERS = ("429", "resource_exhausted", "rate limit", "rate_limit")
TRANSIENT_MARKERS = (
    "500", "502", "503", "504", "unavailable", "overloaded", "timed out",
    "timeout", "temporarily", "connection reset", "connection error",
)
PERMANENT_MARKERS = (
    "400", "401", "403", "404", "invalid_argument", "not_found",
    "permission_denied", "unauthorized", "api key is invalid", "model not found",
)


def classify_error(exc: Exception) -> str:
    """Classify failures as invalid, quota, rate, transient, permanent, or unknown."""
    if isinstance(exc, OutputError):
        return "invalid"
    if isinstance(exc, ModelCallLimitExceeded):
        return "limit"
    message = str(exc).lower()
    compact = re.sub(r"[^a-z0-9]+", "", message)
    if any(marker in message for marker in QUOTA_MARKERS) or "perday" in compact:
        return "quota"
    if any(marker in message for marker in RATE_MARKERS):
        return "rate"
    if any(marker in message for marker in TRANSIENT_MARKERS):
        return "transient"
    if any(marker in message for marker in PERMANENT_MARKERS):
        return "permanent"
    return "unknown"


def _backoff(attempt: int) -> float:
    base = min(LLM_BACKOFF_BASE * (2 ** (attempt - 1)), LLM_BACKOFF_MAX)
    return base * random.uniform(0.8, 1.2)


def _gemini_schema(schema: dict) -> dict:
    """Translate the small JSON Schema subset used here to Gemini SDK types."""
    result = {"type": schema["type"].upper()}
    if result["type"] == "OBJECT":
        result["properties"] = {
            key: _gemini_schema(value) for key, value in schema.get("properties", {}).items()
        }
        if schema.get("required"):
            result["required"] = list(schema["required"])
    elif result["type"] == "ARRAY":
        result["items"] = _gemini_schema(schema["items"])
    return result


def _gemini_completion(client, model: str, schema: dict, system_prompt: str,
                       user_message: str, budget: int) -> str:
    from google.genai import types

    config_data = {
        "system_instruction": system_prompt,
        "temperature": TEMPERATURE,
        "max_output_tokens": budget,
        "response_mime_type": "application/json",
        "response_schema": schema,
    }
    if GEMINI_THINKING_BUDGET > 0:
        config_data["thinking_config"] = types.ThinkingConfig(
            thinking_budget=GEMINI_THINKING_BUDGET
        )
    config = types.GenerateContentConfig(**config_data)

    def send(current_config):
        record_model_call(f"gemini:{model}")
        return client.models.generate_content(
            model=model, contents=user_message, config=current_config
        )

    try:
        response = send(config)
    except Exception as exc:
        # Retrying without a nonessential thinking option can recover model-specific
        # INVALID_ARGUMENT responses; when budget is zero the option is omitted already.
        if GEMINI_THINKING_BUDGET > 0 and "thinking" in str(exc).lower():
            config_data.pop("thinking_config", None)
            response = send(types.GenerateContentConfig(**config_data))
        else:
            raise

    finish = ""
    try:
        finish = str(response.candidates[0].finish_reason)
    except (AttributeError, IndexError, TypeError):
        pass
    if "MAX_TOKENS" in finish.upper():
        raise OutputError(f"Gemini {model} قطع الرد (MAX_TOKENS)", truncated=True)
    try:
        text = (response.text or "").strip()
    except (AttributeError, ValueError):
        text = ""
    if not text:
        raise OutputError(f"Gemini {model} أعاد ردًا فارغًا (finish={finish or '?'})", truncated=True)
    return text


def _chat_text_and_finish(data: dict, label: str) -> tuple[str, str]:
    choices = data.get("choices") or []
    if not choices:
        raise OutputError(f"{label} لم يُرجع choices")
    choice = choices[0] or {}
    finish = str(choice.get("finish_reason") or "")
    if finish.lower() in {"length", "max_tokens"}:
        raise OutputError(f"{label} قطع الرد ({finish})", truncated=True)
    message = choice.get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
    if not isinstance(content, str) or not content.strip():
        refusal = message.get("refusal")
        raise OutputError(f"{label} أعاد ردًا فارغًا أو مرفوضًا: {refusal or 'بدون محتوى'}")
    usage = data.get("usage") or {}
    if usage:
        print(
            f"   🔢 {label} | مدخل: {usage.get('prompt_tokens', '?')} "
            f"| مخرج: {usage.get('completion_tokens', '?')} "
            f"| إجمالي: {usage.get('total_tokens', '?')}"
        )
    return content.strip(), finish


def _post_chat(url: str, key: str, payload: dict, label: str,
               extra_headers: dict | None = None) -> str:
    import requests

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    record_model_call(label)
    response = requests.post(url, headers=headers, json=payload, timeout=LLM_REQUEST_TIMEOUT)
    if response.status_code != 200:
        body = (response.text or "")[:400]
        raise RuntimeError(f"{label} HTTP {response.status_code}: {body}")
    try:
        data = response.json()
    except ValueError as exc:
        raise OutputError(f"{label} أعاد JSON API غير صالح") from exc
    text, _ = _chat_text_and_finish(data, label)
    return text


def _groq_completion(model: str, schema: dict, system_prompt: str,
                     user_message: str, budget: int) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": TEMPERATURE,
        "max_completion_tokens": budget,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "episode", "strict": True, "schema": schema},
        },
    }
    return _post_chat("https://api.groq.com/openai/v1/chat/completions",
                      GROQ_API_KEY, payload, f"groq:{model}")


def _openrouter_completion(model: str, schema_keys: list[str], system_prompt: str,
                           user_message: str, budget: int) -> str:
    keys_hint = "أعد JSON واحدًا فقط وبالمفاتيح المطلوبة بالضبط: " + ", ".join(schema_keys)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt + "\n\n" + keys_hint},
            {"role": "user", "content": user_message},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": budget,
        "response_format": {"type": "json_object"},
        "reasoning": {"effort": "none", "exclude": True},
    }
    return _post_chat(
        "https://openrouter.ai/api/v1/chat/completions", OPENROUTER_API_KEY, payload,
        f"openrouter:{model}",
        {"HTTP-Referer": "https://github.com/ahmedalsharqwi2-gif/islamic-reminder1",
         "X-Title": "Islamic Reminder Episode Generator"},
    )


@dataclass
class Provider:
    label: str
    fn: Callable[[str, str, int], str]


def build_providers(schema: dict, gemini_schema_builder: Callable[[dict], dict] | None = None,
                    gemini_client=None) -> list[Provider]:
    """Build providers only for configured keys; preserve deterministic fallback order."""
    providers: list[Provider] = []
    if GEMINI_API_KEY:
        from google import genai

        client = gemini_client or genai.Client(api_key=GEMINI_API_KEY)
        model_names = list(dict.fromkeys([GEMINI_MODEL, *GEMINI_FALLBACK_MODELS]))
        converted_schema = gemini_schema_builder(schema) if gemini_schema_builder else _gemini_schema(schema)
        for model in model_names:
            providers.append(Provider(
                f"gemini:{model}",
                lambda system, user, budget, m=model: _gemini_completion(
                    client, m, converted_schema, system, user, budget
                ),
            ))
    if GROQ_API_KEY:
        providers.append(Provider(
            f"groq:{GROQ_MODEL}",
            lambda system, user, budget: _groq_completion(
                GROQ_MODEL, schema, system, user, budget
            ),
        ))
    if OPENROUTER_API_KEY:
        keys = list(schema.get("properties", {}).keys())
        for model in OPENROUTER_MODELS:
            providers.append(Provider(
                f"openrouter:{model}",
                lambda system, user, budget, m=model: _openrouter_completion(
                    m, keys, system, user, budget
                ),
            ))
    return providers


def generate_valid_episode(
    system_prompt: str,
    user_message: str,
    budget: int,
    providers: list[Provider],
    validate: Callable[[dict], None],
    normalize: Callable[[dict], dict] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[dict, str]:
    """Try providers in order; a result is success only after parse + normalize + validation."""
    if not providers:
        raise RuntimeError(
            "لا يوجد مزوّد نموذج مهيأ. أضف GEMINI_API_KEY أو GROQ_API_KEY أو OPENROUTER_API_KEY."
        )
    deadline = clock() + LLM_DEADLINE_SECONDS
    errors: list[str] = []

    for provider in providers:
        current_budget = budget
        feedback = ""
        transient_attempts = 0
        invalid_attempts = 0
        while True:
            if clock() >= deadline:
                errors.append("انتهت المهلة الكلية لمجموعة المزوّدين")
                raise RuntimeError(" | ".join(errors[-8:]))
            try:
                raw = provider.fn(system_prompt, user_message + feedback, current_budget)
                episode = parse_episode_json(raw)
                if normalize:
                    episode = normalize(episode)
                validate(episode)
                print(
                    f"✅ قُبلت الحلقة عبر {provider.label} بعد "
                    f"{MODEL_CALL_COUNT}/{LLM_MAX_CALLS} نداءات"
                )
                return episode, provider.label
            except ModelCallLimitExceeded:
                raise
            except Exception as exc:  # noqa: BLE001 - classify and fail over safely
                kind = classify_error(exc)
                message = f"{provider.label} [{kind}]: {str(exc)[:240]}"
                errors.append(message)
                print(f"⚠️ {message}", flush=True)
                if kind in {"quota", "permanent"}:
                    break
                if kind == "limit":
                    raise
                if kind == "invalid":
                    invalid_attempts += 1
                    if invalid_attempts >= LLM_INVALID_RETRIES:
                        break
                    if getattr(exc, "truncated", False):
                        current_budget = min(
                            max(current_budget + 512, int(current_budget * LLM_BUDGET_STEP)),
                            LLM_MAX_BUDGET,
                        )
                    problem = getattr(exc, "problem", str(exc))
                    feedback = (
                        "\n\n[تصحيح مطلوب من المحاولة السابقة: " + problem[:500]
                        + ". أعد إخراج الحلقة كاملة وفق المخطط، ولا تُسقط أو تغيّر أي حقل مطلوب.]"
                    )
                    continue
                transient_attempts += 1
                if transient_attempts >= LLM_RETRIES:
                    break
                delay = _backoff(transient_attempts)
                print(f"   ⏳ إعادة المحاولة خلال {delay:.1f} ثانية", flush=True)
                sleep(delay)

    detail = " | ".join(errors[-8:]) or "لا توجد استجابة من المزوّدين"
    raise RuntimeError(f"فشلت جميع المزوّدات بعد {MODEL_CALL_COUNT}/{LLM_MAX_CALLS} نداءات: {detail}")
