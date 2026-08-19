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

"""Public model exports for the DGE harvest extension.

The package re-exports the tables and helpers introduced by the harvest
report change so plugin bootstrap and Alembic can import them from one place.
"""

from ckanext.dge_harvest.model.dge_harvest_job_extra import (
    DgeHarvestJobExtra,
    dge_harvest_job_extra_table,
    upsert_job_extra,
    get_job_extra,
)
from ckanext.dge_harvest.model.dge_harvest_report import (
    DgeHarvestMessage,
    DgeHarvestReportRow,
    dge_harvest_message_table,
    dge_harvest_report_row_table,
)

__all__ = [
    "DgeHarvestJobExtra",
    "DgeHarvestMessage",
    "DgeHarvestReportRow",
    "dge_harvest_job_extra_table",
    "dge_harvest_message_table",
    "dge_harvest_report_row_table",
    "upsert_job_extra",
    "get_job_extra"
]
