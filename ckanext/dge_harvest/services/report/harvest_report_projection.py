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
"""Helpers to project structured report messages to legacy harvest tables."""

from ckanext.harvest.model import HarvestGatherError, HarvestObjectError

from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_LEGACY_PROJECTION_GATHER,
    REPORT_LEGACY_PROJECTION_NONE,
    REPORT_LEGACY_PROJECTION_OBJECT,
    REPORT_ALLOWED_LEGACY_PROJECTIONS,
    REPORT_PHASE_FETCH,
    REPORT_PHASE_IMPORT,
)


LEGACY_PROJECTION_GATHER = REPORT_LEGACY_PROJECTION_GATHER
LEGACY_PROJECTION_OBJECT = REPORT_LEGACY_PROJECTION_OBJECT
LEGACY_PROJECTION_NONE = REPORT_LEGACY_PROJECTION_NONE
LEGACY_ALLOWED_PROJECTIONS = REPORT_ALLOWED_LEGACY_PROJECTIONS

LEGACY_STAGE_GATHER = "Gather"
LEGACY_STAGE_FETCH = "Fetch"
LEGACY_STAGE_IMPORT = "Import"
LEGACY_ALLOWED_STAGES = (
    LEGACY_STAGE_GATHER,
    LEGACY_STAGE_FETCH,
    LEGACY_STAGE_IMPORT,
)


def normalize_legacy_projection(value):
    """Normalize the configured legacy projection target.

    Returns ``None`` when the caller provides no value. Otherwise the value is
    compacted and validated against the closed set of supported projections.
    """
    if value is None:
        return None

    normalized = " ".join(str(value).strip().lower().split())
    if not normalized:
        return None
    if normalized not in LEGACY_ALLOWED_PROJECTIONS:
        raise ValueError(
            "legacy_projection must be one of {}".format(
                LEGACY_ALLOWED_PROJECTIONS
            )
        )
    return normalized


def resolve_legacy_projection(level, legacy_projection=None):
    """Resolve the effective legacy projection for one structured message.

    The new report is canonical, so omitted projections degrade to ``none``.
    Only blocking errors are allowed to reach legacy tables.
    """
    resolved_projection = normalize_legacy_projection(legacy_projection)
    if resolved_projection is None:
        resolved_projection = LEGACY_PROJECTION_NONE

    if resolved_projection != LEGACY_PROJECTION_NONE and level != "error":
        raise ValueError("Only error messages can be projected to legacy tables")

    return resolved_projection


def build_legacy_object_stage(phase):
    """Translate a structured phase into the legacy object error stage."""
    if phase == REPORT_PHASE_FETCH:
        return LEGACY_STAGE_FETCH
    if phase == REPORT_PHASE_IMPORT:
        return LEGACY_STAGE_IMPORT
    return LEGACY_STAGE_GATHER


def normalize_legacy_stage(value):
    """Normalize an explicit legacy stage when the caller already knows it."""
    if value is None:
        return None

    normalized = " ".join(str(value).strip().split())
    if not normalized:
        return None
    if normalized not in LEGACY_ALLOWED_STAGES:
        raise ValueError(
            "legacy_stage must be one of {}".format(LEGACY_ALLOWED_STAGES)
        )
    return normalized


def project_legacy_message(
    legacy_projection,
    display_message,
    harvest_job=None,
    harvest_object=None,
    phase=None,
    legacy_stage=None,
):
    """Write a structured message to the matching legacy table when required.

    ``gather`` messages are projected at job level, while ``object`` messages
    require a concrete harvest object. ``none`` is a no-op.
    """
    if legacy_projection == LEGACY_PROJECTION_NONE:
        return None

    if legacy_projection == LEGACY_PROJECTION_GATHER:
        if harvest_job is None:
            raise ValueError(
                "harvest_job is required for gather legacy projection"
            )
        HarvestGatherError.create(display_message, harvest_job)
        return legacy_projection

    if legacy_projection == LEGACY_PROJECTION_OBJECT:
        if harvest_object is None:
            raise ValueError(
                "harvest_object is required for object legacy projection"
            )
        resolved_stage = normalize_legacy_stage(legacy_stage)
        if resolved_stage is None:
            resolved_stage = build_legacy_object_stage(phase)
        HarvestObjectError.create(
            display_message,
            harvest_object,
            resolved_stage,
        )
        return legacy_projection

    raise ValueError(
        "Unsupported legacy_projection {}".format(legacy_projection)
    )
