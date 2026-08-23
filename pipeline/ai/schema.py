"""Workers AI 評価レスポンスの JSON Schema (worker/src/ai.ts と同一契約)。

AI の自由文章を DB に直接入れないための構造化契約。テストからも参照する。
"""

AI_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "summary_ja": {"type": "string", "maxLength": 500},
        "importance": {"type": "number", "minimum": 0, "maximum": 100},
        "novelty": {"type": "number", "minimum": 0, "maximum": 100},
        "category": {"type": "string"},
        "country": {"type": "string"},
        "entities": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        "why_it_matters": {"type": "string", "maxLength": 500},
        "market_relevance": {"type": "number", "minimum": 0, "maximum": 100},
        "technology_relevance": {"type": "number", "minimum": 0, "maximum": 100},
    },
    "required": [
        "summary_ja",
        "importance",
        "novelty",
        "category",
        "country",
        "entities",
        "why_it_matters",
        "market_relevance",
        "technology_relevance",
    ],
    "additionalProperties": False,
}
