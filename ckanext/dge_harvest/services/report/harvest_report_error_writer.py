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
"""Structured gather/object error writers for DGE harvest.

This module centralizes the DGE-owned write path for errors that used to go to
legacy ``HarvestGatherError`` and ``HarvestObjectError`` tables. Error-level
messages dual-write to structured tables plus matching legacy tables, while
warnings and info stay only in structured tables.
"""

from ckanext.dge_harvest.services.report.harvest_report_context import (
    build_report_context,
)
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_CATEGORY_TECHNICAL,
    REPORT_LEGACY_PROJECTION_GATHER,
    REPORT_LEGACY_PROJECTION_OBJECT,
    REPORT_LEGACY_PROJECTION_NONE,
    REPORT_ORIGIN_DCAT_AP_ES,
)
from ckanext.dge_harvest.services.report.harvest_report_service import (
    create_harvest_message,
    create_adapted_harvest_message
)

from ckanext.dge_harvest.services.report.harvest_report_projection import (
    LEGACY_STAGE_GATHER,
)

def save_adapted_gather_report_message(harvest_job, adapted_message):
    """Persist an already adapted gather-level report message."""
    return create_adapted_harvest_message(
        harvest_job=harvest_job,
        adapted_message=adapted_message,
    )


def save_adapted_object_report_message(harvest_object, adapted_message):
    """Persist an already adapted object-level report message."""
    return create_adapted_harvest_message(
        harvest_object=harvest_object,
        adapted_message=adapted_message,
    )


def save_structured_gather_message(
    harvest_job,
    level,
    raw_message,
    display_message,
    phase,
    kind,
    reason=None,
    origin=REPORT_ORIGIN_DCAT_AP_ES,
    category=REPORT_CATEGORY_TECHNICAL,
    resource_uri=None,
    metadata_uri=None,
    term_uri=None,
    node_id=None,
    message_code=None,
    payload=None,
    more_info_url=None,
    legacy_projection=None,
    legacy_stage=LEGACY_STAGE_GATHER,
):
    """Persist one gather-level structured report message."""
    if legacy_projection is None:
        legacy_projection = (
            REPORT_LEGACY_PROJECTION_GATHER
            if level == "error"
            else REPORT_LEGACY_PROJECTION_NONE
        )

    return create_harvest_message(
        harvest_job=harvest_job,
        level=level,
        phase=phase,
        origin=origin,
        category=category,
        message_code=message_code,
        display_message=display_message,
        raw_message=raw_message,
        details_json=build_report_context(
            level=level,
            phase=phase,
            origin=origin,
            kind=kind,
            reason=reason,
            metadata_uri=metadata_uri,
            term_uri=term_uri,
            node_id=node_id,
            resource_uri=resource_uri,
            payload=payload or {},
        ),
        more_info_url=more_info_url,
        legacy_projection=legacy_projection,
        legacy_stage=legacy_stage,
    )


def save_structured_gather_error(**kwargs):
    """Persist one gather-level error."""
    kwargs["level"] = "error"
    return save_structured_gather_message(**kwargs)


def save_structured_gather_warning(**kwargs):
    """Persist one gather-level warning."""
    kwargs["level"] = "warning"
    kwargs.setdefault("legacy_projection", REPORT_LEGACY_PROJECTION_NONE)
    return save_structured_gather_message(**kwargs)


def save_structured_gather_info(**kwargs):
    """Persist one gather-level info message."""
    kwargs["level"] = "info"
    kwargs.setdefault("legacy_projection", REPORT_LEGACY_PROJECTION_NONE)
    return save_structured_gather_message(**kwargs)


def save_structured_object_message(
    harvest_object,
    level,
    raw_message,
    display_message,
    phase,
    kind,
    reason=None,
    origin=REPORT_ORIGIN_DCAT_AP_ES,
    category=REPORT_CATEGORY_TECHNICAL,
    resource_uri=None,
    metadata_uri=None,
    message_code=None,
    payload=None,
    more_info_url=None,
    legacy_projection=None,
    legacy_stage=None,
):
    """Persist one object-level structured report message."""
    if legacy_projection is None:
        legacy_projection = (
            REPORT_LEGACY_PROJECTION_OBJECT
            if level == "error"
            else REPORT_LEGACY_PROJECTION_NONE
        )

    return create_harvest_message(
        harvest_object=harvest_object,
        level=level,
        phase=phase,
        origin=origin,
        category=category,
        message_code=message_code,
        display_message=display_message,
        raw_message=raw_message,
        details_json=build_report_context(
            level=level,
            phase=phase,
            origin=origin,
            kind=kind,
            reason=reason,
            metadata_uri=metadata_uri,
            resource_uri=resource_uri,
            payload=payload or {},
        ),
        more_info_url=more_info_url,
        legacy_projection=legacy_projection,
        legacy_stage=legacy_stage,
    )


def save_structured_object_error(**kwargs):
    """Persist one object-level error."""
    kwargs["level"] = "error"
    return save_structured_object_message(**kwargs)


def save_structured_object_warning(**kwargs):
    """Persist one object-level warning."""
    kwargs["level"] = "warning"
    kwargs.setdefault("legacy_projection", REPORT_LEGACY_PROJECTION_NONE)
    return save_structured_object_message(**kwargs)


def save_structured_object_info(**kwargs):
    """Persist one object-level info message."""
    kwargs["level"] = "info"
    kwargs.setdefault("legacy_projection", REPORT_LEGACY_PROJECTION_NONE)
    return save_structured_object_message(**kwargs)
