"""
Document Parser Service

Uses Claude Vision to extract structured data from uploaded PDFs and images.
Supports leasing flyers, void analyses, investment memos, and other CRE documents.
"""
import base64
import json
import re
from pathlib import Path

from anthropic import Anthropic

from app.core.config import settings
from app.models.document import (
    DocumentType,
    ExtractedFlyerData,
    ExtractedPropertyInfo,
    ExtractedAvailableSpace,
    ExtractedTenant,
)

# Initialize Anthropic client
client = Anthropic(api_key=settings.anthropic_api_key)

# Use Claude Sonnet for better vision capabilities
VISION_MODEL = "claude-sonnet-4-20250514"


def encode_file_to_base64(file_path: str) -> str:
    """Read a file and encode it to base64."""
    with open(file_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def get_media_type(file_path: str) -> str:
    """Determine the media type based on file extension."""
    ext = Path(file_path).suffix.lower()
    media_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return media_types.get(ext, "application/pdf")


async def classify_document(file_path: str) -> tuple[DocumentType, float]:
    """
    Classify a document by its type using Claude Vision.

    Returns:
        Tuple of (DocumentType, confidence_score)
    """
    base64_data = encode_file_to_base64(file_path)
    media_type = get_media_type(file_path)

    system_prompt = """You are a commercial real estate document classifier.
Analyze the provided document and classify it into one of these types:
- leasing_flyer: Marketing materials showing available spaces, site plans, tenant lists
- void_analysis: Gap analysis reports showing missing retail categories in a trade area
- investment_memo: One-pagers or investment summaries with financials, demographics, ROI
- loan_document: Loan agreements, financing documents, mortgage paperwork
- comp_report: Comparable lease/sale reports
- other: Any document that doesn't fit the above categories

Respond with JSON only: {"type": "document_type", "confidence": 0.95}"""

    response = client.messages.create(
        model=VISION_MODEL,
        max_tokens=200,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Classify this document. Return JSON only.",
                    },
                ],
            }
        ],
    )

    # Parse the response
    response_text = response.content[0].text.strip()

    # Extract JSON from response (handle markdown code blocks)
    json_match = re.search(r'\{[^}]+\}', response_text)
    if json_match:
        result = json.loads(json_match.group())
        doc_type = DocumentType(result.get("type", "other"))
        confidence = float(result.get("confidence", 0.5))
        return doc_type, confidence

    return DocumentType.OTHER, 0.5


async def parse_leasing_flyer(file_path: str) -> ExtractedFlyerData:
    """
    Parse a leasing flyer/brochure and extract structured data.

    Extracts:
    - Property information (name, address, total SF)
    - Available spaces (suite, SF, rent, features)
    - Existing tenants (name, category, anchor status)
    - Amenities and highlights
    """
    base64_data = encode_file_to_base64(file_path)
    media_type = get_media_type(file_path)

    system_prompt = """You are a commercial real estate data extraction expert.
Analyze this leasing flyer/brochure and extract all relevant information.

Return a JSON object with this exact structure:
{
    "property_info": {
        "name": "Property Name or null",
        "address": "Street Address or null",
        "city": "City or null",
        "state": "State abbreviation or null",
        "zip_code": "ZIP or null",
        "property_type": "retail/office/industrial/mixed-use or null",
        "total_sf": integer or null,
        "year_built": integer or null,
        "parking_ratio": "X:1000 SF or null",
        "landlord_name": "Owner/Landlord name or null"
    },
    "available_spaces": [
        {
            "suite_number": "Suite # or building address",
            "building_address": "Full address if different from main property",
            "square_footage": integer,
            "min_divisible_sf": integer or null,
            "asking_rent_psf": float or null,
            "rent_type": "NNN/Gross/Modified Gross or null",
            "is_endcap": boolean,
            "is_anchor": boolean (>10,000 SF typically),
            "has_drive_thru": boolean,
            "has_patio": boolean,
            "previous_tenant": "Former tenant name or null",
            "notes": "Additional details or null"
        }
    ],
    "existing_tenants": [
        {
            "name": "Tenant Name",
            "category": "dining/retail/service/anchor/etc",
            "suite_number": "Suite # or null",
            "square_footage": integer or null,
            "is_anchor": boolean,
            "is_national": boolean (national brand vs local)
        }
    ],
    "amenities": ["Patio dining", "Ample parking", etc.],
    "highlights": ["Key selling points extracted from the document"],
    "contact_info": {
        "broker_name": "Name or null",
        "company": "Company or null",
        "phone": "Phone or null",
        "email": "Email or null"
    }
}

IMPORTANT:
- Extract ALL available spaces shown, including from site plans
- Look for color coding (yellow/green = available, blue/gray = leased)
- Parse square footage numbers carefully (can be ranges like "divisible to 2x 1,552 SF")
- Identify anchor tenants (typically >10,000 SF or major brands)
- If information is not available, use null
- Return valid JSON only, no markdown formatting"""

    response = client.messages.create(
        model=VISION_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all property information, available spaces, existing tenants, amenities, and highlights from this leasing flyer. Return JSON only.",
                    },
                ],
            }
        ],
    )

    response_text = response.content[0].text.strip()

    # Extract JSON from response (handle markdown code blocks)
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        data = json.loads(json_match.group())
    else:
        # Return empty structure if parsing fails
        data = {
            "property_info": {},
            "available_spaces": [],
            "existing_tenants": [],
            "amenities": [],
            "highlights": [],
            "contact_info": None,
        }

    # Convert to Pydantic models
    property_info = ExtractedPropertyInfo(**data.get("property_info", {}))

    available_spaces = [
        ExtractedAvailableSpace(**space)
        for space in data.get("available_spaces", [])
    ]

    existing_tenants = [
        ExtractedTenant(**tenant)
        for tenant in data.get("existing_tenants", [])
    ]

    return ExtractedFlyerData(
        property_info=property_info,
        available_spaces=available_spaces,
        existing_tenants=existing_tenants,
        amenities=data.get("amenities", []),
        highlights=data.get("highlights", []),
        contact_info=data.get("contact_info"),
    )


async def parse_void_analysis(file_path: str) -> dict:
    """
    Parse a void analysis document and extract gap data.

    Void analyses typically show:
    - Categories with "VOID" indicators (missing retailers)
    - Existing retailers in each category
    - Market vs site counts
    - Suggested tenants for gaps
    """
    base64_data = encode_file_to_base64(file_path)
    media_type = get_media_type(file_path)

    system_prompt = """You are a commercial real estate analyst specializing in void/gap analysis.
Analyze this void analysis document and extract structured data about retail gaps.

Return a JSON object with this structure:
{
    "property_address": "Address being analyzed or null",
    "radius_miles": float (trade area radius) or null,
    "analysis_date": "Date if shown or null",
    "categories": [
        {
            "category_name": "Main Category (e.g., Fast Casual, Grocery)",
            "subcategory": "Subcategory if any or null",
            "is_void": true/false (true if 0 in site radius),
            "site_count": integer (retailers in immediate area),
            "market_count": integer (retailers in broader market),
            "avg_square_footage": integer or null,
            "existing_retailers": ["Names of existing retailers in this category"],
            "void_opportunities": ["Names of retailers marked as voids/opportunities"],
            "match_score": float 0-100 or null,
            "common_cotenants": ["Frequent co-tenants for this category"],
            "notes": "Any additional insights"
        }
    ],
    "summary": {
        "total_categories_analyzed": integer,
        "total_voids": integer,
        "high_priority_voids": ["List of most significant gaps"],
        "key_insights": ["Key takeaways from the analysis"]
    }
}

IMPORTANT:
- Look for "VOID" indicators or 0 counts in the site column
- Categories like Fast Casual, Mediterranean, Boutique Fitness are often high-priority voids
- Extract specific tenant names mentioned as opportunities
- Return valid JSON only"""

    response = client.messages.create(
        model=VISION_MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all void/gap analysis data from this document. Identify all categories, existing retailers, and void opportunities. Return JSON only.",
                    },
                ],
            }
        ],
    )

    response_text = response.content[0].text.strip()

    # Extract JSON from response
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        return json.loads(json_match.group())

    return {
        "categories": [],
        "summary": {"total_voids": 0, "high_priority_voids": []},
    }


