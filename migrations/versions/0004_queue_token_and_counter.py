"""add queue_tokens and daily_token_counters tables

Revision ID: 0004_queue_token_and_counter
Revises: 0003_appointment_unique_index
Create Date: 2026-10-19 16:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_queue_token_and_counter"
down_revision: str | None = "0003_appointment_unique_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Daily token counters table
    op.create_table(
        "daily_token_counters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("clinic_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("token_date", sa.Date(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doctor_id", "token_date", name="uq_counter_doctor_date"),
    )
    op.create_index(
        op.f("ix_daily_token_counters_clinic_id"),
        "daily_token_counters",
        ["clinic_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_token_counters_doctor_id"),
        "daily_token_counters",
        ["doctor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_token_counters_token_date"),
        "daily_token_counters",
        ["token_date"],
        unique=False,
    )

    # Queue tokens table
    op.create_table(
        "queue_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("clinic_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("appointment_id", sa.String(length=36), nullable=True),
        sa.Column("token_number", sa.Integer(), nullable=False),
        sa.Column("token_date", sa.Date(), nullable=False),
        sa.Column("access_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="WAITING"),
        sa.Column("is_emergency", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consultation_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consultation_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "doctor_id", "token_date", "token_number", name="uq_doctor_date_token_num"
        ),
    )
    op.create_index(op.f("ix_queue_tokens_id"), "queue_tokens", ["id"], unique=False)
    op.create_index(op.f("ix_queue_tokens_clinic_id"), "queue_tokens", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_queue_tokens_doctor_id"), "queue_tokens", ["doctor_id"], unique=False)
    op.create_index(
        op.f("ix_queue_tokens_patient_id"), "queue_tokens", ["patient_id"], unique=False
    )
    op.create_index(
        op.f("ix_queue_tokens_appointment_id"), "queue_tokens", ["appointment_id"], unique=False
    )
    op.create_index(
        op.f("ix_queue_tokens_token_date"), "queue_tokens", ["token_date"], unique=False
    )
    op.create_index(
        op.f("ix_queue_tokens_access_code"), "queue_tokens", ["access_code"], unique=True
    )
    op.create_index(op.f("ix_queue_tokens_status"), "queue_tokens", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_queue_tokens_status"), table_name="queue_tokens")
    op.drop_index(op.f("ix_queue_tokens_access_code"), table_name="queue_tokens")
    op.drop_index(op.f("ix_queue_tokens_token_date"), table_name="queue_tokens")
    op.drop_index(op.f("ix_queue_tokens_appointment_id"), table_name="queue_tokens")
    op.drop_index(op.f("ix_queue_tokens_patient_id"), table_name="queue_tokens")
    op.drop_index(op.f("ix_queue_tokens_doctor_id"), table_name="queue_tokens")
    op.drop_index(op.f("ix_queue_tokens_clinic_id"), table_name="queue_tokens")
    op.drop_index(op.f("ix_queue_tokens_id"), table_name="queue_tokens")
    op.drop_table("queue_tokens")

    op.drop_index(op.f("ix_daily_token_counters_token_date"), table_name="daily_token_counters")
    op.drop_index(op.f("ix_daily_token_counters_doctor_id"), table_name="daily_token_counters")
    op.drop_index(op.f("ix_daily_token_counters_clinic_id"), table_name="daily_token_counters")
    op.drop_table("daily_token_counters")
