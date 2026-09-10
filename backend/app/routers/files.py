"""
Oilora Blue AI — File Management API

Endpoints for uploading, validating, and managing data files.
"""

import logging
import os
import shutil
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from .. import config
from ..models.common import BaseResponse
from ..services.case_service import case_service
from ..services.file_service import file_service

logger = logging.getLogger("oilora_blue.files")

router = APIRouter(prefix="/api/cases", tags=["files"])


async def _store_file(
    case_id: str,
    request: Request,
    file: UploadFile,
    file_type: str,
    product_identifier: str | None = None,
    acquisition_time: str | None = None,
    provenance_source: str | None = None,
    polarization: str | None = None,
):
    """
    Upload and validate a data file for a case.

    The file is validated for:
    - Extension correctness
    - File size limits
    - Magic byte signatures
    - Path safety
    - Filename sanitization

    For ``sar`` uploads, optional Sentinel-1 provenance fields (product
    identifier, acquisition time, source, polarization) are validated and
    stored. A derived Sentinel-1 GeoTIFF without these fields is still
    registered, but the map honestly reports that provenance is incomplete
    instead of claiming verified Sentinel-1 input.

    On success, the file is stored and registered with a SHA-256 checksum.
    Temporary upload directories are always removed, on success and failure.
    """
    # Check case exists
    case = case_service.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    # Validate file type
    valid_types = {"sar", "ais", "environmental", "mask", "boundary", "other"}
    if file_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file_type '{file_type}'. Must be one of: {valid_types}",
        )

    # Check file was provided
    if file.filename is None or file.filename == "":
        raise HTTPException(status_code=400, detail="No file provided")

    # Create temp file inside the data directory
    safe_name = file_service.sanitize_filename(file.filename)
    temp_dir = tempfile.mkdtemp(dir=config.settings.DATA_DIR)
    temp_path = os.path.join(temp_dir, safe_name)

    try:
        # Stream upload to temp file
        total_size = 0
        chunk_size = 1024 * 1024  # 1 MB chunks
        with open(temp_path, "wb") as buffer:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > config.settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large: exceeds {config.settings.MAX_UPLOAD_SIZE_MB} MB limit",
                    )
                buffer.write(chunk)

        # Optional Sentinel-1 provenance: validate before registration so an
        # invalid acquisition time is rejected up front, and normalize it to
        # canonical UTC for storage.
        extra_metadata = None
        if file_type == "sar":
            provenance_errors = file_service.validate_sar_provenance(
                product_identifier,
                acquisition_time,
                provenance_source,
                polarization,
            )
            if provenance_errors:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": "Sentinel-1 provenance validation failed",
                        "errors": provenance_errors,
                    },
                )
            if acquisition_time:
                from ..validation import normalize_iso_utc

                acquisition_time = normalize_iso_utc(acquisition_time)
            extra_metadata = {
                key: value
                for key, value in {
                    "product_identifier": product_identifier,
                    "acquisition_time": acquisition_time,
                    "provenance_source": provenance_source,
                    "polarization": polarization,
                }.items()
                if value is not None
            }

        # Validate and register
        result = file_service.register_file(
            case_id=case_id,
            file_path=temp_path,
            original_filename=file.filename,
            file_type=file_type,
            extra_metadata=extra_metadata,
        )

        if result is None:
            # Validation failed — return the safe, specific validation errors
            validation = file_service.validate_upload(temp_path, file.filename, file_type)
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "File validation failed",
                    "errors": validation["errors"],
                    "warnings": validation["warnings"],
                },
            )

        return BaseResponse(
            success=True,
            message="File uploaded and validated successfully",
            data=result,
        )

    except HTTPException:
        raise
    except Exception:
        # Never leak internal error details to the client. Log the internal
        # reference ID and the sanitized exception, return a safe envelope.
        request_id = getattr(request.state, "request_id", None) or "unknown"
        logger.exception(
            "Upload failed: case=%s request_id=%s",
            case_id,
            request_id,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Upload failed",
                "error_code": "UPLOAD_FAILED",
                "request_id": request_id,
            },
        )
    finally:
        # Remove the temporary upload directory in every outcome
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/{case_id}/files", response_model=BaseResponse, status_code=201)
async def upload_file(
    case_id: str,
    request: Request,
    file: UploadFile = File(..., description="Data file to upload"),
    file_type: str = Form(..., description="File type: sar|ais|environmental|mask|boundary|other"),
    product_identifier: str | None = Form(
        None, description="Sentinel-1 product identifier (e.g. S1A_IW_GRDH_1SDV_...)"
    ),
    acquisition_time: str | None = Form(
        None, description="ISO 8601 acquisition time (timezone required)"
    ),
    provenance_source: str | None = Form(
        None, description="Dataset publisher / source URL / DOI for Sentinel-1 input"
    ),
    polarization: str | None = Form(None, description="Polarization, e.g. VV or VH (Sentinel-1)"),
):
    """
    Upload and validate a data file for a case.

    The file is validated for extension correctness, size limits, magic byte
    signatures, path safety and filename sanitization. For ``sar`` uploads,
    optional Sentinel-1 provenance fields are validated and stored.
    """
    return await _store_file(
        case_id=case_id,
        request=request,
        file=file,
        file_type=file_type,
        product_identifier=product_identifier,
        acquisition_time=acquisition_time,
        provenance_source=provenance_source,
        polarization=polarization,
    )


