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
"""Shared structural vocabulary for the harvest federation report.

This module centralizes the non-catalog dimensions used by the structured
report contract: phases, origins, categories and legacy projection targets.
It exists to avoid scattering string literals across harvesters, adapters,
catalog helpers and projection code.
"""
REPORT_PHASE_SETUP = "setup"
REPORT_PHASE_DOWNLOAD = "download"
REPORT_PHASE_FETCH = "fetch"
REPORT_PHASE_PREPROCESSING = "preprocessing"
REPORT_PHASE_VALIDATION = "validation"
REPORT_PHASE_STORAGE = "storage"
REPORT_PHASE_IMPORT = "import"
REPORT_PHASE_FALLBACK = "fallback"

REPORT_ALLOWED_PHASES = (
    REPORT_PHASE_SETUP,
    REPORT_PHASE_DOWNLOAD,
    REPORT_PHASE_FETCH,
    REPORT_PHASE_PREPROCESSING,
    REPORT_PHASE_VALIDATION,
    REPORT_PHASE_STORAGE,
    REPORT_PHASE_IMPORT,
    REPORT_PHASE_FALLBACK,
)

REPORT_ORIGIN_DCAT_AP_ES = "dcat_ap_es_harvester"
REPORT_ORIGIN_NTI = "nti_harvester"

REPORT_CATEGORY_COMMON = "common"
REPORT_CATEGORY_SHACL = "shacl"
REPORT_CATEGORY_VOCABULARY = "vocabulary"
REPORT_CATEGORY_TECHNICAL = "technical"

REPORT_LEGACY_PROJECTION_GATHER = "gather"
REPORT_LEGACY_PROJECTION_OBJECT = "object"
REPORT_LEGACY_PROJECTION_NONE = "none"

REPORT_ALLOWED_LEGACY_PROJECTIONS = (
    REPORT_LEGACY_PROJECTION_GATHER,
    REPORT_LEGACY_PROJECTION_OBJECT,
    REPORT_LEGACY_PROJECTION_NONE,
)

