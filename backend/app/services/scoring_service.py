from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class ScorePayload:
    model_name: str
    practicality_score: int
    innovation_score: int
    total_score: int
    practicality_reason: str
    innovation_reason: str
    strengths: str
    weaknesses: str
    needs_human_review: bool


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


SYSTEM_PROMPT = """你是项目申请书评审助手。请严格根据以下标准评分，并仅返回 JSON。
评分结构：
1. 项目实用性 60 分：来自实际需求、应用范围适合、操作流程简洁、操作步骤明确、应用输出确切、具有实用前景。
2. 项目创新性 40 分：合理使用大模型、智能体，设计合理，技术具有难度，工作量适度。
输出字段必须包含：practicality_score, innovation_score, total_score, practicality_reason, innovation_reason, strengths, weaknesses, needs_human_review。
要求：在不偏离事实的前提下，措辞尽量多样化，避免多次评分出现完全相同的评语。
"""


async def score_application_text(text: str | None) -> ScorePayload:
    settings = get_settings()
    normalized_text = (text or "").strip()

    if not normalized_text:
        return _fallback_score("", reason="申请书正文缺失，需人工复核。")

    if (
        settings.model_provider.lower() == "openai-compatible"
        and settings.model_base_url
        and settings.model_api_key
    ):
        try:
            return await _score_with_openai_compatible(normalized_text)
        except Exception:
            return _fallback_score(normalized_text, reason="模型调用失败，已回退到规则评分，建议人工复核。")

    return _fallback_score(normalized_text, reason="未配置模型密钥，当前使用规则评分，建议配置模型以启用 AI 评审。")


async def _score_with_openai_compatible(text: str) -> ScorePayload:
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.model_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.model_name,
        "temperature": 0.55,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"申请书内容如下：\n{text}\n请直接返回 JSON。"},
        ],
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            settings.model_base_url.rstrip("/") + "/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    practicality_score = _clamp(int(parsed.get("practicality_score", 0)), 0, 60)
    innovation_score = _clamp(int(parsed.get("innovation_score", 0)), 0, 40)

    return ScorePayload(
        model_name=settings.model_name,
        practicality_score=practicality_score,
        innovation_score=innovation_score,
        total_score=practicality_score + innovation_score,
        practicality_reason=str(parsed.get("practicality_reason", "")),
        innovation_reason=str(parsed.get("innovation_reason", "")),
        strengths=_normalize_text_field(parsed.get("strengths")),
        weaknesses=_normalize_text_field(parsed.get("weaknesses")),
        needs_human_review=bool(parsed.get("needs_human_review", False)),
    )


def _normalize_text_field(value: object) -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value)
    return str(value or "")


def _fallback_score(text: str, reason: str | None = None) -> ScorePayload:
    practicality_keywords = ["需求", "应用", "流程", "步骤", "输出", "落地", "场景", "实用"]
    innovation_keywords = ["大模型", "智能体", "agent", "算法", "多模态", "自动化", "推理", "检索"]

    practicality_hits = sum(1 for keyword in practicality_keywords if keyword.lower() in text.lower())
    innovation_hits = sum(1 for keyword in innovation_keywords if keyword.lower() in text.lower())

    practicality_score = min(20 + practicality_hits * 5, 60)
    innovation_score = min(12 + innovation_hits * 4, 40)

    needs_review = len(text) < 120 or reason is not None
    practicality_reason = reason or "基于申请书中的需求、流程、输出和落地描述进行了规则评分。"
    innovation_reason = "基于是否体现大模型、智能体和技术挑战度进行了规则评分。"
    strengths = "覆盖真实需求时通常得分更高；若说明流程和输出会提升实用性评分。"
    weaknesses = "当前为规则回退评分，不等同于真实模型评审结果。"

    return ScorePayload(
        model_name=get_settings().model_name,
        practicality_score=practicality_score,
        innovation_score=innovation_score,
        total_score=practicality_score + innovation_score,
        practicality_reason=practicality_reason,
        innovation_reason=innovation_reason,
        strengths=strengths,
        weaknesses=weaknesses,
        needs_human_review=needs_review,
    )
