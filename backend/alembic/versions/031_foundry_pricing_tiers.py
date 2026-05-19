"""foundry-style pricing tiers and yearly billing

Revision ID: 031
Revises: 030
Create Date: 2026-05-19

Restructure pricing around four individual tiers (free + starter / pro /
max) plus a separate enterprise "contact us" track. Adds yearly billing
support to `subscription_plans` and seeds the new tier rows. Any
subscription that was bound to the legacy `individual` plan is
re-pointed at the new `pro` plan; the legacy row is marked inactive so
it stops appearing in /subscription/plans.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "031"
down_revision: str = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Columns: yearly pricing + interval default. Nullable + server_default
    # so rolling forward doesn't break existing rows.
    op.add_column(
        "subscription_plans",
        sa.Column("price_yearly", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "stripe_price_id_yearly", sa.String(length=255), nullable=True
        ),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "billing_interval_default",
            sa.String(length=10),
            server_default="monthly",
            nullable=False,
        ),
    )

    conn = op.get_bind()

    # 1. Mark the legacy `individual` plan inactive (kept for FK integrity
    #    on any historical subscriptions or audit rows).
    conn.execute(
        sa.text(
            "UPDATE subscription_plans SET is_active = FALSE "
            "WHERE tier = 'individual'"
        )
    )

    # 2. Re-point existing subscriptions from the legacy individual plan
    #    to the new pro plan. Done in two steps because the new plan rows
    #    don't exist yet — insert pro first.
    pro_plan_exists = conn.execute(
        sa.text("SELECT 1 FROM subscription_plans WHERE tier = 'pro'")
    ).first()
    if not pro_plan_exists:
        conn.execute(
            sa.text(
                """
                INSERT INTO subscription_plans (
                    id, tier, name, description,
                    price_monthly, price_yearly, stripe_price_id,
                    stripe_price_id_yearly, billing_interval_default,
                    chat_sessions_per_month, void_analyses_per_month,
                    demographics_reports_per_month, emails_per_month,
                    documents_per_month, team_members,
                    monthly_token_budget,
                    has_placer_access, has_siteusa_access,
                    has_costar_access, has_email_outreach, has_api_access,
                    has_gmail_monitoring, has_qualification_scoring,
                    has_loi_generation, has_pro_forma,
                    has_approval_workflow, has_followup_automation,
                    has_pipeline_reports, has_comp_database,
                    properties_limit, gmail_emails_per_day,
                    is_active, created_at
                ) VALUES (
                    gen_random_uuid()::text, 'pro', 'Pro',
                    'For active CRE pros who chat all day',
                    10000, 9600, NULL, NULL, 'monthly',
                    1000, -1, -1, 2000, 200, 1,
                    10000000,
                    TRUE, TRUE, FALSE, TRUE, FALSE,
                    FALSE, TRUE, FALSE, FALSE, FALSE, TRUE, TRUE, FALSE,
                    -1, 100,
                    TRUE, now()
                )
                """
            )
        )

    # 3. Backfill legacy subscriptions to point at pro.
    conn.execute(
        sa.text(
            """
            UPDATE subscriptions
            SET plan_id = (SELECT id FROM subscription_plans WHERE tier = 'pro' LIMIT 1)
            WHERE plan_id IN (
                SELECT id FROM subscription_plans WHERE tier = 'individual'
            )
            """
        )
    )

    # 4. Seed starter / max. Enterprise stays as-is (we keep the tier but
    #    the PricingPage will replace the checkout button with a sales-
    #    lead flow). Free stays as-is (description was already brought up
    #    to date by 030).
    seed_rows = [
        {
            "tier": "starter",
            "name": "Starter",
            "description": "For solo brokers kicking the tires",
            "price_monthly": 2000,
            "price_yearly": 19200,
            "chat_sessions_per_month": 200,
            "void_analyses_per_month": 20,
            "demographics_reports_per_month": 50,
            "emails_per_month": 200,
            "documents_per_month": 50,
            "team_members": 1,
            "monthly_token_budget": 2000000,
            "has_placer_access": False,
            "has_siteusa_access": False,
            "has_costar_access": False,
            "has_email_outreach": True,
            "has_api_access": False,
            "has_pipeline_reports": False,
        },
        {
            "tier": "max",
            "name": "Max",
            "description": "For high-volume teams who live in chat",
            "price_monthly": 20000,
            "price_yearly": 192000,
            "chat_sessions_per_month": 5000,
            "void_analyses_per_month": -1,
            "demographics_reports_per_month": -1,
            "emails_per_month": 10000,
            "documents_per_month": -1,
            "team_members": 1,
            "monthly_token_budget": 25000000,
            "has_placer_access": True,
            "has_siteusa_access": True,
            "has_costar_access": True,
            "has_email_outreach": True,
            "has_api_access": True,
            "has_pipeline_reports": True,
        },
    ]

    for row in seed_rows:
        exists = conn.execute(
            sa.text("SELECT 1 FROM subscription_plans WHERE tier = :tier"),
            {"tier": row["tier"]},
        ).first()
        if exists:
            continue
        conn.execute(
            sa.text(
                """
                INSERT INTO subscription_plans (
                    id, tier, name, description,
                    price_monthly, price_yearly, stripe_price_id,
                    stripe_price_id_yearly, billing_interval_default,
                    chat_sessions_per_month, void_analyses_per_month,
                    demographics_reports_per_month, emails_per_month,
                    documents_per_month, team_members,
                    monthly_token_budget,
                    has_placer_access, has_siteusa_access,
                    has_costar_access, has_email_outreach, has_api_access,
                    has_gmail_monitoring, has_qualification_scoring,
                    has_loi_generation, has_pro_forma,
                    has_approval_workflow, has_followup_automation,
                    has_pipeline_reports, has_comp_database,
                    properties_limit, gmail_emails_per_day,
                    is_active, created_at
                ) VALUES (
                    gen_random_uuid()::text, :tier, :name, :description,
                    :price_monthly, :price_yearly, NULL, NULL, 'monthly',
                    :chat_sessions_per_month, :void_analyses_per_month,
                    :demographics_reports_per_month, :emails_per_month,
                    :documents_per_month, :team_members,
                    :monthly_token_budget,
                    :has_placer_access, :has_siteusa_access,
                    :has_costar_access, :has_email_outreach, :has_api_access,
                    FALSE, TRUE, FALSE, FALSE, FALSE, TRUE,
                    :has_pipeline_reports, FALSE,
                    -1, 100,
                    TRUE, now()
                )
                """
            ),
            row,
        )


def downgrade() -> None:
    # Re-activate legacy individual plan; remove new tier rows. Do not
    # attempt to un-backfill subscriptions (we don't know which pro
    # subscribers were originally individual vs. genuinely on pro).
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE subscription_plans SET is_active = TRUE WHERE tier = 'individual'"
        )
    )
    conn.execute(
        sa.text(
            "DELETE FROM subscription_plans WHERE tier IN ('starter', 'pro', 'max') "
            "AND id NOT IN (SELECT plan_id FROM subscriptions)"
        )
    )

    op.drop_column("subscription_plans", "billing_interval_default")
    op.drop_column("subscription_plans", "stripe_price_id_yearly")
    op.drop_column("subscription_plans", "price_yearly")
