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
"""Adapt SHACL validation results to the structured harvest report model.

This module translates the neutral SHACL extraction produced by
``shacl_results_formatter`` into payloads ready for
``DgeHarvestReportService.create_message``. Functional classification is
delegated to the dedicated SHACL classifier module.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Optional

from ckanext.dge_harvest.services.report.harvest_report_message import (
    HarvestReportMessage,
)
from ckanext.dge_harvest.services.report.harvest_report_context import (
    build_report_context,
)
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_CATEGORY_SHACL,
    REPORT_PHASE_VALIDATION,
    REPORT_ORIGIN_DCAT_AP_ES
)
from ckanext.dge_harvest.services.report.harvest_report_projection import (
    LEGACY_PROJECTION_GATHER,
    LEGACY_PROJECTION_NONE,
    LEGACY_STAGE_GATHER,
)
from ckanext.dge_harvest.services.report.harvest_report_shacl_classifier import (
    get_shacl_message_code
)
from ckanext.dge_harvest.services.report.harvest_report_text import (
    normalize_preserved_text,
    normalize_single_line_text
)
from ckanext.dge_harvest.services.report.harvest_report_adapter import(
    AdaptedHarvestReportMessage
)
from ckanext.dge_harvest.services.report.harvest_report_severity import(
    MESSAGE_ALLOWED_LEVELS
)
from ckanext.dge_harvest.services.report.harvest_report_code_constants import(
    LEVEL_TO_CODE
)

DEFAULT_SHACL_DISPLAY_MESSAGE = "Resultado SHACL sin mensaje visible."

SHACL_SEVERITY_TO_LEVEL = {
    "Violation": "error",
    "sh:Violation": "error",
    "http://www.w3.org/ns/shacl#Violation": "error",
    "Warning": "warning",
    "sh:Warning": "warning",
    "http://www.w3.org/ns/shacl#Warning": "warning",
    "Info": "info",
    "sh:Info": "info",
    "http://www.w3.org/ns/shacl#Info": "info",
}

def adapt_shacl_result_to_report_message(
    result,
    entity_type=None,
    entity_uri=None,
    resource_uri=None,
    metadata_uri=None,
    extra_payload=None,
    origin=REPORT_ORIGIN_DCAT_AP_ES,
):
    """Translate one neutral SHACL result into the report message model.

    Args:
        result: Neutral SHACL result dictionary extracted from the validation
            graph.
        kind: Normalized report context kind.
        entity_uri: Optional validated entity URI.
        resource_uri: Optional affected resource URI. Defaults to
            ``entity_uri`` when omitted.
        metadata_uri: Optional affected metadata or predicate URI.
        extra_payload: Optional additional structured context.
        origin: Technical origin emitting the SHACL message.

    Returns:
        AdaptedReportMessage: Payload ready to be passed to the common report
        service.

    Raises:
        ValueError: If the SHACL result does not expose a supported severity.
    """
    level = _get_shacl_result_level(result)
    display_message = _build_display_message(result)
    kind="shacl_validation_result",
    reason = (result or {}).get("constraint")
    message_code = get_shacl_message_code(
        level = level,
        phase = REPORT_PHASE_VALIDATION,
        reason=(result or {}).get("constraint"),
    )
    resource_uri = (result or {}).get("resource_uri")
    metadata_uri = (result or {}).get("metadata_uri")

    message = HarvestReportMessage(
        level=level,
        phase=REPORT_PHASE_VALIDATION,
        origin=origin,
        category=REPORT_CATEGORY_SHACL,
        message_code=message_code,
        display_message=display_message,
    )

    return AdaptedHarvestReportMessage(
        message=message,
        raw_message=display_message,
        details_json=_build_details_json(
            result=result,
            level=level,
            kind=kind,
            reason=reason,
            entity_type=entity_type,
            entity_uri=entity_uri,
            resource_uri=resource_uri,
            metadata_uri=metadata_uri,
            extra_payload=extra_payload,
            origin=origin,
        ),
        more_info_url=_resolve_more_info_url(result),
        legacy_projection=_resolve_legacy_projection(level),
        legacy_stage=LEGACY_STAGE_GATHER,
    )


def adapt_shacl_results_to_report_messages(results):
    """Translate many neutral SHACL results into report message payloads."""
    return [
        adapt_shacl_result_to_report_message(result)
        for result in (results or [])
    ]


def _get_shacl_result_level(result):
    """Map SHACL severity to a HarvestReportMessage level."""
    severity = (result or {}).get("severity")

    level = SHACL_SEVERITY_TO_LEVEL.get(severity)

    if level not in MESSAGE_ALLOWED_LEVELS:
        raise ValueError(
            "Unsupported SHACL severity {!r}".format(severity)
        )
    return level


def _build_display_message(result):
    """Resolve the visible SHACL message with stable fallbacks."""
    message_text = (result or {}).get("message")
    return normalize_preserved_text(message_text) or DEFAULT_SHACL_DISPLAY_MESSAGE


def _resolve_legacy_projection(level):
    """Project only SHACL blocking errors to the legacy gather table."""
    if level == "error":
        return LEGACY_PROJECTION_GATHER
    return LEGACY_PROJECTION_NONE


def _resolve_more_info_url(result):
    """Resolve the SHACL help URL from the neutral result """
    return normalize_single_line_text((result or {}).get("more_info_url"))


def _build_details_json(
    result,
    level,
    kind,
    reason=None,
    entity_type=None,
    entity_uri=None,
    resource_uri=None,
    metadata_uri=None,
    extra_payload=None,
    origin=REPORT_ORIGIN_DCAT_AP_ES,
):
    """Build structured context for one SHACL validation result."""
    payload = {
        "shacl_result": result,
    }

    if entity_type:
        payload["entity_type"] = entity_type

    if entity_uri:
        payload["entity_uri"] = entity_uri

    payload.update(extra_payload or {})

    return build_report_context(
        level=level,
        phase=REPORT_PHASE_VALIDATION,
        origin=origin,
        kind=kind,
        reason=reason,
        metadata_uri=metadata_uri,
        resource_uri=resource_uri or entity_uri,
        payload=payload,
    )


