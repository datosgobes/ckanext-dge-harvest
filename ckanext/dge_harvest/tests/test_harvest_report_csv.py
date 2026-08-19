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

"""Unit tests for federation report CSV helpers."""

from ckanext.dge_harvest.services.report.harvest_report_csv import (
    build_report_csv_filename,
    render_report_rows_csv,
)
from ckanext.dge_harvest.services.report.harvest_report_query import (
    build_report_csv_url,
)


def test_render_report_rows_csv_uses_visual_columns():
    csv_data = render_report_rows_csv([
        {
            "type": "warning",
            "message": "Message 1\nVuelve a intentarlo más tarde. (Código: W2502)",
            "count": 3,
            "actions": {"more_info_url": "https://example.test/help"},
        }
    ])

    assert "Type,Message,Count,More info URL" in csv_data
    assert (
        "warning,Message 1 Vuelve a intentarlo más tarde. (Código: W2502),3,"
        "https://example.test/help"
    ) in csv_data


def test_build_report_csv_filename_uses_job_id():
    assert build_report_csv_filename("job-1") == "harvest-job-report-job-1.csv"


def test_build_report_csv_url_preserves_filter_and_sort(monkeypatch):
    captured = {}

    def _fake_url_for(endpoint, **params):
        captured["endpoint"] = endpoint
        captured["params"] = params
        return "/harvest/source-1/job/job-1/report.csv"

    monkeypatch.setattr(
        "ckanext.dge_harvest.services.report.harvest_report_query.toolkit.url_for",
        _fake_url_for,
    )

    result = build_report_csv_url(
        source_name="source-1",
        harvest_job_id="job-1",
        query={
            "message_type": "warning",
            "sort_by": "message",
            "sort_dir": "asc",
        },
    )

    assert result == "/harvest/source-1/job/job-1/report.csv"
    assert captured == {
        "endpoint": "dgeHarvester.report_csv",
        "params": {
            "source": "source-1",
            "id": "job-1",
            "message_type": "warning",
            "sort_by": "message",
            "sort_dir": "asc",
        },
    }
