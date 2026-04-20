"""Placer.ai Property Report PDF parser.

Uses Claude Vision (via document_parser's LLM client) to extract structured
trade area metrics from Placer's standard Property Report PDF layout.
"""

import base64
import json
import logging
from pathlib import Path

from app.services.imports.normalize import TradeAreaMetrics

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are analyzing a Placer.ai Property Report PDF. Extract ALL available data into this exact JSON structure. Use null for any field not found in the document.

{
  "property_name": "string or null",
  "property_address": "string",
  "reporting_period": "string describing the time range, e.g. 'Jan 2025 - Dec 2025'",
  "visit_count_12mo": integer or null,
  "unique_visitors_12mo": integer or null,
  "avg_dwell_minutes": number or null,
  "home_trade_area_zip_codes": ["list", "of", "zip", "codes"] or [],
  "visitor_demographics": {
    "age_distribution": {"18-24": pct, "25-34": pct, ...} or {},
    "income_distribution": {"<50k": pct, "50k-100k": pct, ...} or {},
    "median_hhi": number or null
  },
  "cross_visit_destinations": ["list of other places visitors also go"] or []
}

Return ONLY valid JSON. No markdown, no explanation."""


async def parse_placer_pdf(file_path: str) -> TradeAreaMetrics:
    """Parse a Placer.ai Property Report PDF into TradeAreaMetrics.

    Uses Claude Vision to extract structured data from the PDF pages.
    """
    from app.llm import get_vision_llm_client, LLMVisionRequest, LLMVisionDocument
    from app.core.config import settings

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    pdf_bytes = path.read_bytes()
    base64_data = base64.standard_b64encode(pdf_bytes).decode("ascii")

    llm = get_vision_llm_client()
    response_text = await llm.vision_document(
        LLMVisionRequest(
            model=settings.llm_vision_model,
            max_tokens=4096,
            system="You are a precise data extraction agent. Extract structured data from commercial real estate documents.",
            document=LLMVisionDocument(
                media_type="application/pdf",
                data_base64=base64_data,
            ),
            user_text=EXTRACTION_PROMPT,
        )
    )

    # Parse the JSON response
    try:
        # Handle cases where the model wraps in markdown code blocks
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Placer PDF extraction response: %s", e)
        logger.debug("Raw response: %s", response_text[:500])
        raise ValueError(f"Failed to parse Placer PDF extraction: {e}")

    demographics = data.get("visitor_demographics", {})

    return TradeAreaMetrics(
        property_address=data.get("property_address", "Unknown"),
        property_name=data.get("property_name"),
        reporting_period=data.get("reporting_period"),
        visit_count_12mo=data.get("visit_count_12mo"),
        unique_visitors_12mo=data.get("unique_visitors_12mo"),
        avg_dwell_minutes=data.get("avg_dwell_minutes"),
        home_trade_area_zip_codes=data.get("home_trade_area_zip_codes", []),
        visitor_demographics=demographics,
        cross_visit_destinations=data.get("cross_visit_destinations", []),
        source="placer",
    )
