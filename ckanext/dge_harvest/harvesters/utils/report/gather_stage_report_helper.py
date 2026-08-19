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
    REPORT_CATEGORY_COMMON,
    REPORT_ORIGIN_DCAT_AP_ES,
    REPORT_ORIGIN_NTI,
    REPORT_LEGACY_PROJECTION_NONE,
    REPORT_LEGACY_PROJECTION_GATHER,
    REPORT_LEGACY_PROJECTION_OBJECT,
    REPORT_PHASE_PREPROCESSING,
)
from ckanext.dge_harvest.services.report.harvest_report_projection import (
    LEGACY_STAGE_GATHER
)
from ckanext.dge_harvest.services.report.harvest_report_severity import (
    MESSAGE_LEVEL_INFO,
    MESSAGE_LEVEL_ERROR,
    MESSAGE_LEVEL_WARNING
)

from ckanext.dge_harvest.services.report.harvest_report_common_classifier import(
    get_common_info_message_code,
)
from ckanext.dge_harvest.harvesters.utils.report.harvest_report_helper import (
    GatherReportHelperMixin,
    ObjectReportHelperMixin
)

log = logging.getLogger(__name__)


class GatherStageReportHelperMixin(GatherReportHelperMixin, ObjectReportHelperMixin):
    """Mixin with structured gather report helpers for DGE harvesters."""
    report_origin = REPORT_ORIGIN_DCAT_AP_ES

    def _build_default_gather_stage_kwargs(self, exception, **kwargs):
        kwargs.setdefault("origin", self._get_report_origin())
        kwargs["legacy_stage"] = LEGACY_STAGE_GATHER
        kwargs["legacy_projection"] = REPORT_LEGACY_PROJECTION_NONE
        kwargs = self._build_default_kwargs(exception, **kwargs)

        return kwargs


    ## GATHER ERROR REPORT MESSAGES ##
    def _save_structured_gather_report_error(self, exception=None, **kwargs):
        kwargs = self._build_default_gather_stage_kwargs(exception=exception, **kwargs)
        kwargs["level"] = MESSAGE_LEVEL_ERROR
        kwargs["legacy_projection"] = REPORT_LEGACY_PROJECTION_GATHER
        return self._save_structured_gather_report_message(**kwargs)

    def _save_technical_structured_gather_report_error(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_TECHNICAL
        return self._save_structured_gather_report_error(exception, **kwargs)

    def _save_common_structured_gather_report_error(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_COMMON
        return self._save_structured_gather_report_error(exception, **kwargs)

    def _finish_unsuccessful_structured_gather_stage(self, exception=None, **kwargs):
        self._save_structured_gather_report_error(exception, **kwargs)
        return []

    ## GATHER WARNING REPORT MESSAGES

    def _save_structured_gather_report_warning(self, exception=None, **kwargs):
        kwargs = self._build_default_gather_stage_kwargs(exception=exception, **kwargs)
        kwargs["level"] = MESSAGE_LEVEL_WARNING
        return self._save_structured_gather_report_message(**kwargs)

    def _save_technical_structured_gather_report_warning(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_TECHNICAL
        return self._save_structured_gather_report_warning(exception, **kwargs)

    def _save_common_structured_gather_report_warning(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_COMMON
        return self._save_structured_gather_report_warning(exception, **kwargs)

    #### GATHER INFO REPORT MESSAGES ###
 
    def _save_structured_gather_report_info(self, exception=None, **kwargs):
        kwargs = self._build_default_gather_stage_kwargs(exception=exception,**kwargs)
        kwargs["level"] = MESSAGE_LEVEL_INFO
        return self._save_structured_gather_report_message(**kwargs)

    def _save_technical_structured_gather_report_info(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_TECHNICAL
        return self._save_structured_gather_report_info(exception, **kwargs)

    def _save_common_structured_gather_report_info(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_COMMON
        return self._save_structured_gather_report_info(exception, **kwargs)

    ## OBJECT ERROR REPORT MESSAGES IN GATHER STAGE##
    def _save_gather_stage_structured_object_report_error(self, exception=None, **kwargs):
        kwargs = self._build_default_gather_stage_kwargs(exception=exception, **kwargs)
        kwargs["level"] = MESSAGE_LEVEL_ERROR
        kwargs["legacy_projection"] = REPORT_LEGACY_PROJECTION_OBJECT
        return self._save_structured_object_report_message(**kwargs)

    def _save_gather_stage_technical_structured_object_report_error(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_TECHNICAL
        return self._save_gather_stage_structured_object_report_error(exception, **kwargs)

    def _save_gather_stage_common_structured_object_report_error(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_COMMON
        return self._save_gather_stage_structured_object_report_error(exception, **kwargs)

    def _finish_unsuccessful_structured_gather_stage_object_stage(self, exception=None, **kwargs):
        self._save_gather_stage_structured_object_report_error(exception, **kwargs)
        return []

    ## OBJECT WARNING REPORT MESSAGES@

    def _save_gather_stage_structured_object_report_warning(self, exception=None, **kwargs):
        kwargs = self._build_default_gather_stage_kwargs(exception=exception, **kwargs)
        kwargs["level"] = MESSAGE_LEVEL_WARNING
        return self._save_structured_object_report_message(**kwargs)

    def _save_gather_stage_technical_structured_object_report_warning(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_TECHNICAL
        return self._save_gather_stage_structured_object_report_warning(exception, **kwargs)

    def _save_gather_stage_common_structured_object_report_warning(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_COMMON
        return self._save_gather_stage_structured_object_report_warning(exception, **kwargs)

    #### object INFO REPORT MESSAGES ###
 
    def _save_gather_stage_structured_object_report_info(self, exception=None, **kwargs):
        kwargs = self._build_default_gather_stage_kwargs(exception=exception,**kwargs)
        kwargs["level"] = MESSAGE_LEVEL_INFO
        return self._save_structured_object_report_message(**kwargs)

    def _save_gather_stage_technical_structured_object_report_info(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_TECHNICAL
        return self._save_gather_stage_structured_object_report_info(exception, **kwargs)

    def _save_gather_stage_common_structured_object_report_info(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_COMMON
        return self._save_gather_stage_structured_object_report_info(exception, **kwargs)
        
class DcatGatherStageReportHelperMixin(GatherStageReportHelperMixin):
    """NTI-specific report helpers layered on top of the common mixin."""
    report_origin = REPORT_ORIGIN_DCAT_AP_ES

    def _save_preprocessing_structured_gather_report_info_message(self, **kwargs):
        reason = kwargs.get("reason")
        kwargs["phase"] = REPORT_PHASE_PREPROCESSING
        kwargs["category"] = REPORT_CATEGORY_COMMON
        kwargs["message_code"] = get_common_info_message_code(phase=REPORT_PHASE_PREPROCESSING, reason=reason)
        return self._save_structured_gather_report_info(exception=None, **kwargs)

class NtiGatherStageReportHelperMixin(GatherStageReportHelperMixin):
    """NTI-specific report helpers layered on top of the common mixin."""
    report_origin = REPORT_ORIGIN_NTI
