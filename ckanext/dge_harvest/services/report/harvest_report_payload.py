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
"""Normalization helpers for internal raw payloads of report messages.

This module owns the normalization and bounding of ``raw_message`` and
``details_json`` so ORM validators can persist safe values without mixing them
with user-facing text.
"""

import json

from ckanext.dge_harvest.services.report.harvest_report_text import (
    clean_text,
    truncate_text,
)


RAW_MESSAGE_MAX_LENGTH = 8192
DETAILS_JSON_MAX_LENGTH = 32768
TRUNCATION_SUFFIX = "...[truncated]"
DETAILS_TRUNCATED_KEY = "_truncated"


def normalize_raw_message(raw_message):
    """Return a bounded text value for the internal raw message."""
    if raw_message is None:
        return None

    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8", "replace")
    else:
        raw_message = str(raw_message)

    raw_message = clean_text(raw_message)
    return truncate_text(raw_message, RAW_MESSAGE_MAX_LENGTH, TRUNCATION_SUFFIX)


def normalize_details_json(details):
    """Return bounded JSON text for structured internal details."""
    if details is None:
        return None

    normalized_details = _normalize_json_value(details)
    details_json = _json_dumps(normalized_details)

    if len(details_json) <= DETAILS_JSON_MAX_LENGTH:
        return details_json

    return _bounded_truncated_details_json(details_json)


def _normalize_json_value(value):
    """Convert arbitrary values into JSON-serializable bounded primitives."""
    if isinstance(value, str):
        value = clean_text(value)
        try:
            return _normalize_json_value(json.loads(value))
        except ValueError:
            return value

    if isinstance(value, bytes):
        return clean_text(value.decode("utf-8", "replace"))

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, dict):
        return {
            clean_text(str(key)): _normalize_json_value(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_normalize_json_value(item) for item in value]

    return clean_text(str(value))


def _json_dumps(value):
    """Serialize JSON in a compact and deterministic representation."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _preview_length():
    """Calculate preview room inside the truncated details JSON envelope."""
    fixed_payload = _json_dumps({DETAILS_TRUNCATED_KEY: True, "preview": ""})
    return DETAILS_JSON_MAX_LENGTH - len(fixed_payload) - len(TRUNCATION_SUFFIX)


def _bounded_truncated_details_json(details_json):
    """Build a truncated details JSON payload that never exceeds the limit."""
    preview = truncate_text(details_json, _preview_length(), TRUNCATION_SUFFIX)

    while True:
        payload = _json_dumps(
            {
                DETAILS_TRUNCATED_KEY: True,
                "preview": preview,
            }
        )
        if len(payload) <= DETAILS_JSON_MAX_LENGTH:
            return payload
        preview = truncate_text(preview, len(preview) - 1, TRUNCATION_SUFFIX)
