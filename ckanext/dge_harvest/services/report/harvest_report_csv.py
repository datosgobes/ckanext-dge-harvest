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
"""CSV helpers for the unified federation report.

This module converts the visual row contract produced by the federation report
query service into a downloadable CSV payload. It keeps CSV formatting out of
actions, views and templates so the same columns can remain aligned with the
table shown in the job UI.
"""

import csv
from io import StringIO


def render_report_rows_csv(rows):
    """Render report rows to a UTF-8 CSV string.

    Args:
        rows (list[dict]): Visual report rows with ``type``, ``message``,
            ``count`` and ``actions.more_info_url``.

    Returns:
        str: CSV content ready to be returned as an attachment payload.
    """
    output = StringIO()
    writer = csv.writer(output)
    #writer.writerow(["Type", "Message", "Count", "More info URL"])
    writer.writerow(["Tipo", "Mensaje", "Cantidad", "Ver más"])
    for row in rows or []:
        actions = row.get("actions") or {}
        writer.writerow([
            row.get("type") or "",
            _normalize_csv_message(row.get("message")),
            row.get("count") or 0,
            actions.get("more_info_url") or "",
        ])
    return output.getvalue()


def _normalize_csv_message(message):
    """Remove line breaks from visible messages before CSV export."""
    if message is None:
        return ""
    return (
        str(message)
        .replace("\r\n", " ")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def build_report_csv_filename(harvest_job_id):
    """Build the download filename for one harvest job report.

    Args:
        harvest_job_id (str): Harvest job identifier.

    Returns:
        str: Attachment filename with ``.csv`` suffix.
    """
    return "harvest-job-report-{}.csv".format(harvest_job_id)
