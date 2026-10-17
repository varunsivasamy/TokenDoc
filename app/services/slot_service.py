from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.doctor_schedule import DoctorSchedule
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.schedule import ScheduleCreate, TimeSlot


class SlotService:
    """Service responsible for generating doctor available slots and weekly schedule management."""

    def __init__(self, schedule_repo: ScheduleRepository):
        self._schedule_repo = schedule_repo

    def set_doctor_schedule(self, doctor_id: str, data: ScheduleCreate) -> DoctorSchedule:
        """Create or update a doctor's weekly work schedule for a day of week."""
        existing = self._schedule_repo.get_by_doctor_and_day(doctor_id, data.day_of_week)
        if existing:
            existing.start_time = data.start_time
            existing.end_time = data.end_time
            existing.slot_duration_minutes = data.slot_duration_minutes
            self._schedule_repo.db.commit()
            self._schedule_repo.db.refresh(existing)
            return existing

        schedule = DoctorSchedule(
            doctor_id=doctor_id,
            day_of_week=data.day_of_week,
            start_time=data.start_time,
            end_time=data.end_time,
            slot_duration_minutes=data.slot_duration_minutes,
        )
        return self._schedule_repo.create(schedule)

    def generate_slots_for_date(
        self,
        doctor: Doctor,
        clinic: Clinic,
        target_date: date,
        booked_slot_starts: set[datetime] | None = None,
    ) -> Sequence[TimeSlot]:
        """Generate all appointment slots for a given doctor on a specific date.

        Times are calculated in the clinic's local timezone and stored/returned in UTC.
        """
        day_of_week = target_date.weekday()  # Monday is 0, Sunday is 6
        schedule = self._schedule_repo.get_by_doctor_and_day(doctor.id, day_of_week)

        if not schedule or not schedule.is_active:
            return []

        try:
            clinic_tz = ZoneInfo(clinic.timezone)
        except Exception:
            clinic_tz = ZoneInfo("UTC")

        # Create localized start and end datetime in clinic timezone
        local_start = datetime.combine(target_date, schedule.start_time).replace(tzinfo=clinic_tz)
        local_end = datetime.combine(target_date, schedule.end_time).replace(tzinfo=clinic_tz)

        # Convert to UTC
        utc_start = local_start.astimezone(UTC)
        utc_end = local_end.astimezone(UTC)

        slot_delta = timedelta(minutes=schedule.slot_duration_minutes)
        slots: list[TimeSlot] = []
        current = utc_start

        normalized_booked = booked_slot_starts or set()

        while current + slot_delta <= utc_end:
            slot_end = current + slot_delta
            is_avail = current not in normalized_booked
            slots.append(
                TimeSlot(
                    slot_start=current,
                    slot_end=slot_end,
                    is_available=is_avail,
                )
            )
            current = slot_end

        return slots
