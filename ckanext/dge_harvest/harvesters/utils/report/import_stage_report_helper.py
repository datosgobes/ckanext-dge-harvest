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
    REPORT_PHASE_IMPORT
)
from ckanext.dge_harvest.services.report.harvest_report_projection import (
    LEGACY_STAGE_IMPORT
)
from ckanext.dge_harvest.services.report.harvest_report_severity import (
    MESSAGE_LEVEL_INFO,
    MESSAGE_LEVEL_ERROR,
    MESSAGE_LEVEL_WARNING
)

from ckanext.dge_harvest.harvesters.utils.report.harvest_report_helper import (
    ObjectReportHelperMixin
)

log = logging.getLogger(__name__)


class ImportStageReportHelperMixin(ObjectReportHelperMixin):
    """Mixin with structured import report helpers for DGE harvesters."""
    report_origin = REPORT_ORIGIN_DCAT_AP_ES
   
    def _build_default_import_stage_kwargs(self, exception, **kwargs):
        kwargs.setdefault("origin", self._get_report_origin())
        kwargs["legacy_stage"] = LEGACY_STAGE_IMPORT
        kwargs["phase"] = REPORT_PHASE_IMPORT
        kwargs = self._build_default_kwargs(exception, **kwargs)
        return kwargs
    
    ## ERROR REPORT MESSAGES ##
    
    def _save_import_stage_structured_object_report_error(self, exception=None, **kwargs):
        kwargs = self._build_default_import_stage_kwargs(exception=exception, **kwargs)
        kwargs["level"] = MESSAGE_LEVEL_ERROR
        return self._save_structured_object_report_message(**kwargs)

    def _save_import_stage_technical_structured_object_report_error(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_TECHNICAL
        return self._save_import_stage_structured_object_report_error(exception, **kwargs)

    def _save_import_stage_common_structured_object_report_error(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_COMMON
        return self._save_import_stage_structured_object_report_error(exception, **kwargs)

    
    ## WARNING REPORT MESSAGES

    def _save_import_stage_structured_object_report_warning(self, exception=None, **kwargs):
        kwargs = self._build_default_import_stage_kwargs(exception=exception, **kwargs)
        kwargs["level"] = MESSAGE_LEVEL_WARNING
        kwargs.setdefault("legacy_projection",REPORT_LEGACY_PROJECTION_NONE,)
        return self._save_structured_object_report_message(**kwargs)

    def _save_import_stage_technical_structured_object_report_warning(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_TECHNICAL
        return self._save_import_stage_structured_object_report_warning(exception, **kwargs)

    def _save_import_stage_common_structured_object_report_warning(self, exception=None, **kwargs):
        kwargs["category"] = REPORT_CATEGORY_COMMON
        return self._save_import_stage_structured_object_report_warning(exception, **kwargs)

    #### INFO REPORT MESSAGES ###
 
    def _save_import_stage_structured_object_report_info(self, exception=None, **kwargs):
        kwargs = self._build_default_import_stage_kwargs(exception=exception, **kwargs)
        kwargs["level"] = MESSAGE_LEVEL_INFO
        kwargs.setdefault("legacy_projection",REPORT_LEGACY_PROJECTION_NONE,)
        return self._save_structured_object_report_message(**kwargs)

    def _save_import_stage_technical_structured_object_report_info(self, exception=None, **kwargs):
        kwargs.pop("category", None) or None
        kwargs["category"] = REPORT_CATEGORY_TECHNICAL
        return self._save_import_stage_structured_object_report_info(**kwargs)

    def _save_import_stage_common_structured_object_report_info(self, exception=None, **kwargs):
        kwargs.pop("category", None) or None
        kwargs["category"] = REPORT_CATEGORY_COMMON
        return self._save_import_stage_structured_object_report_info(**kwargs)

class DcatImportStageReportHelperMixin(ImportStageReportHelperMixin):
    """DCAT-AP-ES-specific report helpers layered on top of the common mixin."""
    report_origin = REPORT_ORIGIN_DCAT_AP_ES

class NtiImportStageReportHelperMixin(ImportStageReportHelperMixin):
    """NTI-specific report helpers layered on top of the common mixin."""
    report_origin = REPORT_ORIGIN_NTI
