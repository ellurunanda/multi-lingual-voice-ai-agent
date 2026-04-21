"""
Outbound Campaign Scheduler.
Manages proactive outbound calls for:
- Appointment reminders (24h before)
- Follow-up checkups
- Vaccination reminders
Uses APScheduler for background job management.
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, and_, update

from models.database import (
    Appointment, Patient, Doctor, OutboundCampaign,
    AppointmentStatus, CampaignStatus, CampaignType
)
from models.db_connection import get_db_context
from agent.prompt.system_prompts import get_outbound_prompt
from config import settings

logger = logging.getLogger(__name__)


class CampaignScheduler:
    """
    Background scheduler for outbound campaigns.
    Runs periodic jobs to send reminders and follow-ups.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        logger.info("Campaign Scheduler initialized")

    def start(self):
        """Start the background scheduler."""
        if not self.is_running:
            # Job 1: Send appointment reminders (runs every hour)
            self.scheduler.add_job(
                self.send_appointment_reminders,
                trigger=IntervalTrigger(hours=1),
                id="appointment_reminders",
                name="Appointment Reminders",
                replace_existing=True,
                misfire_grace_time=300,
            )

            # Job 2: Process pending campaigns (runs every minute)
            self.scheduler.add_job(
                self.process_pending_campaigns,
                trigger=IntervalTrigger(minutes=settings.campaign_scheduler_interval),
                id="process_campaigns",
                name="Process Pending Campaigns",
                replace_existing=True,
                misfire_grace_time=60,
            )

            # Job 3: Follow-up reminders (runs daily at 9 AM)
            self.scheduler.add_job(
                self.send_follow_up_reminders,
                trigger=CronTrigger(hour=9, minute=0),
                id="follow_up_reminders",
                name="Follow-up Reminders",
                replace_existing=True,
            )

            # Job 4: Clean up expired sessions (runs every 6 hours)
            self.scheduler.add_job(
                self.cleanup_expired_data,
                trigger=IntervalTrigger(hours=6),
                id="cleanup",
                name="Cleanup Expired Data",
                replace_existing=True,
            )

            self.scheduler.start()
            self.is_running = True
            logger.info("Campaign Scheduler started")

    def stop(self):
        """Stop the background scheduler."""
        if self.is_running:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("Campaign Scheduler stopped")

    async def send_appointment_reminders(self):
        """
        Send reminders for appointments scheduled in the next 24 hours.
        Creates outbound campaign records for each reminder.
        """
        logger.info("Running appointment reminder job")

        try:
            async with get_db_context() as db:
                # Find appointments in next 24 hours
                tomorrow = date.today() + timedelta(days=1)
                reminder_cutoff = datetime.now() + timedelta(
                    hours=settings.reminder_hours_before
                )

                result = await db.execute(
                    select(Appointment, Patient, Doctor)
                    .join(Patient, Appointment.patient_id == Patient.id)
                    .join(Doctor, Appointment.doctor_id == Doctor.id)
                    .where(
                        and_(
                            Appointment.appointment_date == tomorrow,
                            Appointment.status.in_([
                                AppointmentStatus.SCHEDULED,
                                AppointmentStatus.CONFIRMED
                            ])
                        )
                    )
                )

                appointments = result.all()
                reminder_count = 0

                for appointment, patient, doctor in appointments:
                    # Check if reminder already sent
                    existing_result = await db.execute(
                        select(OutboundCampaign).where(
                            and_(
                                OutboundCampaign.campaign_type == CampaignType.REMINDER,
                                OutboundCampaign.target_patient_ids.contains(
                                    [appointment.patient_id]
                                ),
                                OutboundCampaign.scheduled_at >= datetime.now() - timedelta(hours=25)
                            )
                        )
                    )

                    if existing_result.scalar_one_or_none():
                        continue  # Reminder already sent

                    # Get patient's preferred language
                    language = patient.preferred_language or "en"

                    # Generate reminder message
                    message = get_outbound_prompt(
                        campaign_type="reminder",
                        language=language,
                        patient_name=patient.name,
                        doctor_name=doctor.name,
                        time=appointment.appointment_time
                    )

                    # Create campaign record
                    campaign = OutboundCampaign(
                        name=f"Reminder - {patient.name} - {appointment.appointment_date}",
                        campaign_type=CampaignType.REMINDER,
                        target_patient_ids=[appointment.patient_id],
                        message_template=message,
                        language=language,
                        scheduled_at=datetime.now(),
                        status=CampaignStatus.PENDING,
                    )
                    db.add(campaign)
                    reminder_count += 1

                logger.info(f"Created {reminder_count} appointment reminders")

        except Exception as e:
            logger.error(f"Error in appointment reminder job: {e}", exc_info=True)

    async def send_follow_up_reminders(self):
        """
        Send follow-up reminders for completed appointments (7 days after).
        """
        logger.info("Running follow-up reminder job")

        try:
            async with get_db_context() as db:
                # Find appointments completed 7 days ago
                seven_days_ago = date.today() - timedelta(days=7)

                result = await db.execute(
                    select(Appointment, Patient, Doctor)
                    .join(Patient, Appointment.patient_id == Patient.id)
                    .join(Doctor, Appointment.doctor_id == Doctor.id)
                    .where(
                        and_(
                            Appointment.appointment_date == seven_days_ago,
                            Appointment.status == AppointmentStatus.COMPLETED
                        )
                    )
                )

                appointments = result.all()
                follow_up_count = 0

                for appointment, patient, doctor in appointments:
                    language = patient.preferred_language or "en"

                    message = get_outbound_prompt(
                        campaign_type="follow_up",
                        language=language,
                        patient_name=patient.name,
                        doctor_name=doctor.name,
                    )

                    campaign = OutboundCampaign(
                        name=f"Follow-up - {patient.name} - {appointment.appointment_date}",
                        campaign_type=CampaignType.FOLLOW_UP,
                        target_patient_ids=[appointment.patient_id],
                        message_template=message,
                        language=language,
                        scheduled_at=datetime.now(),
                        status=CampaignStatus.PENDING,
                    )
                    db.add(campaign)
                    follow_up_count += 1

                logger.info(f"Created {follow_up_count} follow-up reminders")

        except Exception as e:
            logger.error(f"Error in follow-up reminder job: {e}", exc_info=True)

    async def process_pending_campaigns(self):
        """
        Process pending outbound campaigns.
        In production, this would trigger actual calls via telephony API.
        """
        logger.info("Processing pending campaigns")

        try:
            async with get_db_context() as db:
                result = await db.execute(
                    select(OutboundCampaign).where(
                        and_(
                            OutboundCampaign.status == CampaignStatus.PENDING,
                            OutboundCampaign.scheduled_at <= datetime.now()
                        )
                    ).limit(10)
                )

                campaigns = result.scalars().all()

                for campaign in campaigns:
                    try:
                        # Mark as in progress
                        await db.execute(
                            update(OutboundCampaign)
                            .where(OutboundCampaign.id == campaign.id)
                            .values(status=CampaignStatus.IN_PROGRESS)
                        )

                        # Process each target patient
                        for patient_id in campaign.target_patient_ids:
                            await self._process_campaign_for_patient(
                                campaign=campaign,
                                patient_id=patient_id
                            )

                        # Mark as completed
                        await db.execute(
                            update(OutboundCampaign)
                            .where(OutboundCampaign.id == campaign.id)
                            .values(
                                status=CampaignStatus.COMPLETED,
                                completed_count=len(campaign.target_patient_ids)
                            )
                        )

                        logger.info(f"Campaign {campaign.id} processed successfully")

                    except Exception as e:
                        logger.error(f"Error processing campaign {campaign.id}: {e}")
                        await db.execute(
                            update(OutboundCampaign)
                            .where(OutboundCampaign.id == campaign.id)
                            .values(
                                status=CampaignStatus.FAILED,
                                failed_count=len(campaign.target_patient_ids)
                            )
                        )

        except Exception as e:
            logger.error(f"Error in process_pending_campaigns: {e}", exc_info=True)

    async def _process_campaign_for_patient(
        self,
        campaign: OutboundCampaign,
        patient_id: str
    ):
        """
        Process a campaign for a specific patient.
        In production: trigger actual phone call via Twilio/similar.
        For now: logs the campaign message.
        """
        logger.info(
            f"[OUTBOUND CAMPAIGN] Type={campaign.campaign_type} "
            f"Patient={patient_id} "
            f"Language={campaign.language} "
            f"Message='{campaign.message_template[:100]}...'"
        )
        # TODO: Integrate with telephony provider (Twilio, Exotel, etc.)
        # await telephony_client.make_call(
        #     to=patient_phone,
        #     message=campaign.message_template,
        #     language=campaign.language
        # )

    async def cleanup_expired_data(self):
        """Clean up old data to maintain performance."""
        logger.info("Running cleanup job")
        # In production: clean up old conversation logs, expired sessions, etc.

    async def create_manual_campaign(
        self,
        name: str,
        campaign_type: str,
        patient_ids: List[str],
        message_template: str,
        language: str = "en",
        scheduled_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a manual outbound campaign.

        Args:
            name: Campaign name
            campaign_type: Type of campaign
            patient_ids: List of target patient IDs
            message_template: Message to send
            language: Language code
            scheduled_at: When to send (default: now)

        Returns:
            Created campaign data
        """
        async with get_db_context() as db:
            campaign = OutboundCampaign(
                name=name,
                campaign_type=campaign_type,
                target_patient_ids=patient_ids,
                message_template=message_template,
                language=language,
                scheduled_at=scheduled_at or datetime.now(),
                status=CampaignStatus.PENDING,
            )
            db.add(campaign)
            await db.flush()

            logger.info(f"Created manual campaign: {campaign.id} - {name}")

            return {
                "id": campaign.id,
                "name": campaign.name,
                "campaign_type": campaign.campaign_type,
                "patient_count": len(patient_ids),
                "scheduled_at": campaign.scheduled_at.isoformat(),
                "status": campaign.status,
            }

    async def get_campaign_stats(self) -> Dict[str, Any]:
        """Get campaign statistics."""
        async with get_db_context() as db:
            result = await db.execute(select(OutboundCampaign))
            campaigns = result.scalars().all()

            stats = {
                "total": len(campaigns),
                "pending": sum(1 for c in campaigns if c.status == CampaignStatus.PENDING),
                "in_progress": sum(1 for c in campaigns if c.status == CampaignStatus.IN_PROGRESS),
                "completed": sum(1 for c in campaigns if c.status == CampaignStatus.COMPLETED),
                "failed": sum(1 for c in campaigns if c.status == CampaignStatus.FAILED),
                "total_patients_reached": sum(c.completed_count for c in campaigns),
            }

            return stats


# Singleton instance
_campaign_scheduler: Optional[CampaignScheduler] = None


def get_campaign_scheduler() -> CampaignScheduler:
    """Get or create the campaign scheduler singleton."""
    global _campaign_scheduler
    if _campaign_scheduler is None:
        _campaign_scheduler = CampaignScheduler()
    return _campaign_scheduler