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

"""Unit tests for gather context freezing in the base harvester."""

from ckanext.dge_harvest.constants.constants import HarvesterConstants
from ckanext.dge_harvest.harvesters.dge_harvester import DGERDFHarvester


class _DummySource(object):
    """Minimal source stub with only the fields used by the helper."""

    def __init__(self, url, source_type, source_config, owner_org):
        self.url = url
        self.type = source_type
        self.config = source_config
        self.owner_org = owner_org


class _DummyJob(object):
    """Minimal harvest job stub with id and source."""

    def __init__(self, job_id, url, source_type, source_config, owner_org):
        self.id = job_id
        self.source = _DummySource(url, source_type, source_config, owner_org)


def test_prepare_gather_context_persists_url_type_and_config(monkeypatch):
    calls = []

    class _SessionStub(object):
        def refresh(self, source):
            return source

        def commit(self):
            return None

        def rollback(self):
            return None

    monkeypatch.setattr(
        "ckanext.dge_harvest.harvesters.dge_harvester.model.Session",
        _SessionStub(),
    )

    def _fake_upsert(job_id, key, value):
        calls.append((job_id, key, value))

    monkeypatch.setattr(
        "ckanext.dge_harvest.harvesters.dge_harvester.upsert_job_extra",
        _fake_upsert,
    )

    harvester = DGERDFHarvester()
    job = _DummyJob(
        "job-1",
        "https://example.test/catalog.rdf",
        "dge_nti_rdf",
        "{\"rdf_format\": \"xml\"}",
        "org-1",
    )

    result = harvester._prepare_gather_context(job)

    assert result == "https://example.test/catalog.rdf"
    assert calls == [
        (
            "job-1",
            HarvesterConstants.SOURCE_URL_AT_RUN,
            "https://example.test/catalog.rdf",
        ),
        (
            "job-1",
            HarvesterConstants.SOURCE_TYPE_AT_RUN,
            "dge_nti_rdf",
        ),
        (
            "job-1",
            HarvesterConstants.SOURCE_CONFIG_AT_RUN,
            "{\"rdf_format\": \"xml\"}",
        ),
        (
            "job-1",
            HarvesterConstants.SOURCE_OWNER_ORG_AT_RUN,
            "org-1",
        ),
    ]


def test_get_local_content_and_type_uses_structured_gather_report(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "ckanext.dge_harvest.harvesters.dge_harvester.os.path.exists",
        lambda path: False,
    )

    def _fake_save(self, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        DGERDFHarvester,
        "_save_structured_global_report_error",
        _fake_save,
    )

    harvester = DGERDFHarvester()
    content, content_type = harvester._get_local_content_and_type(
        "/tmp/missing.rdf",
        object(),
    )

    assert content is None
    assert content_type is None
    assert captured["phase"] == "download"
    assert captured["kind"] == "catalog_access_error"
    assert captured["display_message"] == captured["raw_message"]
