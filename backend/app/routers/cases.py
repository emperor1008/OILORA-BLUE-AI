"""
Oilora Blue AI — Case Management API

Endpoints for creating, reading, updating, and deleting investigation cases.
"""

from fastapi import APIRouter, HTTPException, Query

from ..models.cases import CaseCreate, CaseUpdate
from ..models.common import BaseResponse, PaginatedResponse
from ..services.case_service import case_service
from ..services.file_service import file_service

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.post("", response_model=BaseResponse, status_code=201)
async def create_case(case_data: CaseCreate):
    """Create a new investigation case."""
    # Unexpected exceptions propagate to the global handler, which returns a
    # sanitized 500 response (no internal details) plus a request ID.
    case = case_service.create_case(case_data.model_dump())
    return BaseResponse(
        success=True,
        message="Case created successfully",
        data=case,
    )


@router.get("", response_model=PaginatedResponse)
async def list_cases(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List all investigation cases with pagination."""
    cases, total = case_service.list_cases(offset=offset, limit=limit)
    return PaginatedResponse(
        success=True,
        data=cases,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{case_id}", response_model=BaseResponse)
async def get_case(case_id: str):
    """Get detailed information about a specific case."""
    case = case_service.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    # Attach files
    files = file_service.get_case_files(case_id)
    case["files"] = files

    return BaseResponse(success=True, data=case)


@router.patch("/{case_id}", response_model=BaseResponse)
async def update_case(case_id: str, update_data: CaseUpdate):
    """Update a case's metadata."""
    case = case_service.update_case(case_id, update_data.model_dump(exclude_unset=True))
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    return BaseResponse(
        success=True,
        message="Case updated successfully",
        data=case,
    )


@router.delete("/{case_id}", response_model=BaseResponse)
async def delete_case(case_id: str):
    """Delete a case and all associated data."""
    deleted = case_service.delete_case(case_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    return BaseResponse(success=True, message="Case deleted successfully")


@router.get("/{case_id}/status", response_model=BaseResponse)
async def get_case_status(case_id: str):
    """Get the processing status of a case."""
    case = case_service.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    return BaseResponse(
        success=True,
        data={
            "case_id": case_id,
            "status": case["status"],
            "current_stage": case["current_stage"],
            "dataset_ready": case["dataset_ready"],
            "system_ready": case["system_ready"],
        },
    )
