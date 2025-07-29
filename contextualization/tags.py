import textwrap

from contextualization.models.anomaly_insights import InsightCategory

ANOMALY_CATEGORY_DEFINITIONS = {
    InsightCategory.TIMELINE_IMPACT.value: "Schedule changes, velocity shifts, cadence anomalies",
    InsightCategory.QUALITY_IMPACT.value: "Defect patterns, stability issues, technical debt signals",
    InsightCategory.SCOPE_IMPACT.value: "Feature completion, requirements changes, work redistribution",
    InsightCategory.RESOURCE_IMPACT.value: "Allocation shifts, utilization patterns, capacity anomalies",
    InsightCategory.TECHNICAL_IMPACT.value: "Architecture changes, component behavior, system performance",
    InsightCategory.FEATURE_ADDITION.value: (
        "Introduction of entirely new capabilities, tracking new functionality, "
        "systems, or components that expand system capabilities and user features"
    ),
    InsightCategory.FEATURE_ENHANCEMENT.value: (
        "Improvements to existing capabilities, tracking significant refinements, "
        "expansions, and extensions that enhance user or system experiences."
    ),
    InsightCategory.SECURITY_IMPACT.value: (
        "Vulnerability disclosures, access control changes, threat mitigation patterns"
    ),
    InsightCategory.OTHER.value: "Any significant anomaly that doesn't fit the above categories",
}

FORMAT_AS_BULLET_POINTS_TAG = "[FORMAT_AS_BULLET_POINTS]"
INCLUDE_ANOMALY_CATEGORY_DEFINITIONS = "[ANOMALY_CATEGORY_DEFINITIONS]"
INCLUDE_ANOMALY_CATEGORIES = "[ANOMALY_CATEGORIES]"

ALL_TAGS = [
    FORMAT_AS_BULLET_POINTS_TAG,
    INCLUDE_ANOMALY_CATEGORY_DEFINITIONS,
    INCLUDE_ANOMALY_CATEGORIES,
]

category_definitions_as_prompt = textwrap.indent(
    "\n".join(f"- **{key}**: {value}" for key, value in ANOMALY_CATEGORY_DEFINITIONS.items()),
    prefix="            ",
)


def get_tags_prompt(format_as_bullet_points=False, include_anomaly_categories=False):
    prompt = textwrap.dedent(f"""
    You will receive fields that may include format tags like {", ".join(ALL_TAGS)}.

    TAGS:
    """)

    if format_as_bullet_points:
        prompt += textwrap.dedent(f"""
        - {FORMAT_AS_BULLET_POINTS_TAG}: Format the field as bullet points. Each bullet should:
            - Start with '• '
            - Appear on a new line, using '\\n' as the line break character
        """)

    if include_anomaly_categories:
        prompt += textwrap.dedent(f"""
        - {INCLUDE_ANOMALY_CATEGORY_DEFINITIONS}: When you see this tag, insert this:
{category_definitions_as_prompt}
        - {INCLUDE_ANOMALY_CATEGORIES}: When you see this tag, use these categories:
            - {", ".join([e.value for e in InsightCategory])}
        """)

    return prompt
