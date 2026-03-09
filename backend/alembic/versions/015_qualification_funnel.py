"""Replace deal stages with acquisition funnel + enrich property model + subscription tier rename

Revision ID: 015
Revises: 014
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None

# Stage migration mapping
STAGE_MAPPING = {
    'lead': 'intake',
    'tour': 'qualification',
    'loi': 'loi',
    'lease': 'under_contract',
    'closed': 'closed',
    'lost': 'dead',
}

REVERSE_STAGE_MAPPING = {v: k for k, v in STAGE_MAPPING.items()}


def upgrade() -> None:
    # --- 1. Migrate deal stages ---
    # Update deals table
    for old_stage, new_stage in STAGE_MAPPING.items():
        op.execute(
            sa.text(f"UPDATE deals SET stage = '{new_stage}' WHERE stage = '{old_stage}'")
        )

    # Update deal_stage_history
    for old_stage, new_stage in STAGE_MAPPING.items():
        op.execute(
            sa.text(f"UPDATE deal_stage_history SET from_stage = '{new_stage}' WHERE from_stage = '{old_stage}'")
        )
        op.execute(
            sa.text(f"UPDATE deal_stage_history SET to_stage = '{new_stage}' WHERE to_stage = '{old_stage}'")
        )

    # --- 2. Add new property columns ---
    # Market classification
    with op.batch_alter_table('properties') as batch_op:
        batch_op.add_column(sa.Column('market_region', sa.String(10), nullable=True))
        batch_op.add_column(sa.Column('metro_area', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('product_type', sa.String(50), nullable=True))

        # Qualification
        batch_op.add_column(sa.Column('intersection_quality', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('traffic_count_vpd', sa.Integer, nullable=True))
        batch_op.add_column(sa.Column('population_1mi', sa.Integer, nullable=True))
        batch_op.add_column(sa.Column('population_3mi', sa.Integer, nullable=True))
        batch_op.add_column(sa.Column('population_5mi', sa.Integer, nullable=True))
        batch_op.add_column(sa.Column('median_hhi_3mi', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('qualification_score', sa.Integer, nullable=True))
        batch_op.add_column(sa.Column('qualification_data', sa.JSON, nullable=True))

        # Ownership & Zoning
        batch_op.add_column(sa.Column('owner_name', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('owner_entity', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('zoning_code', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('zoning_description', sa.String(255), nullable=True))

        # Pricing
        batch_op.add_column(sa.Column('asking_price', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('cap_rate', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('price_psf', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('noi', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('is_sale_comp', sa.Boolean, server_default=sa.text('false'), nullable=False))

        # Broker contact
        batch_op.add_column(sa.Column('broker_name', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('broker_company', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('broker_phone', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('broker_email', sa.String(255), nullable=True))

        # Source tracking
        batch_op.add_column(sa.Column('source_type', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('source_url', sa.String(500), nullable=True))

    # --- 3. Rename subscription tier PRO -> INDIVIDUAL ---
    op.execute(
        sa.text("UPDATE subscription_plans SET tier = 'individual' WHERE tier = 'pro'")
    )
    op.execute(
        sa.text("UPDATE subscription_plans SET name = 'Individual' WHERE name = 'Pro'")
    )

    # --- 4. Add new feature flags to subscription_plans ---
    with op.batch_alter_table('subscription_plans') as batch_op:
        batch_op.add_column(sa.Column('has_gmail_monitoring', sa.Boolean, server_default=sa.text('false'), nullable=False))
        batch_op.add_column(sa.Column('has_qualification_scoring', sa.Boolean, server_default=sa.text('false'), nullable=False))
        batch_op.add_column(sa.Column('has_loi_generation', sa.Boolean, server_default=sa.text('false'), nullable=False))
        batch_op.add_column(sa.Column('has_pro_forma', sa.Boolean, server_default=sa.text('false'), nullable=False))
        batch_op.add_column(sa.Column('has_approval_workflow', sa.Boolean, server_default=sa.text('false'), nullable=False))
        batch_op.add_column(sa.Column('has_followup_automation', sa.Boolean, server_default=sa.text('false'), nullable=False))
        batch_op.add_column(sa.Column('has_pipeline_reports', sa.Boolean, server_default=sa.text('false'), nullable=False))
        batch_op.add_column(sa.Column('has_comp_database', sa.Boolean, server_default=sa.text('false'), nullable=False))
        batch_op.add_column(sa.Column('properties_limit', sa.Integer, server_default='-1', nullable=False))
        batch_op.add_column(sa.Column('gmail_emails_per_day', sa.Integer, server_default='0', nullable=False))

    # Set feature flags for individual tier
    op.execute(sa.text("""
        UPDATE subscription_plans SET
            has_qualification_scoring = true,
            has_comp_database = true,
            has_gmail_monitoring = true,
            has_loi_generation = true,
            has_pro_forma = true,
            has_pipeline_reports = true,
            gmail_emails_per_day = 50
        WHERE tier = 'individual'
    """))

    # Set feature flags for enterprise tier
    op.execute(sa.text("""
        UPDATE subscription_plans SET
            has_qualification_scoring = true,
            has_comp_database = true,
            has_gmail_monitoring = true,
            has_loi_generation = true,
            has_pro_forma = true,
            has_approval_workflow = true,
            has_followup_automation = true,
            has_pipeline_reports = true,
            gmail_emails_per_day = -1
        WHERE tier = 'enterprise'
    """))

    # Set free tier property limit
    op.execute(sa.text("""
        UPDATE subscription_plans SET properties_limit = 10 WHERE tier = 'free'
    """))

    # --- 5. Add approval_requests table ---
    op.create_table(
        'approval_requests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('deal_id', sa.String(36), sa.ForeignKey('deals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requested_by', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('approval_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('decided_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('decided_at', sa.DateTime, nullable=True),
    )

    # --- 6. Add config fields ---
    with op.batch_alter_table('user_preferences') as batch_op:
        batch_op.add_column(sa.Column('market_config', sa.JSON, nullable=True))


def downgrade() -> None:
    # Remove market_config from preferences
    with op.batch_alter_table('user_preferences') as batch_op:
        batch_op.drop_column('market_config')

    # Drop approval_requests
    op.drop_table('approval_requests')

    # Remove new subscription plan columns
    with op.batch_alter_table('subscription_plans') as batch_op:
        batch_op.drop_column('gmail_emails_per_day')
        batch_op.drop_column('properties_limit')
        batch_op.drop_column('has_comp_database')
        batch_op.drop_column('has_pipeline_reports')
        batch_op.drop_column('has_followup_automation')
        batch_op.drop_column('has_approval_workflow')
        batch_op.drop_column('has_pro_forma')
        batch_op.drop_column('has_loi_generation')
        batch_op.drop_column('has_qualification_scoring')
        batch_op.drop_column('has_gmail_monitoring')

    # Remove new property columns
    with op.batch_alter_table('properties') as batch_op:
        batch_op.drop_column('source_url')
        batch_op.drop_column('source_type')
        batch_op.drop_column('broker_email')
        batch_op.drop_column('broker_phone')
        batch_op.drop_column('broker_company')
        batch_op.drop_column('broker_name')
        batch_op.drop_column('is_sale_comp')
        batch_op.drop_column('noi')
        batch_op.drop_column('price_psf')
        batch_op.drop_column('cap_rate')
        batch_op.drop_column('asking_price')
        batch_op.drop_column('zoning_description')
        batch_op.drop_column('zoning_code')
        batch_op.drop_column('owner_entity')
        batch_op.drop_column('owner_name')
        batch_op.drop_column('qualification_data')
        batch_op.drop_column('qualification_score')
        batch_op.drop_column('median_hhi_3mi')
        batch_op.drop_column('population_5mi')
        batch_op.drop_column('population_3mi')
        batch_op.drop_column('population_1mi')
        batch_op.drop_column('traffic_count_vpd')
        batch_op.drop_column('intersection_quality')
        batch_op.drop_column('product_type')
        batch_op.drop_column('metro_area')
        batch_op.drop_column('market_region')

    # Revert subscription tier rename
    op.execute(sa.text("UPDATE subscription_plans SET tier = 'pro' WHERE tier = 'individual'"))
    op.execute(sa.text("UPDATE subscription_plans SET name = 'Pro' WHERE name = 'Individual'"))

    # Revert deal stages
    for new_stage, old_stage in REVERSE_STAGE_MAPPING.items():
        op.execute(sa.text(f"UPDATE deals SET stage = '{old_stage}' WHERE stage = '{new_stage}'"))
        op.execute(sa.text(f"UPDATE deal_stage_history SET from_stage = '{old_stage}' WHERE from_stage = '{new_stage}'"))
        op.execute(sa.text(f"UPDATE deal_stage_history SET to_stage = '{old_stage}' WHERE to_stage = '{new_stage}'"))
