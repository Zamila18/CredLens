"""Safe reading of uploaded files: a size cap while reading, and limits on unpacking archives.

Purpose: an upload is read in pieces and refused as soon as it passes its limit, instead of
    being read whole into memory first; a zip (a data bundle or an .xlsx workbook, which is a
    zip inside) is unpacked in counted pieces, so a small file that unpacks to gigabytes is
    refused (docs/audits/CREDLENS_END_TO_END_AUDIT.md, S5/S6).
Owner role: D (full-stack).
Implements: Phase 0 of docs/product/CREDLENS_PRODUCT_RECOVERY_BLUEPRINT.md.

The sizes written inside a zip are not trusted: only the bytes actually unpacked are counted.
Limits come from the `api` section of config/default.yaml.
"""

from __future__ import annotations

import io
import zipfile
import zlib
from typing import Any

from fastapi import Request

from src.api.common import api_error

CHUNK = 64 * 1024


class ArchiveRefused(ValueError):
    """An archive breaks a limit or cannot be read. The message is for the user."""


def archive_limits(config: dict[str, Any]) -> tuple[int, int]:
    """(largest total unpacked size in bytes, most members) from the config."""
    settings = config["api"]
    return int(settings["upload_max_unpacked_mb"]) * 1024 * 1024, int(
        settings["upload_max_archive_members"]
    )


async def read_capped(request: Request, limit: int) -> bytes:
    """The request body, refused with 413 as soon as it is larger than `limit` bytes."""
    megabytes = max(1, limit // (1024 * 1024))
    too_large = api_error(413, "file_too_large", f"The file is larger than {megabytes} MB.")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise too_large
    parts: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise too_large
        parts.append(chunk)
    return b"".join(parts)


def read_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int, budget: list[int]
) -> bytes:
    """One member, unpacked in pieces. `limit` caps the member; `budget` holds the bytes the
    whole archive may still unpack (shared between members, decreased here)."""
    parts: list[bytes] = []
    size = 0
    with archive.open(info) as handle:
        while chunk := handle.read(CHUNK):
            size += len(chunk)
            budget[0] -= len(chunk)
            if size > limit:
                raise ArchiveRefused(f"'{info.filename}' is larger than the limit for one file.")
            if budget[0] < 0:
                raise ArchiveRefused("The file unpacks to more data than is allowed.")
            parts.append(chunk)
    return b"".join(parts)


def check_archive(data: bytes, max_unpacked: int, max_members: int) -> None:
    """Unpack every member in counted pieces (keeping nothing) and refuse an archive that has
    too many members or unpacks to more than `max_unpacked` bytes in total.

    A file that is not a zip at all is left to the caller's own reader to refuse."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return
    with archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        if len(members) > max_members:
            raise ArchiveRefused("The file holds too many parts to be read safely.")
        budget = [max_unpacked]
        for info in members:
            try:
                with archive.open(info) as handle:
                    while chunk := handle.read(CHUNK):
                        budget[0] -= len(chunk)
                        if budget[0] < 0:
                            raise ArchiveRefused("The file unpacks to more data than is allowed.")
            except (zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError) as error:
                raise ArchiveRefused(
                    "The file is damaged or protected and cannot be read."
                ) from error
