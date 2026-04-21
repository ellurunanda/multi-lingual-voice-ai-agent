"""Outbound campaign management REST API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from scheduler.campaign_scheduler import get_campaign_scheduler

router = APIRouter()


class CreateCampaignRequest(BaseModel):
    name: str = Field(..., description="Campaign name")
    campaign_type: str = Field(..., description="Type: reminder/follow_up/vaccination/checkup")
    patient_ids: List[str] = Field(..., description="List of target patient IDs")
    message_template: str = Field(..., description="Message template")
    language: str = Field(default="en", description="Language code (en/hi/ta/te)")
    scheduled_at: Optional[str] = Field(None, description="Schedule time (ISO format)")


@router.post("/")
async def create_campaign(request: CreateCampaignRequest):
    """Create a new outbound campaign."""
    scheduler = get_campaign_scheduler()

    scheduled_at = None
    if request.scheduled_at:
        try:
            scheduled_at = datetime.fromisoformat(request.scheduled_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scheduled_at format")

    result = await scheduler.create_manual_campaign(
        name=request.name,
        campaign_type=request.campaign_type,
        patient_ids=request.patient_ids,
        message_template=request.message_template,
        language=request.language,
        scheduled_at=scheduled_at,
    )

    return result


@router.get("/stats")
async def get_campaign_stats():
    """Get campaign statistics."""
    scheduler = get_campaign_scheduler()
    stats = await scheduler.get_campaign_stats()
    return stats


@router.post("/trigger-reminders")
async def trigger_reminders():
    """Manually trigger appointment reminder job."""
    scheduler = get_campaign_scheduler()
    await scheduler.send_appointment_reminders()
    return {"message": "Reminder job triggered successfully"}


@router.post("/trigger-follow-ups")
async def trigger_follow_ups():
    """Manually trigger follow-up reminder job."""
    scheduler = get_campaign_scheduler()
    await scheduler.send_follow_up_reminders()
    return {"message": "Follow-up job triggered successfully"}