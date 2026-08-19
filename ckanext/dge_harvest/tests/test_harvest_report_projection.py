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

"""Unit tests for structured-to-legacy harvest report projection rules."""

from contextlib import nullcontext

import pytest
from sqlalchemy.exc import IntegrityError

from ckanext.dge_harvest.model import DgeHarvestReportRow
from ckanext.dge_harvest.services.report.harvest_report_projection import (
    LEGACY_PROJECTION_GATHER,
    LEGACY_PROJECTION_NONE,
    LEGACY_PROJECTION_OBJECT,
    LEGACY_ALLOWED_STAGES,
    LEGACY_STAGE_GATHER,
    LEGACY_STAGE_FETCH,
    LEGACY_STAGE_IMPORT,
    build_legacy_object_stage,
    normalize_legacy_projection,
    normalize_legacy_stage,
    resolve_legacy_projection,
)
from ckanext.dge_harvest.services.report.harvest_report_service import (
    DgeHarvestReportService,
)


class DummySession(object):
    """Minimal session stub for service-level unit tests."""

    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    def query(self, _model):
        return DummyQuery()


class DummyQuery(object):
    """Query stub that forces the service down the row-creation path."""

    def filter_by(self, **_kwargs):
        return self

    def first(self):
        return None


class _DuplicateAwareQuery(object):
    """Query stub that surfaces a row after a simulated unique conflict."""

    def __init__(self, session):
        self.session = session
        self.filters = {}

    def filter_by(self, **kwargs):
        self.filters.update(kwargs)
        return self

    def first(self):
        row = self.session.visible_row
        if row is None:
            return None
        for key, value in self.filters.items():
            if getattr(row, key) != value:
                return None
        return row


class _DuplicateAwareSession(object):
    """Session stub that simulates a concurrent insert race."""

    def __init__(self):
        self.added = []
        self.visible_row = None
        self.row_conflict_raised = False

    def add(self, value):
        self.added.append(value)

    def flush(self):
        report_rows = [
            value for value in self.added if isinstance(value, DgeHarvestReportRow)
        ]
        if report_rows and not self.row_conflict_raised:
            self.row_conflict_raised = True
            row = report_rows[0]
            self.visible_row = DgeHarvestReportRow(
                id="row-1",
                harvest_job_id=row.harvest_job_id,
                fingerprint_full=row.fingerprint_full,
                fingerprint_semantic=row.fingerprint_semantic,
                level=row.level,
                phase=row.phase,
                origin=row.origin,
                category=row.category,
                message_code=row.message_code,
                display_message=row.display_message,
                display_message_ui=row.display_message_ui,
                more_info_url=row.more_info_url,
                message_count=1,
                first_message_id="existing-message",
                last_message_id="existing-message",
                first_seen=row.first_seen,
                last_seen=row.last_seen,
                created=row.created,
                modified=row.modified,
            )
            raise IntegrityError("insert", None, Exception("duplicate"))

    def begin_nested(self):
        return nullcontext()

    def query(self, _model):
        return _DuplicateAwareQuery(self)


def test_normalize_legacy_projection_accepts_known_values():
    assert normalize_legacy_projection(" Gather ") == LEGACY_PROJECTION_GATHER
    assert normalize_legacy_projection("object") == LEGACY_PROJECTION_OBJECT
    assert normalize_legacy_projection("none") == LEGACY_PROJECTION_NONE


def test_resolve_legacy_projection_defaults_to_none():
    assert resolve_legacy_projection(level="error") == LEGACY_PROJECTION_NONE


def test_resolve_legacy_projection_rejects_non_errors():
    with pytest.raises(ValueError):
        resolve_legacy_projection(
            level="warning",
            legacy_projection=LEGACY_PROJECTION_GATHER,
        )


def test_normalize_legacy_stage_accepts_known_values():
    assert normalize_legacy_stage("Gather") == LEGACY_STAGE_GATHER
    assert normalize_legacy_stage("Fetch") == LEGACY_STAGE_FETCH
    assert normalize_legacy_stage(" Import ") == LEGACY_STAGE_IMPORT


def test_normalize_legacy_stage_rejects_unknown_values():
    with pytest.raises(ValueError) as excinfo:
        normalize_legacy_stage("Archive")

    assert str(LEGACY_ALLOWED_STAGES) in str(excinfo.value)


def test_build_legacy_object_stage_maps_storage_to_import():
    assert build_legacy_object_stage("fetch") == LEGACY_STAGE_FETCH
    assert build_legacy_object_stage("storage") == LEGACY_STAGE_IMPORT
    assert build_legacy_object_stage("validation") == LEGACY_STAGE_GATHER


