"""
Weekly Pipeline Report Generator

Generates a summary report of the deal pipeline including deals by stage,
recent stage changes, pending follow-ups, and new properties. Renders the
report as a dark-themed HTML email matching SpaceFit branding.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.models.deal import (
    Deal,
    DealActivity,
    DealStage,
    DealStageHistory,
    Property,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineReportData:
    """Data model for a weekly pipeline report."""

    deals_by_stage: dict[str, int] = field(default_factory=dict)
    stage_changes_this_week: list[dict] = field(default_factory=list)
    followups_due: int = 0
    new_properties_count: int = 0
    generated_at: datetime = field(default_factory=datetime.utcnow)


async def generate_pipeline_report(
    user_id: str,
    db: AsyncSession,
) -> PipelineReportData:
    """
    Generate a pipeline report for the given user.

    Queries:
    - Active deals grouped by stage
    - Stage transitions from the last 7 days
    - Pending (overdue or upcoming) follow-up activities
    - Properties created in the last 7 days

    Args:
        user_id: The user ID to generate the report for.
        db: Async database session.

    Returns:
        PipelineReportData with all report metrics.
    """
    now = datetime.utcnow()
    one_week_ago = now - timedelta(days=7)

    report = PipelineReportData(generated_at=now)

    # --- Deals by stage ---
    stage_query = await db.execute(
        select(Deal.stage, func.count(Deal.id))
        .where(
            Deal.user_id == user_id,
            Deal.is_archived == False,
        )
        .group_by(Deal.stage)
    )
    for stage, count in stage_query.all():
        report.deals_by_stage[stage] = count

    # Ensure all stages are represented
    for stage in DealStage:
        if stage.value not in report.deals_by_stage:
            report.deals_by_stage[stage.value] = 0

    logger.info(
        "[pipeline_report] Deals by stage for user %s: %s",
        user_id,
        report.deals_by_stage,
    )

    # --- Stage changes this week ---
    changes_query = await db.execute(
        select(DealStageHistory)
        .join(Deal, Deal.id == DealStageHistory.deal_id)
        .where(
            Deal.user_id == user_id,
            DealStageHistory.changed_at >= one_week_ago,
        )
        .order_by(DealStageHistory.changed_at.desc())
    )
    stage_changes = changes_query.scalars().all()

    for change in stage_changes:
        report.stage_changes_this_week.append(
            {
                "deal_id": change.deal_id,
                "from_stage": change.from_stage,
                "to_stage": change.to_stage,
                "changed_at": change.changed_at.isoformat(),
                "notes": change.notes,
            }
        )

    # --- Follow-ups due ---
    followups_query = await db.execute(
        select(func.count(DealActivity.id))
        .where(
            DealActivity.user_id == user_id,
            DealActivity.scheduled_at <= now,
            DealActivity.completed_at.is_(None),
        )
    )
    report.followups_due = followups_query.scalar() or 0

    # --- New properties this week ---
    properties_query = await db.execute(
        select(func.count(Property.id))
        .where(
            Property.user_id == user_id,
            Property.created_at >= one_week_ago,
        )
    )
    report.new_properties_count = properties_query.scalar() or 0

    logger.info(
        "[pipeline_report] Report generated for user %s: %d stage changes, "
        "%d follow-ups due, %d new properties",
        user_id,
        len(report.stage_changes_this_week),
        report.followups_due,
        report.new_properties_count,
    )

    return report


def render_report_html(data: PipelineReportData) -> str:
    """
    Render a pipeline report as HTML email body with dark theme styling.

    Uses SpaceFit brand colors (dark background, teal accents) for
    consistent branding.

    Args:
        data: PipelineReportData to render.

    Returns:
        Complete HTML string suitable for email body.
    """
    # Stage display labels and colors
    stage_colors = {
        "intake": "#6B7280",
        "qualification": "#3B82F6",
        "due_diligence": "#8B5CF6",
        "tenant_vetting": "#F59E0B",
        "loi": "#10B981",
        "under_contract": "#06B6D4",
        "closed": "#22C55E",
        "passed": "#9CA3AF",
        "dead": "#EF4444",
    }

    stage_labels = {
        "intake": "Intake",
        "qualification": "Qualification",
        "due_diligence": "Due Diligence",
        "tenant_vetting": "Tenant Vetting",
        "loi": "LOI",
        "under_contract": "Under Contract",
        "closed": "Closed",
        "passed": "Passed",
        "dead": "Dead",
    }

    # Build stage rows
    stage_rows = ""
    active_stages = ["intake", "qualification", "due_diligence", "tenant_vetting", "loi", "under_contract"]
    total_active = sum(data.deals_by_stage.get(s, 0) for s in active_stages)

    for stage_value in DealStage:
        stage = stage_value.value
        count = data.deals_by_stage.get(stage, 0)
        color = stage_colors.get(stage, "#6B7280")
        label = stage_labels.get(stage, stage.replace("_", " ").title())

        stage_rows += f"""
        <tr>
          <td style="padding: 10px 16px; border-bottom: 1px solid #374151;">
            <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: {color}; margin-right: 8px;"></span>
            {label}
          </td>
          <td style="padding: 10px 16px; border-bottom: 1px solid #374151; text-align: right; font-weight: 600; font-size: 18px;">
            {count}
          </td>
        </tr>"""

    # Build stage changes rows
    changes_html = ""
    if data.stage_changes_this_week:
        for change in data.stage_changes_this_week[:10]:  # Limit to 10
            from_label = stage_labels.get(change["from_stage"] or "", "New")
            to_label = stage_labels.get(change["to_stage"], change["to_stage"])
            from_color = stage_colors.get(change["from_stage"] or "", "#6B7280")
            to_color = stage_colors.get(change["to_stage"], "#6B7280")

            changes_html += f"""
            <tr>
              <td style="padding: 8px 16px; border-bottom: 1px solid #374151; font-size: 13px;">
                {change['deal_id'][:8]}...
              </td>
              <td style="padding: 8px 16px; border-bottom: 1px solid #374151; font-size: 13px;">
                <span style="color: {from_color};">{from_label}</span>
                <span style="color: #6B7280;"> &rarr; </span>
                <span style="color: {to_color}; font-weight: 600;">{to_label}</span>
              </td>
              <td style="padding: 8px 16px; border-bottom: 1px solid #374151; font-size: 13px; color: #9CA3AF;">
                {change['changed_at'][:10]}
              </td>
            </tr>"""
    else:
        changes_html = """
            <tr>
              <td colspan="3" style="padding: 16px; text-align: center; color: #6B7280;">
                No stage changes this week
              </td>
            </tr>"""

    # Followup badge color
    followup_color = "#EF4444" if data.followups_due > 0 else "#22C55E"
    followup_text = f"{data.followups_due} overdue" if data.followups_due > 0 else "All clear"

    generated_str = data.generated_at.strftime("%B %d, %Y at %I:%M %p UTC")

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #111827; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <div style="max-width: 640px; margin: 0 auto; padding: 32px 16px;">

    <!-- Header -->
    <div style="text-align: center; margin-bottom: 32px;">
      <h1 style="color: #F9FAFB; font-size: 24px; margin: 0 0 4px 0;">
        SpaceFit Pipeline Report
      </h1>
      <p style="color: #6B7280; font-size: 14px; margin: 0;">
        Weekly Summary &mdash; {generated_str}
      </p>
    </div>

    <!-- KPI Cards -->
    <div style="display: flex; gap: 12px; margin-bottom: 24px;">
      <div style="flex: 1; background: #1F2937; border-radius: 8px; padding: 16px; text-align: center;">
        <div style="color: #06B6D4; font-size: 28px; font-weight: 700;">{total_active}</div>
        <div style="color: #9CA3AF; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Active Deals</div>
      </div>
      <div style="flex: 1; background: #1F2937; border-radius: 8px; padding: 16px; text-align: center;">
        <div style="color: #10B981; font-size: 28px; font-weight: 700;">{data.new_properties_count}</div>
        <div style="color: #9CA3AF; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">New Properties</div>
      </div>
      <div style="flex: 1; background: #1F2937; border-radius: 8px; padding: 16px; text-align: center;">
        <div style="color: {followup_color}; font-size: 28px; font-weight: 700;">{data.followups_due}</div>
        <div style="color: #9CA3AF; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;">Follow-ups Due</div>
      </div>
    </div>

    <!-- Deals by Stage -->
    <div style="background: #1F2937; border-radius: 8px; margin-bottom: 24px; overflow: hidden;">
      <div style="padding: 16px; border-bottom: 1px solid #374151;">
        <h2 style="color: #F9FAFB; font-size: 16px; margin: 0;">Deals by Stage</h2>
      </div>
      <table style="width: 100%; border-collapse: collapse; color: #E5E7EB;">
        {stage_rows}
      </table>
    </div>

    <!-- Stage Changes This Week -->
    <div style="background: #1F2937; border-radius: 8px; margin-bottom: 24px; overflow: hidden;">
      <div style="padding: 16px; border-bottom: 1px solid #374151;">
        <h2 style="color: #F9FAFB; font-size: 16px; margin: 0;">
          Stage Changes This Week
          <span style="font-size: 13px; color: #6B7280; font-weight: 400; margin-left: 8px;">
            ({len(data.stage_changes_this_week)})
          </span>
        </h2>
      </div>
      <table style="width: 100%; border-collapse: collapse; color: #E5E7EB;">
        <tr style="background: #111827;">
          <th style="padding: 8px 16px; text-align: left; font-size: 11px; color: #6B7280; text-transform: uppercase;">Deal</th>
          <th style="padding: 8px 16px; text-align: left; font-size: 11px; color: #6B7280; text-transform: uppercase;">Transition</th>
          <th style="padding: 8px 16px; text-align: left; font-size: 11px; color: #6B7280; text-transform: uppercase;">Date</th>
        </tr>
        {changes_html}
      </table>
    </div>

    <!-- Follow-up Status -->
    <div style="background: #1F2937; border-radius: 8px; padding: 20px; margin-bottom: 24px; text-align: center;">
      <div style="color: #9CA3AF; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
        Follow-up Status
      </div>
      <div style="color: {followup_color}; font-size: 20px; font-weight: 600;">
        {followup_text}
      </div>
    </div>

    <!-- Footer -->
    <div style="text-align: center; padding-top: 16px; border-top: 1px solid #374151;">
      <p style="color: #4B5563; font-size: 12px; margin: 0;">
        Generated by SpaceFit AI &mdash; Your CRE Deal Pipeline
      </p>
    </div>

  </div>
</body>
</html>"""

    return html
