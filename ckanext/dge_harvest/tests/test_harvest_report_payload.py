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

import json

from ckanext.dge_harvest.services.report.harvest_report_payload import (
    DETAILS_JSON_MAX_LENGTH,
    RAW_MESSAGE_MAX_LENGTH,
    normalize_details_json,
    normalize_raw_message,
)


def test_normalize_raw_message_truncates_and_removes_null_bytes():
    raw_message = "a" * (RAW_MESSAGE_MAX_LENGTH + 10) + "\x00"

    normalized = normalize_raw_message(raw_message)

    assert len(normalized) == RAW_MESSAGE_MAX_LENGTH
    assert normalized.endswith("...[truncated]")
    assert "\x00" not in normalized


def test_normalize_details_json_serializes_compact_valid_json():
    normalized = normalize_details_json(
        {
            "message": "value",
            "items": [1, None, True],
        }
    )

    assert json.loads(normalized) == {
        "message": "value",
        "items": [1, None, True],
    }
    assert " " not in normalized


def test_normalize_details_json_wraps_plain_text_as_json_string():
    normalized = normalize_details_json("plain text")

    assert json.loads(normalized) == "plain text"


def test_normalize_details_json_truncates_large_payload():
    normalized = normalize_details_json({"payload": "a" * DETAILS_JSON_MAX_LENGTH})
    parsed = json.loads(normalized)

    assert len(normalized) <= DETAILS_JSON_MAX_LENGTH
    assert parsed["_truncated"] is True
    assert parsed["preview"].endswith("...[truncated]")
