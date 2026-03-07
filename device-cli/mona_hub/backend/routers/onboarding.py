from fastapi import APIRouter

from backend.models.onboarding_state import (
    OnboardingState,
    ProfileData,
    ProgressUpdate,
)
from backend.services import profile

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/state", response_model=OnboardingState)
async def get_state():
    return profile.get_onboarding_state()


@router.put("/profile", response_model=OnboardingState)
async def update_profile(data: ProfileData):
    state = profile.save_profile(data.model_dump())
    return state


@router.put("/progress", response_model=OnboardingState)
async def update_progress(update: ProgressUpdate):
    state = profile.update_progress(update.phase, update.step, update.completed)
    return state


@router.post("/complete", response_model=OnboardingState)
async def complete_onboarding():
    state = profile.mark_complete()
    return state
