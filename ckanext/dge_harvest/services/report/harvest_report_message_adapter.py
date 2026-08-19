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
"""Adapt controlled process messages to the structured harvest report model."""

from ckanext.dge_harvest.services.report.harvest_report_adapter import (
    AdaptedHarvestReportMessage,
)
from ckanext.dge_harvest.services.report.harvest_report_context import (
    build_report_context,
)
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_CATEGORY_TECHNICAL,
    REPORT_ORIGIN_DCAT_AP_ES,
)
from ckanext.dge_harvest.services.report.harvest_report_message import (
    HarvestReportMessage,
)
from ckanext.dge_harvest.services.report.harvest_report_projection import (
    LEGACY_PROJECTION_GATHER,
    LEGACY_PROJECTION_NONE,
    LEGACY_STAGE_GATHER,
)
from ckanext.dge_harvest.services.report.harvest_report_text import (
    normalize_preserved_text,
    normalize_single_line_text,
)



DEFAULT_MESSAGE_ORIGIN = REPORT_ORIGIN_DCAT_AP_ES
DEFAULT_MESSAGE_CATEGORY = REPORT_CATEGORY_TECHNICAL
DEFAULT_DISPLAY_MESSAGE = (
    "Se ha registrado un mensaje durante el proceso de federación."
)


def adapt_message_to_report_message(
    raw_message,
    level,
    phase,
    kind,
    reason=None,
    origin=DEFAULT_MESSAGE_ORIGIN,
    category=DEFAULT_MESSAGE_CATEGORY,
    message_code=None,
    display_message=None,
    resource_uri=None,
    metadata_uri=None,
    term_uri=None,
    node_id=None,
    field=None,
    payload=None,
    more_info_url=None,
    legacy_projection=None,
    legacy_stage=LEGACY_STAGE_GATHER,
):
    """Adapt one controlled federation process message to the report model."""

    display_message = (
        normalize_preserved_text(display_message)
        or normalize_preserved_text(raw_message)
        or DEFAULT_DISPLAY_MESSAGE
    )

    resolved_legacy_projection = legacy_projection
    if resolved_legacy_projection is None:
        resolved_legacy_projection = (
            LEGACY_PROJECTION_GATHER
            if level == "error"
            else LEGACY_PROJECTION_NONE
        )

    message = HarvestReportMessage(
        level=level,
        phase=phase,
        origin=origin,
        category=category,
        message_code=message_code,
        display_message=display_message,
    )

    return AdaptedHarvestReportMessage(
        message=message,
        raw_message=normalize_single_line_text(raw_message),
        details_json=build_report_context(
            level=level,
            phase=phase,
            origin=origin,
            kind=kind,
            reason=reason,
            field=field,
            metadata_uri=metadata_uri,
            term_uri=term_uri,
            node_id=node_id,
            resource_uri=resource_uri,
            payload=payload,
        ),
        more_info_url=more_info_url,
        legacy_projection=resolved_legacy_projection,
        legacy_stage=legacy_stage,
    )