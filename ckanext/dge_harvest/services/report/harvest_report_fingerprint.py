# Copyright (C) 2026 Entidad Pública Empresarial Red.es
#
# This file is part of "dge-harvest (datos.gob.es)".
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Hash-based grouping helpers for structured harvest report messages."""

import hashlib
import json

from ckanext.dge_harvest.services.report.harvest_report_visible_message import (
    build_visible_report_message,
)


FINGERPRINT_FULL_PREFIX = "full"
FINGERPRINT_SEMANTIC_PREFIX = "semantic"


def build_fingerprint_full(
    level,
    display_message,
    more_info_url=None,
    message_code=None,
):
    """Build the visible grouping fingerprint for report rows.

    This fingerprint intentionally uses only the fields that change what the
    user sees in the materialized report row.
    """
    payload = {
        "level": _normalize_part(level),
        "display_message": _normalize_part(
            build_visible_report_message(display_message, message_code)
        ),
        "more_info_url": _normalize_part(more_info_url),
    }
    return _hash_payload(FINGERPRINT_FULL_PREFIX, payload)


def build_fingerprint_semantic(
    message_code=None,
    level=None,
    phase=None,
    category=None,
    display_message=None,
):
    """Build a stable semantic fingerprint for future support grouping.

    This fingerprint favors ``message_code`` whenever the message is
    cataloged, so support and future grouping can ignore technical noise such
    as origin-specific traces.
    """
    if message_code:
        payload = {
            "message_code": _normalize_part(message_code),
        }
    else:
        payload = {
            "level": _normalize_part(level),
            "phase": _normalize_part(phase),
            "category": _normalize_part(category),
            "display_message": _normalize_part(display_message),
        }
    return _hash_payload(FINGERPRINT_SEMANTIC_PREFIX, payload)


def _normalize_part(value):
    """Normalize one fingerprint component without changing its semantics."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def _hash_payload(prefix, payload):
    """Return a stable prefixed hash for a canonical JSON payload."""
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    return "{}:{}".format(prefix, digest)
