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

"""Common adapter contract for harvest report messages.

All report adapters (SHACL, NTI, DCAT import, preprocessing, global errors,
etc.) must return this structure before persistence. The object carries the
normalized domain message together with persistence-side metadata required by
the report service.
"""

from dataclasses import dataclass
from typing import Optional

from ckanext.dge_harvest.services.report.harvest_report_message import (
    HarvestReportMessage,
)
from ckanext.dge_harvest.services.report.harvest_report_projection import (
    LEGACY_PROJECTION_NONE,
)


@dataclass(frozen=True)
class AdaptedHarvestReportMessage(object):
    """Common adapter output consumed by the report service.

    Attributes:
        message: Normalized domain message.
        raw_message: Optional original technical message.
        details_json: Optional structured context payload.
        more_info_url: Optional help or documentation URL.
        legacy_projection: Legacy projection target.
        legacy_stage: Legacy harvest stage.
    """

    message: HarvestReportMessage
    raw_message: Optional[str] = None
    details_json: object = None
    more_info_url: Optional[str] = None
    legacy_projection: str = LEGACY_PROJECTION_NONE
    legacy_stage: Optional[str] = None