async def parse_investment_memo(file_path: str) -> dict:
    """
    Parse an investment memo/one-pager and extract financial and property data.
    """
    base64_data = encode_file_to_base64(file_path)
    media_type = get_media_type(file_path)

    system_prompt = """You are a commercial real estate investment analyst.
Analyze this investment memo/one-pager and extract all relevant data.

Return a JSON object with this structure:
{
    "property_info": {
        "name": "Property/Development Name",
        "address": "Full Address",
        "city": "City",
        "state": "State",
        "zip_code": "ZIP",
        "property_type": "retail/office/mixed-use",
        "gla_sf": integer (gross leasable area),
        "land_area_sf": integer or null,
        "year_built": integer or null,
        "status": "Existing/Under Development/Proposed"
    },
    "financials": {
        "irr": float (percentage) or null,
        "rental_yield": float (percentage) or null,
        "exit_cap_rate": float (percentage) or null,
        "land_price": float (total $) or null,
        "land_price_psf": float or null,
        "total_investment": float or null,
        "noi": float (net operating income) or null,
        "asking_rent_psf": float or null,
        "rent_type": "NNN/Gross/etc or null",
        "cam_charges_psf": float or null
    },
    "demographics": {
        "radius_miles": float,
        "population": integer or null,
        "households": integer or null,
        "median_hh_income": float or null,
        "avg_hh_income": float or null,
        "daytime_employment": integer or null,
        "traffic_count": integer (vehicles per day) or null
    },
    "tenant_interest": [
        {
            "tenant_name": "Tenant Name",
            "category": "Category",
            "status": "LOI/Interested/Signed/etc",
            "square_footage": integer or null
        }
    ],
    "highlights": ["Key investment highlights"],
    "scope_of_work": "Development/renovation scope if mentioned",
    "timing": {
        "delivery_date": "Expected delivery or null",
        "construction_start": "Start date or null",
        "lease_up_period": "Timeline or null"
    },
    "contact_info": {
        "developer": "Developer/Owner name or null",
        "broker": "Listing broker or null",
        "phone": "Phone or null",
        "email": "Email or null"
    }
}

IMPORTANT:
- Extract all financial metrics precisely
- Convert percentages to decimal form (e.g., 15% = 15.0, not 0.15)
- Identify any tenant interest or LOIs mentioned
- Return valid JSON only"""

    response = client.messages.create(
        model=VISION_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all investment and property information from this memo. Return JSON only.",
                    },
                ],
            }
        ],
    )

    response_text = response.content[0].text.strip()

    # Extract JSON from response
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        return json.loads(json_match.group())

    return {
        "property_info": {},
        "financials": {},
        "demographics": {},
        "tenant_interest": [],
        "highlights": [],
    }


async def parse_document(file_path: str, document_type: DocumentType | None = None) -> dict:
    """
    Main entry point for document parsing.

    Classifies the document if type not provided, then parses accordingly.

    Returns:
        Dictionary with document_type, confidence, and extracted_data
    """
    # Classify if not provided
    if document_type is None:
        document_type, confidence = await classify_document(file_path)
    else:
        confidence = 1.0

    # Parse based on type
    extracted_data = {}

    if document_type == DocumentType.LEASING_FLYER:
        flyer_data = await parse_leasing_flyer(file_path)
        extracted_data = flyer_data.model_dump()
    elif document_type == DocumentType.VOID_ANALYSIS:
        extracted_data = await parse_void_analysis(file_path)
    elif document_type == DocumentType.INVESTMENT_MEMO:
        extracted_data = await parse_investment_memo(file_path)
    else:
        # For other types, do a generic extraction
        extracted_data = {"raw_text": "Document type not fully supported yet"}

    return {
        "document_type": document_type.value,
        "confidence": confidence,
        "extracted_data": extracted_data,
    }
