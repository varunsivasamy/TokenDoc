"""add doctor_schedules and appointments with partial unique index

Revision ID: 0003_appointment_unique_index
Revises: 0002_doctor_and_patient
Create Date: 2026-10-17 15:18:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_appointment_unique_index"
down_revision: str | None = "0002_doctor_and_patient"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Doctor schedules table
    op.create_table(
        "doctor_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("clinic_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doctor_id", "day_of_week", name="uq_doctor_day_schedule"),
    )
    op.create_index(op.f("ix_doctor_schedules_id"), "doctor_schedules", ["id"], unique=False)
    op.create_index(
        op.f("ix_doctor_schedules_clinic_id"), "doctor_schedules", ["clinic_id"], unique=False
    )
    op.create_index(
        op.f("ix_doctor_schedules_doctor_id"), "doctor_schedules", ["doctor_id"], unique=False
    )

    # Appointments table
    op.create_table(
        "appointments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("clinic_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="BOOKED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_appointments_id"), "appointments", ["id"], unique=False)
    op.create_index(op.f("ix_appointments_clinic_id"), "appointments", ["clinic_id"], unique=False)
    op.create_index(op.f("ix_appointments_doctor_id"), "appointments", ["doctor_id"], unique=False)
    op.create_index(
        op.f("ix_appointments_patient_id"), "appointments", ["patient_id"], unique=False
    )
    op.create_index(
        op.f("ix_appointments_slot_start"), "appointments", ["slot_start"], unique=False
    )
    op.create_index(op.f("ix_appointments_status"), "appointments", ["status"], unique=False)

    # Partial unique index preventing double-booking on active slots
    op.create_index(
        "uq_active_doctor_slot",
        "appointments",
        ["doctor_id", "slot_start"],
        unique=True,
        postgresql_where=sa.text("status IN ('BOOKED', 'CONFIRMED')"),
        sqlite_where=sa.text("status IN ('BOOKED', 'CONFIRMED')"),
    )


def downgrade() -> None:
    op.drop_index("uq_active_doctor_slot", table_name="appointments")
    op.drop_index(op.f("ix_appointments_status"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_slot_start"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_patient_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_doctor_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_clinic_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_id"), table_name="appointments")
    op.drop_table("appointments")

    op.drop_index(op.f("ix_doctor_schedules_doctor_id"), table_name="doctor_schedules")
    op.drop_index(op.f("ix_doctor_schedules_clinic_id"), table_name="doctor_schedules")
    op.drop_index(op.f("ix_doctor_schedules_id"), table_name="doctor_schedules")
    op.drop_table("doctor_schedules")
