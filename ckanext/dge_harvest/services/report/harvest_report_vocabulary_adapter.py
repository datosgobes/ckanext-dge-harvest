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
"""Adapt vocabulary validation messages to the structured harvest report model.

This module translates literal vocabulary validation errors emitted during the
validation stage into payloads ready for
``DgeHarvestReportService.create_message``. Functional classification is
kept in the dedicated vocabulary classifier module.

Vocabulary validation currently emits only blocking validation errors: no
warning or informational levels are accepted by this adapter.
"""

from ckanext.dge_harvest.services.report.harvest_report_message import (
    HarvestReportMessage,
)
from ckanext.dge_harvest.services.report.harvest_report_context import (
    build_report_context,
)
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_CATEGORY_VOCABULARY,
    REPORT_PHASE_VALIDATION,
    REPORT_ORIGIN_DCAT_AP_ES,
)
from ckanext.dge_harvest.services.report.harvest_report_projection import (
    LEGACY_PROJECTION_GATHER,
    LEGACY_STAGE_GATHER,
)
from ckanext.dge_harvest.services.report.harvest_report_vocabulary_classifier import (
    get_vocabulary_error_message_code,
    VOCABULARY_REASON_INVALID_VALUE
)
from ckanext.dge_harvest.services.report.harvest_report_text import (
    normalize_preserved_text,
    normalize_single_line_text,
)
from ckanext.dge_harvest.services.report.harvest_report_adapter import (
    AdaptedHarvestReportMessage,
)
from ckanext.dge_harvest.services.report.harvest_report_severity import(
    MESSAGE_LEVEL_ERROR
)

DEFAULT_VOCABULARY_DISPLAY_MESSAGE = (
    "Error de vocabulario controlado sin mensaje visible."
)

ENTITY_TYPE_NAMES_ES = {
    "catalog": "catálogo",
    "dataset": "conjunto de datos",
    "dataservice": "servicio de datos",
    "distribution": "distribución",
}

ENTITY_TYPE_ARTICLES_ES = {
    "catalog": "el",
    "dataset": "el",
    "dataservice": "el",
    "distribution": "la",
}


def adapt_vocabulary_result_to_report_message(
    result,
    entity_type=None,
    entity_uri=None,
    resource_uri=None,
    metadata_uri=None,
    extra_payload=None,
    origin=REPORT_ORIGIN_DCAT_AP_ES,
):
    """Translate one vocabulary validation literal into the report model.

    Args:
        result: Literal vocabulary validation message. The current validator
            emits strings such as ``"<value> no es un elemento..."``.
        entity_type: Optional affected DCAT entity type: ``catalog``,
            ``dataset``, ``dataservice`` or ``distribution``.
        entity_uri: Optional affected entity URI.
        resource_uri: Optional affected resource URI. Defaults to
            ``entity_uri`` when omitted.
        metadata_uri: Optional affected metadata or predicate URI.
        extra_payload: Optional additional structured context.
        origin: Technical origin emitting the vocabulary validation message.

    Returns:
        AdaptedHarvestReportMessage: Payload ready for the common report
        service.
    """
    level = MESSAGE_LEVEL_ERROR
    raw_message = _build_raw_message(result)
    display_message = _build_display_message(
        raw_message=raw_message,
        entity_type=entity_type,
        entity_uri=entity_uri,
        resource_uri=resource_uri,
        metadata_uri=metadata_uri,
    )
    kind = "vocabulary_validation_result"
    message_code = get_vocabulary_error_message_code(
            phase=REPORT_PHASE_VALIDATION,
            reason=VOCABULARY_REASON_INVALID_VALUE,
        )

    message = HarvestReportMessage(
        level=level,
        phase=REPORT_PHASE_VALIDATION,
        origin=origin,
        category=REPORT_CATEGORY_VOCABULARY,
        message_code=message_code,
        display_message=display_message,
    )

    return AdaptedHarvestReportMessage(
        message=message,
        raw_message=raw_message,
        details_json=_build_details_json(
            result=result,
            raw_message=raw_message,
            level=level,
            kind=kind,
            reason="invalid_vocabulary_value",
            entity_type=entity_type,
            entity_uri=entity_uri,
            resource_uri=resource_uri,
            metadata_uri=metadata_uri,
            extra_payload=extra_payload,
            origin=origin,
        ),
        more_info_url=None,
        legacy_projection=LEGACY_PROJECTION_GATHER,
        legacy_stage=LEGACY_STAGE_GATHER,
    )


def adapt_vocabulary_results_to_report_messages(
    results,
    entity_type=None,
    entity_uri=None,
    resource_uri=None,
    metadata_uri=None,
    extra_payload=None,
    origin=REPORT_ORIGIN_DCAT_AP_ES,
):
    """Translate many vocabulary validation literals into report payloads."""
    return [
        adapt_vocabulary_result_to_report_message(
            result=result,
            entity_type=entity_type,
            entity_uri=entity_uri,
            resource_uri=resource_uri,
            metadata_uri=metadata_uri,
            extra_payload=extra_payload,
            origin=origin,
        )
        for result in (results or [])
    ]


def _build_raw_message(result):
    """Resolve the raw vocabulary message with stable fallbacks."""
    return (
        normalize_preserved_text(result)
        or DEFAULT_VOCABULARY_DISPLAY_MESSAGE
    )


def _build_display_message(
    raw_message,
    entity_type=None,
    entity_uri=None,
    resource_uri=None,
    metadata_uri=None,
):
    """Build a user-facing message enriched with affected entity context."""
    context_message = _build_entity_context_message(
        entity_type=entity_type,
        entity_uri=entity_uri,
        resource_uri=resource_uri,
        metadata_uri=metadata_uri,
    )

    if context_message:
        return "{} {}".format(context_message, raw_message)
    return raw_message


def _build_entity_context_message(
    entity_type=None,
    entity_uri=None,
    resource_uri=None,
    metadata_uri=None,
):
    """Return a compact Spanish context prefix for the affected entity."""
    target_uri = resource_uri or entity_uri

    if not entity_type and not target_uri and not metadata_uri:
        return None

    parts = []

    if entity_type:
        entity_name = ENTITY_TYPE_NAMES_ES.get(entity_type, entity_type)
        article = ENTITY_TYPE_ARTICLES_ES.get(entity_type, "el")
        parts.append("En {} {}".format(article, entity_name))
    else:
        parts.append("En el recurso")

    if target_uri:
        parts.append("{}".format(target_uri))

    if metadata_uri:
        parts.append("para el metadato {}".format(metadata_uri))

    return "{}:".format(" ".join(parts))


def _build_details_json(
    result,
    raw_message,
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
    """Build structured context for one vocabulary validation result."""
    payload = {
        "vocabulary_result": result,
        "vocabulary_message": raw_message,
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
