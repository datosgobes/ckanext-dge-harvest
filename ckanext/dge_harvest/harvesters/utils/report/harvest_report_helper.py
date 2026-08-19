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

"""Helpers for harvest-stage report persistence.

This module centralizes the small set of orchestration helpers used by DGE
harvesters to persist structured gather errors, info messages and the final
cleanup path for unsuccessful gather stages.
"""

import logging

from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_CATEGORY_TECHNICAL,
    REPORT_ORIGIN_DCAT_AP_ES,
    REPORT_LEGACY_PROJECTION_NONE,
)
from ckanext.dge_harvest.services.report.harvest_report_projection import (
    LEGACY_STAGE_GATHER,
    LEGACY_STAGE_IMPORT
)

from ckanext.dge_harvest.services.report.harvest_report_error_writer import (
    save_adapted_gather_report_message,
)
from ckanext.dge_harvest.services.report.harvest_report_message_adapter import (
    adapt_message_to_report_message
)
from ckanext.dge_harvest.services.report.harvest_report_message_adapter import (
    adapt_message_to_report_message
)
from ckanext.dge_harvest.services.report.harvest_report_error_writer import (
    save_adapted_gather_report_message,
)
from ckanext.dge_harvest.services.report.harvest_report_error_writer import (
    save_adapted_object_report_message
)
from ckanext.dge_harvest.services.report.harvest_report_message_adapter import (
    adapt_message_to_report_message
)

log = logging.getLogger(__name__)


class ReportHelperMixin(object):
    """Mixin with common method for report helpers for DGE harvesters."""
    report_origin = REPORT_ORIGIN_DCAT_AP_ES

    def _get_report_origin(self):
        return self.report_origin

    def _build_exception_payload(self, exception, payload=None):
        resolved_payload = dict(payload or {})

        if exception is not None:
            resolved_payload.setdefault(
                "exception_class",
                exception.__class__.__name__,
            )
            resolved_payload.setdefault(
                "exception_message",
                str(exception),
            )
            resolved_payload.setdefault(
                "exception_context",
                getattr(exception, "context", None),
            )

        return resolved_payload

    def _build_default_kwargs(self, exception, **kwargs):
        kwargs.setdefault("origin", self._get_report_origin())
        kwargs.setdefault("legacy_projection", REPORT_LEGACY_PROJECTION_NONE)
        payload = dict(kwargs.pop("payload", None) or {})

        if exception is not None:
            payload = self._build_exception_payload(exception, payload)
            kwargs["reason"] = kwargs.get("reason") or type(exception).__name__

        kwargs["payload"] = payload
        return kwargs

class GatherReportHelperMixin(ReportHelperMixin):
    """Mixin with structured gather report helpers for DGE harvesters."""
    report_origin = REPORT_ORIGIN_DCAT_AP_ES
    def _save_structured_gather_report_message(
        self,
        harvest_job,
        level,
        phase,
        kind,
        reason=None,
        origin=None,
        category=REPORT_CATEGORY_TECHNICAL,
        raw_message=None,
        display_message=None,
        resource_uri=None,
        metadata_uri=None,
        term_uri=None,
        node_id=None,
        field=None,
        payload=None,
        message_code=None,
        more_info_url=None,
        legacy_projection=None,
        legacy_stage=LEGACY_STAGE_GATHER,
    ):
        resolved_origin = origin or self._get_report_origin()
        adapted_message = adapt_message_to_report_message(
            raw_message=raw_message,
            level=level,
            phase=phase,
            kind=kind,
            reason=reason,
            origin=resolved_origin,
            category=category,
            resource_uri=resource_uri,
            metadata_uri=metadata_uri,
            term_uri=term_uri,
            node_id=node_id,
            field=field,
            payload=payload,
            message_code=message_code,
            display_message=display_message,
            more_info_url=more_info_url,
            legacy_projection=legacy_projection,
            legacy_stage=legacy_stage,
        )

        return save_adapted_gather_report_message(
            harvest_job=harvest_job,
            adapted_message=adapted_message,
        )
    
class ObjectReportHelperMixin(ReportHelperMixin):
    """Mixin with structured gather report helpers for DGE harvesters."""
    def _save_structured_object_report_message(
        self,
        harvest_object,
        level,
        kind,
        phase,
        reason=None,
        origin=None,
        category=REPORT_CATEGORY_TECHNICAL,
        raw_message=None,
        display_message=None,
        resource_uri=None,
        metadata_uri=None,
        term_uri=None,
        node_id=None,
        field=None,
        payload=None,
        message_code=None,
        more_info_url=None,
        legacy_projection=None,
        legacy_stage=LEGACY_STAGE_IMPORT,
    ):

        adapted_message = adapt_message_to_report_message(
            raw_message=raw_message,
            level=level,
            phase=phase,
            kind=kind,
            reason=reason,
            origin=origin,
            category=category,
            resource_uri=resource_uri,
            metadata_uri=metadata_uri,
            term_uri=term_uri,
            node_id=node_id,
            field=field,
            payload=payload,
            message_code=message_code,
            display_message=display_message,
            more_info_url=more_info_url,
            legacy_projection=legacy_projection,
            legacy_stage=legacy_stage,
        )

        return save_adapted_object_report_message(
            harvest_object=harvest_object,
            adapted_message=adapted_message,
        )
    