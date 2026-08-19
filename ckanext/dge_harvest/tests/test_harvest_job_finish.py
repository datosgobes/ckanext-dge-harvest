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

"""Unit tests for the harvest job finish orchestration hook."""

from ckanext.dge_harvest.services import harvest_job_finish


def test_run_harvest_job_finished_hook_runs_consolidation_then_notification(
    monkeypatch,
):
    calls = []

    def _finalize(job_id, session=None):
        calls.append(("finalize", job_id, session))
        return {"job_id": job_id, "mode": "structured"}

    def _notify(context, source_id, job_id, action_getter=None):
        calls.append(("notify", context, source_id, job_id))
        return None

    monkeypatch.setattr(
        harvest_job_finish,
        "finalize_harvest_report_for_job",
        _finalize,
    )
    monkeypatch.setattr(
        harvest_job_finish,
        "notify_harvest_job_finished",
        _notify,
    )

    result = harvest_job_finish.run_harvest_job_finished_hook(
        context={"user": "site-user"},
        source_id="source-1",
        job_id="job-1",
        session="session-1",
    )

    assert result == {"job_id": "job-1", "mode": "structured"}
    assert calls == [
        ("finalize", "job-1", "session-1"),
        ("notify", {"user": "site-user"}, "source-1", "job-1"),
    ]