@router.post("/{case_id}/sar-sources", response_model=BaseResponse, status_code=201)
async def register_sar_source(
    case_id: str,
    request: Request,
    file: UploadFile = File(
        ..., description="Sentinel-1 SAFE ZIP or derived georeferenced GeoTIFF"
    ),
    source_kind: str = Form(
        "derived_geotiff",
        description="derived_geotiff | original_safe_zip | downloaded_catalogue_product",
    ),
    product_identifier: str | None = Form(
        None, description="Sentinel-1 product identifier (e.g. S1A_IW_GRDH_1SDV_...)"
    ),
    acquisition_time: str | None = Form(
        None, description="ISO 8601 acquisition time (timezone required)"
    ),
    provenance_source: str | None = Form(
        None, description="Dataset publisher / official product/source URL"
    ),
    polarization: str | None = Form(None, description="Polarization, e.g. VV or VV+VH"),
):
    """
    Register an authentic Sentinel-1 source for a case.

    Accepts a derived georeferenced Sentinel-1 GeoTIFF or a Sentinel-1 SAFE
    ZIP. ``source_kind`` plus the mandatory provenance fields determine how the
    file is labelled: without verifiable provenance a raster is never marked
    as verified Sentinel-1 input. PNG/JPEG screenshots are rejected by the
    underlying content validation. Returns the granular SAR state afterwards.
    """
    if source_kind not in ("derived_geotiff", "original_safe_zip", "downloaded_catalogue_product"):
        raise HTTPException(status_code=422, detail=f"Invalid source_kind: {source_kind}")
    if source_kind == "original_safe_zip":
        raise HTTPException(
            status_code=422,
            detail=(
                "Original Sentinel-1 SAFE archive ingestion requires the SAFE "
                "manifest-validation gate, which is not yet implemented. "
                "Register a derived georeferenced Sentinel-1 GeoTIFF instead, "
                "or register the product through the standard case file workflow."
            ),
        )
    # Derived GeoTIFF / downloaded catalogue product path: content and
    # provenance validation happens in the shared upload+validation flow.
    result = await _store_file(
        case_id=case_id,
        request=request,
        file=file,
        file_type="sar",
        product_identifier=product_identifier,
        acquisition_time=acquisition_time,
        provenance_source=provenance_source,
        polarization=polarization,
    )

    # Report the granular, honest SAR state for the case afterwards.
    from ..services.map_service import map_service

    overlay = map_service.get_sar_overlay(case_id)
    stored = result.data if isinstance(result, BaseResponse) else result
    return BaseResponse(
        success=True,
        message="Sentinel-1 SAR source registered",
        data={"file": stored, "sar_overlay": overlay},
    )


@router.get("/{case_id}/files", response_model=BaseResponse)
async def list_files(case_id: str):
    """List all files registered for a case."""
    case = case_service.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    files = file_service.get_case_files(case_id)
    return BaseResponse(success=True, data=files)


@router.get("/{case_id}/files/{file_id}", response_model=BaseResponse)
async def get_file(case_id: str, file_id: str):
    """Get details of a specific file."""
    file_info = file_service.get_file(file_id)
    if file_info is None:
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
    if file_info["case_id"] != case_id:
        raise HTTPException(status_code=404, detail=f"File not found in case {case_id}")

    return BaseResponse(success=True, data=file_info)


@router.get("/{case_id}/files/{file_id}/manifest", response_model=BaseResponse)
async def get_file_manifest(case_id: str, file_id: str):
    """Get the provenance manifest for a registered file.

    The manifest records where the file came from, its checksum, size, media
    format, geospatial metadata where readable, and the granular validation
    status. No absolute filesystem paths are included.
    """
    case = case_service.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    manifest = file_service.get_file_manifest(case_id, file_id)
    if manifest is None:
        raise HTTPException(
            status_code=404,
            detail=f"No provenance manifest found for file {file_id}",
        )
    return BaseResponse(success=True, data=manifest)