def test_create_message_projects_gather_error(monkeypatch):
    captured = []
    session = DummySession()
    service = DgeHarvestReportService(session=session)
    harvest_job = object()

    monkeypatch.setattr(
        "ckanext.dge_harvest.services.report.harvest_report_projection."
        "HarvestGatherError.create",
        lambda message, job: captured.append((message, job)),
    )

    message = service.create_message(
        harvest_job_id="job-1",
        harvest_job=harvest_job,
        level="error",
        phase="download",
        origin="harvester",
        category="technical",
        display_message_ui="Fallo global",
        legacy_projection="gather",
    )

    assert message.legacy_projection == LEGACY_PROJECTION_GATHER
    assert session.added
    assert captured == [("Fallo global", harvest_job)]


def test_create_message_projects_object_error_with_stage(monkeypatch):
    captured = []
    session = DummySession()
    service = DgeHarvestReportService(session=session)
    harvest_object = type(
        "HarvestObjectStub",
        (),
        {"id": "object-1", "harvest_job_id": "job-1"},
    )()

    monkeypatch.setattr(
        "ckanext.dge_harvest.services.report.harvest_report_projection."
        "HarvestObjectError.create",
        lambda message, obj, stage="Fetch", line=None: captured.append(
            (message, obj, stage, line)
        ),
    )

    message = service.create_message(
        harvest_object=harvest_object,
        level="error",
        phase="storage",
        origin="harvester",
        category="technical",
        display_message_ui="Fallo al importar",
        legacy_projection="object",
    )

    assert message.legacy_projection == LEGACY_PROJECTION_OBJECT
    assert session.added
    assert captured == [
        ("Fallo al importar", harvest_object, LEGACY_STAGE_IMPORT, None)
    ]


def test_create_message_projects_object_error_with_explicit_legacy_stage(
    monkeypatch,
):
    captured = []
    session = DummySession()
    service = DgeHarvestReportService(session=session)
    harvest_object = type(
        "HarvestObjectStub",
        (),
        {"id": "object-1", "harvest_job_id": "job-1"},
    )()

    monkeypatch.setattr(
        "ckanext.dge_harvest.services.report.harvest_report_projection."
        "HarvestObjectError.create",
        lambda message, obj, stage="Fetch", line=None: captured.append(
            (message, obj, stage, line)
        ),
    )

    service.create_message(
        harvest_object=harvest_object,
        level="error",
        phase="validation",
        origin="harvester",
        category="technical",
        display_message_ui="Fallo importado desde otra ruta",
        legacy_projection="object",
        legacy_stage="Import",
    )

    assert session.added
    assert captured == [
        (
            "Fallo importado desde otra ruta",
            harvest_object,
            LEGACY_STAGE_IMPORT,
            None,
        )
    ]


def test_create_message_does_not_project_warnings_or_info():
    session = DummySession()
    service = DgeHarvestReportService(session=session)

    message = service.create_message(
        harvest_job_id="job-1",
        level="warning",
        phase="download",
        origin="harvester",
        category="technical",
        display_message_ui="Solo tabla nueva",
    )

    assert message.legacy_projection is None
    assert session.added


def test_create_message_recovers_from_duplicate_report_row():
    session = _DuplicateAwareSession()
    service = DgeHarvestReportService(session=session)

    message = service.create_message(
        harvest_job_id="job-1",
        level="error",
        phase="download",
        origin="harvester",
        category="technical",
        display_message_ui="Fallo repetido",
    )

    assert message in session.added
    assert session.visible_row is not None
    assert session.visible_row.message_count == 2
    assert session.visible_row.last_message_id == message.id


def test_create_message_truncates_display_message_ui_to_1024():
    session = DummySession()
    service = DgeHarvestReportService(session=session)
    long_message = "x" * 1200

    service.create_message(
        harvest_job_id="job-1",
        level="error",
        phase="download",
        origin="harvester",
        category="technical",
        display_message_ui=long_message,
    )

    persisted_message = session.added[0]
    persisted_row = session.added[1]

    assert len(persisted_message.display_message_ui) == 1024
    assert len(persisted_row.display_message_ui) == 1024
    assert persisted_message.display_message == "x" * 1200


def test_create_message_requires_job_for_gather_projection():
    session = DummySession()
    service = DgeHarvestReportService(session=session)

    with pytest.raises(ValueError):
        service.create_message(
            harvest_job_id="job-1",
            level="error",
            phase="download",
            origin="harvester",
            category="technical",
            display_message_ui="Fallo global",
            legacy_projection="gather",
        )


def test_create_message_requires_object_for_object_projection():
    session = DummySession()
    service = DgeHarvestReportService(session=session)

    with pytest.raises(ValueError):
        service.create_message(
            harvest_job_id="job-1",
            level="error",
            phase="storage",
            origin="harvester",
            category="technical",
            display_message_ui="Fallo al importar",
            legacy_projection="object",
        )
