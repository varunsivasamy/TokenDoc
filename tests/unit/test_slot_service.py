from datetime import UTC, date, datetime, time

from sqlalchemy.orm import Session

from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.schedule import ScheduleCreate
from app.services.slot_service import SlotService


def test_slot_generation_utc_conversion_and_availability(db_session: Session):
    """Verify that doctor slots are generated in UTC from clinic local schedule."""
    clinic = Clinic(
        id="c-slot-test",
        name="Timezone Clinic",
        slug="tz-clinic",
        timezone="America/New_York",
    )
    doctor = Doctor(
        id="doc-slot-test",
        clinic_id=clinic.id,
        full_name="Dr. Chronos",
        specialty="General",
        default_slot_duration_minutes=15,
    )
    db_session.add_all([clinic, doctor])
    db_session.commit()

    repo = ScheduleRepository(db_session, clinic.id)
    service = SlotService(repo)

    # Tuesday: 2026-10-20 (weekday == 1)
    # Schedule: 09:00 to 10:00 in America/New_York (EDT is UTC-4 in October)
    # 09:00 EDT == 13:00 UTC
    service.set_doctor_schedule(
        doctor.id,
        ScheduleCreate(
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(10, 0),
            slot_duration_minutes=15,
        ),
    )

    # 13:15 UTC slot is already booked
    booked_time = datetime(2026, 10, 20, 13, 15, tzinfo=UTC)

    slots = service.generate_slots_for_date(
        doctor=doctor,
        clinic=clinic,
        target_date=date(2026, 10, 20),
        booked_slot_starts={booked_time},
    )

    # 1 hour from 9 to 10 with 15 min slots -> exactly 4 slots
    assert len(slots) == 4

    # Slot 0: 13:00 - 13:15 UTC -> available
    assert slots[0].slot_start == datetime(2026, 10, 20, 13, 0, tzinfo=UTC)
    assert slots[0].slot_end == datetime(2026, 10, 20, 13, 15, tzinfo=UTC)
    assert slots[0].is_available is True

    # Slot 1: 13:15 - 13:30 UTC -> booked (not available)
    assert slots[1].slot_start == datetime(2026, 10, 20, 13, 15, tzinfo=UTC)
    assert slots[1].is_available is False

    # Slot 2 & 3: available
    assert slots[2].is_available is True
    assert slots[3].is_available is True
