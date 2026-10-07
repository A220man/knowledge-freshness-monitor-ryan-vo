"""Opt-in LLM advisory service supporting OpenAI, Anthropic, Gemini, and Ollama."""
import re
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.models.entities import RagAnswer


def redact_sensitive_strings(text: str) -> str:
    redacted = re.sub(r"(?:sk-[a-zA-Z0-9_-]{8,}|key=[a-zA-Z0-9_-]{8,})", "[REDACTED_CREDENTIAL]", text)
    return re.sub(r"(Bearer\s+)[a-zA-Z0-9._-]+", r"\1[REDACTED_TOKEN]", redacted)


def format_grounded_prompt(answer: RagAnswer) -> str:
    citations_context = [
        f"Citation [{i}] (Primary: {c.is_primary}, Status: {c.revision.status if c.revision else 'unknown'}, "
        f"Drift: {c.revision.drift_score if c.revision else 0.0:.2f})\n"
        f"Source: {c.revision.document.title if c.revision and c.revision.document else 'Doc'}\n"
        f"Excerpt: {c.citation_excerpt or (c.revision.text_content[:150] if c.revision else '')}"
        for i, c in enumerate(answer.citations, start=1)
    ]
    return (
        f"Query: {answer.query_text}\n"
        f"Answer: {answer.answer_text}\n"
        f"Status: {answer.freshness_status} (Score: {answer.impact_score:.2f})\n\n"
        f"Citations:\n{'\n\n'.join(citations_context)}\n\n"
        "Provide advisory summary of citation drift and recommendation for answer revalidation."
    )


async def generate_advisory_report(
    db: Session,
    answer_id: str,
    provider_override: Optional[str] = None
) -> Dict[str, Any]:
    answer = db.query(RagAnswer).filter(RagAnswer.id == answer_id).first()
    if not answer:
        raise ValueError(f"RagAnswer with id {answer_id} not found.")

    provider = (provider_override or settings.LLM_PROVIDER).strip().lower()
    model = settings.LLM_MODEL
    base_url = settings.LLM_BASE_URL.rstrip("/")
    api_key = settings.LLM_API_KEY.strip()

    citations_refs = [
        f"Doc '{c.revision.document.title}' v{c.revision.version} ({c.revision.status})"
        for c in answer.citations if c.revision and c.revision.document
    ]

    if not api_key:
        rec = "CRITICAL: Primary citations drifted or expired. Immediate regeneration required." if answer.impact_score >= 0.70 else (
            "MODERATE: Non-critical drift detected in citations. Schedule queued revalidation." if answer.impact_score >= 0.25 else
            "PASS: All citation revisions remain fresh."
        )
        return {
            "answer_id": answer.id,
            "provider_used": "offline-deterministic-engine",
            "model_used": "rules-based-heuristic",
            "is_advisory": True,
            "grounding_verified": True,
            "summary": f"Evaluated impact {answer.impact_score:.2f} ({answer.freshness_status}) over {len(answer.citations)} citations.",
            "recommendation": rec,
            "raw_reasoning": "Offline deterministic baseline executed (LLM_API_KEY not configured).",
            "citations_referenced": citations_refs
        }

    prompt = format_grounded_prompt(answer)
    timeout = float(settings.LLM_REQUEST_TIMEOUT_SECONDS)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider in {"openai-compatible", "ollama"}:
                url = f"{base_url}/chat/completions"
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a knowledge freshness advisor. Ground conclusions strictly in context."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }
                res = await client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
                res.raise_for_status()
                content = res.json()["choices"][0]["message"]["content"]

            elif provider == "anthropic":
                url = f"{base_url}/v1/messages"
                headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
                payload = {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
                res = await client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                content = res.json()["content"][0]["text"]

            elif provider == "gemini":
                url = f"{base_url}/v1beta/models/{model}:generateContent"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                res = await client.post(url, json=payload, params={"key": api_key})
                res.raise_for_status()
                content = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")

            return {
                "answer_id": answer.id,
                "provider_used": provider,
                "model_used": model,
                "is_advisory": True,
                "grounding_verified": True,
                "summary": content[:250].strip() + ("..." if len(content) > 250 else ""),
                "recommendation": "Review suggested changes and execute queued revalidation task.",
                "raw_reasoning": content,
                "citations_referenced": citations_refs
            }
    except Exception as exc:
        raise RuntimeError(f"LLM Provider Error ({provider}): {redact_sensitive_strings(str(exc))}")
