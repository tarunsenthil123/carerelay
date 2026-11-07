from datetime import datetime
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    status,
)
from pydantic import (
    BaseModel,
    ConfigDict,
)

from backend.app.models.enums import (
    VerificationMethod,
)
from backend.app.models.events import (
    CareEvent,
    CareEventDraft,
)
from backend.app.services.event_repository import (
    InMemoryEventRepository,
)


router = APIRouter(
    prefix="/events",
    tags=["events"],
)


class ConfirmEventRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    verification_method: VerificationMethod
    verified_at: datetime
    verified_by: str | None = None


def get_event_repository(
    request: Request,
) -> InMemoryEventRepository:
    return request.app.state.event_repository


@router.post(
    "",
    response_model=CareEvent,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    draft: CareEventDraft,
    request: Request,
):
    repository = get_event_repository(
        request
    )

    try:
        return repository.create_event(
            draft
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/{event_id}/confirm",
    response_model=CareEvent,
)
def confirm_event(
    event_id: UUID,
    body: ConfirmEventRequest,
    request: Request,
):
    repository = get_event_repository(
        request
    )

    try:
        return repository.confirm_event(
            event_id,
            verification_method=(
                body.verification_method
            ),
            verified_at=body.verified_at,
            verified_by=body.verified_by,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/{event_id}/deny",
    response_model=CareEvent,
)
def deny_event(
    event_id: UUID,
    request: Request,
):
    repository = get_event_repository(
        request
    )

    try:
        return repository.deny_event(
            event_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/{event_id}/amend",
    response_model=CareEvent,
    status_code=status.HTTP_201_CREATED,
)
def amend_event(
    event_id: UUID,
    draft: CareEventDraft,
    request: Request,
):
    repository = get_event_repository(
        request
    )

    try:
        return repository.amend_event(
            event_id,
            draft,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/effective/{recipient_id}",
    response_model=list[CareEvent],
)
def get_effective_timeline(
    recipient_id: str,
    request: Request,
):
    repository = get_event_repository(
        request
    )

    try:
        return repository.get_effective_timeline(
            recipient_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc