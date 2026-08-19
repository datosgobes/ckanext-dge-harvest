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

"""Unit tests for unified federation report query helpers."""

from ckanext.dge_harvest.services.report.harvest_report_query import (
    build_legacy_report_response,
    REPORT_MODE_LEGACY,
    REPORT_MODE_STRUCTURED,
    build_empty_report_response,
    build_structured_gather_report_response,
    normalize_report_query,
    read_legacy_report_data,
    resolve_report_guide_url,
    resolve_report_mode,
)


class _QueryStub(object):
    """Minimal query stub to drive mode detection tests."""

    def __init__(self, first_result=None, rows=None):
        self._first_result = first_result
        self._rows = list(rows or [])
        self._offset = 0
        self._limit = None

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._first_result

    def count(self):
        return len(self._rows)

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, value):
        self._offset = value
        return self

    def limit(self, value):
        self._limit = value
        return self

    def all(self):
        upper_bound = None
        if self._limit is not None:
            upper_bound = self._offset + self._limit
        return self._rows[self._offset:upper_bound]


class _SessionStub(object):
    """Minimal session stub with a preconfigured first-row result."""

    def __init__(self, first_result=None, rows=None):
        self._first_result = first_result
        self._rows = rows or []

    def query(self, *args, **kwargs):
        return _QueryStub(self._first_result, rows=self._rows)


class _StructuredRowStub(object):
    """Lightweight structured row stub for pagination tests."""

    def __init__(
        self,
        level,
        message,
        count,
        more_info_url=None,
        message_code=None,
        display_message_ui=None,
    ):
        self.level = level
        self.display_message = message
        self.display_message_ui = display_message_ui or message
        self.message_count = count
        self.more_info_url = more_info_url
        self.message_code = message_code


def test_normalize_report_query_uses_defaults():
    normalized = normalize_report_query({})

    assert normalized == {
        "page": 1,
        "limit": 20,
        "message_type": None,
        "sort_by": "count",
        "sort_dir": "desc",
    }


def test_normalize_report_query_validates_and_caps_limit():
    normalized = normalize_report_query(
        {
            "page": "2",
            "limit": "500",
            "message_type": "warning",
            "sort_by": "message",
            "sort_dir": "asc",
        }
    )

    assert normalized == {
        "page": 2,
        "limit": 100,
        "message_type": "warning",
        "sort_by": "message",
        "sort_dir": "asc",
    }


def test_resolve_report_mode_returns_structured_when_rows_exist():
    assert (
        resolve_report_mode("job-1", session=_SessionStub(("row-id",)))
        == REPORT_MODE_STRUCTURED
    )


def test_resolve_report_mode_returns_legacy_without_rows():
    assert (
        resolve_report_mode("job-1", session=_SessionStub(None))
        == REPORT_MODE_LEGACY
    )


def test_build_empty_report_response_returns_base_contract():
    response = build_empty_report_response(
        harvest_job_id="job-1",
        mode=REPORT_MODE_STRUCTURED,
        query={
            "page": 1,
            "limit": 20,
            "message_type": "error",
            "sort_by": "count",
            "sort_dir": "desc",
        },
    )

    assert response == {
        "job_id": "job-1",
        "mode": "structured",
        "rows": [],
        "summary": {
            "total": 0,
            "error": 0,
            "warning": 0,
            "info": 0,
        },
        "total": 0,
        "page": 1,
        "limit": 20,
        "message_type": "error",
        "sort_by": "count",
        "sort_dir": "desc",
        "guide_url": None,
        "csv_url": None,
    }


def test_build_structured_gather_report_response_returns_paginated_rows():
    rows = [
        _StructuredRowStub(
            "error",
            "Error 1",
            5,
            "https://example.test/1",
            message_code="E2501",
        ),
        _StructuredRowStub("warning", "Warning 1", 3, None),
        _StructuredRowStub("info", "Info 1", 1, "https://example.test/3"),
    ]

    response = build_structured_gather_report_response(
        harvest_job_id="job-1",
        query={
            "page": 2,
            "limit": 1,
            "message_type": None,
            "sort_by": "count",
            "sort_dir": "desc",
        },
        session=_SessionStub(rows=rows),
    )

    assert response == {
        "job_id": "job-1",
        "mode": "structured",
        "rows": [
            {
                "type": "warning",
                "message": "Warning 1",
                "message_ui": "Warning 1",
                "count": 3,
                "actions": {"more_info_url": None},
            }
        ],
        "summary": {
            "total": 9,
            "error": 5,
            "warning": 3,
            "info": 1,
        },
        "total": 3,
        "page": 2,
        "limit": 1,
        "message_type": None,
        "sort_by": "count",
        "sort_dir": "desc",
        "guide_url": None,
        "csv_url": None,
    }


def test_build_structured_gather_report_response_filters_by_message_type():
    rows = [
        _StructuredRowStub("error", "Error 1", 5),
        _StructuredRowStub("warning", "Warning 1", 3),
        _StructuredRowStub("warning", "Warning 2", 2),
    ]

    response = build_structured_gather_report_response(
        harvest_job_id="job-1",
        query={
            "page": 1,
            "limit": 20,
            "message_type": "warning",
            "sort_by": "count",
            "sort_dir": "desc",
        },
        session=_SessionStub(rows=rows),
    )

    assert response["total"] == 2
    assert response["summary"] == {
        "total": 10,
        "error": 5,
        "warning": 5,
        "info": 0,
    }
    assert response["rows"] == [
        {
            "type": "warning",
            "message": "Warning 1",
            "message_ui": "Warning 1",
            "count": 3,
            "actions": {"more_info_url": None},
        },
        {
            "type": "warning",
            "message": "Warning 2",
            "message_ui": "Warning 2",
            "count": 2,
            "actions": {"more_info_url": None},
        },
    ]


def test_build_structured_gather_report_response_appends_message_code_to_visible_message():
    rows = [
        _StructuredRowStub(
            "error",
            "Se ha producido un error técnico durante el preprocesado.",
            2,
            message_code="E2502",
        ),
    ]

    response = build_structured_gather_report_response(
        harvest_job_id="job-1",
        query={
            "page": 1,
            "limit": 20,
            "message_type": None,
            "sort_by": "count",
            "sort_dir": "desc",
        },
        session=_SessionStub(rows=rows),
    )

    assert response["rows"][0]["message"] == (
        "Se ha producido un error técnico durante el preprocesado.\n"
        "Vuelve a intentarlo más tarde. Si el problema persiste, contacta con el administrador.\n(Código: E2502)"
    )
    assert response["rows"][0]["message_ui"] == (
        "Se ha producido un error técnico durante el preprocesado.\n"
        "Vuelve a intentarlo más tarde. Si el problema persiste, contacta con el administrador.\n(Código: E2502)"
    )


def test_build_structured_gather_report_response_keeps_code_without_support_hint():
    rows = [
        _StructuredRowStub(
            "error",
            "Valor no permitido.",
            1,
            message_code="E4207",
        ),
    ]

    response = build_structured_gather_report_response(
        harvest_job_id="job-1",
        query={
            "page": 1,
            "limit": 20,
            "message_type": None,
            "sort_by": "count",
            "sort_dir": "desc",
        },
        session=_SessionStub(rows=rows),
    )

    assert response["rows"][0]["message"] == "Valor no permitido. (Código: E4207)"
    assert response["rows"][0]["message_ui"] == "Valor no permitido. (Código: E4207)"


def test_build_structured_gather_report_response_sorts_by_type_ascending():
    rows = [
        _StructuredRowStub("info", "Info 1", 1),
        _StructuredRowStub("warning", "Warning 1", 2),
        _StructuredRowStub("error", "Error 1", 3),
    ]

    response = build_structured_gather_report_response(
        harvest_job_id="job-1",
        query={
            "page": 1,
            "limit": 20,
            "message_type": None,
            "sort_by": "type",
            "sort_dir": "asc",
        },
        session=_SessionStub(rows=rows),
    )

    assert [row["type"] for row in response["rows"]] == [
        "error",
        "warning",
        "info",
    ]


def test_build_structured_gather_report_response_sorts_by_message_descending():
    rows = [
        _StructuredRowStub("error", "Alpha", 1),
        _StructuredRowStub("warning", "Zulu", 2),
        _StructuredRowStub("info", "Mike", 3),
    ]

    response = build_structured_gather_report_response(
        harvest_job_id="job-1",
        query={
            "page": 1,
            "limit": 20,
            "message_type": None,
            "sort_by": "message",
            "sort_dir": "desc",
        },
        session=_SessionStub(rows=rows),
    )

    assert [row["message"] for row in response["rows"]] == [
        "Zulu",
        "Mike",
        "Alpha",
    ]


def test_read_legacy_report_data_reuses_legacy_harvest_action():
    expected = {
        "gather_errors": [{"message": "Job error"}],
        "object_errors": {"obj-1": {"guid": "guid-1", "errors": []}},
    }

    def _action_getter(name):
        assert name == "harvest_job_report"

        def _action(context, data_dict):
            assert context == {"user": "tester"}
            assert data_dict == {"id": "job-1"}
            return expected

        return _action

    assert (
        read_legacy_report_data(
            harvest_job_id="job-1",
            context={"user": "tester"},
            get_action=_action_getter,
        )
        == expected
    )


def test_build_legacy_report_response_returns_transitional_payload():
    response = build_legacy_report_response(
        harvest_job_id="job-1",
        query={
            "page": 1,
            "limit": 20,
            "message_type": None,
            "sort_by": "count",
            "sort_dir": "desc",
        },
        legacy_report_data={
            "gather_errors": [{"message": "Job error"}],
            "object_errors": {
                "obj-1": {
                    "guid": "guid-1",
                    "errors": [{"message": "Object error", "type": "Gather"}],
                }
            },
        },
    )

    assert response == {
        "job_id": "job-1",
        "mode": "legacy",
        "rows": [
            {
                "type": "error",
                "message": "Job error",
                "message_ui": "Job error",
                "count": 1,
                "actions": {"more_info_url": None},
            },
            {
                "type": "error",
                "message": "Object error",
                "message_ui": "Object error",
                "count": 1,
                "actions": {"more_info_url": None},
            },
        ],
        "summary": {
            "total": 2,
            "error": 2,
            "warning": 0,
            "info": 0,
        },
        "total": 2,
        "page": 1,
        "limit": 20,
        "message_type": None,
        "sort_by": "count",
        "sort_dir": "desc",
        "guide_url": None,
        "csv_url": None,
        "legacy_report": {
            "gather_errors": [{"message": "Job error"}],
            "object_errors": {
                "obj-1": {
                    "guid": "guid-1",
                    "errors": [
                        {"message": "Object error", "type": "Gather"}
                    ],
                }
            },
        },
    }


def test_build_legacy_report_response_groups_and_parses_warning_rows():
    response = build_legacy_report_response(
        harvest_job_id="job-1",
        query={
            "page": 1,
            "limit": 20,
            "message_type": "warning",
            "sort_by": "message",
            "sort_dir": "asc",
        },
        legacy_report_data={
            "gather_errors": [
                {"message": "[Warning al tratar el catálogo] Idioma no soportado."},
                {"message": "[Warning al tratar el catálogo] Idioma no soportado."},
                {"message": "Error bloqueante"},
            ],
            "object_errors": {
                "obj-1": {
                    "guid": "guid-1",
                    "errors": [
                        {
                            "message": "[WARNING][Node x][Metadata y] Valor dudoso",
                            "line": 12,
                            "type": "Gather",
                        }
                    ],
                }
            },
        },
    )

    assert response["total"] == 2
    assert response["summary"] == {
        "total": 4,
        "error": 1,
        "warning": 3,
        "info": 0,
    }
    assert response["rows"] == [
        {
            "type": "warning",
            "message": "[WARNING][Node x][Metadata y] Valor dudoso (line 12)",
            "message_ui": "[WARNING][Node x][Metadata y] Valor dudoso (line 12)",
            "count": 1,
            "actions": {"more_info_url": None},
        },
        {
            "type": "warning",
            "message": "[Warning al tratar el catálogo] Idioma no soportado.",
            "message_ui": "[Warning al tratar el catálogo] Idioma no soportado.",
            "count": 2,
            "actions": {"more_info_url": None},
        },
    ]


def test_build_legacy_report_response_extracts_more_info_url_suffix():
    response = build_legacy_report_response(
        harvest_job_id="job-1",
        query={
            "page": 1,
            "limit": 20,
            "message_type": None,
            "sort_by": "count",
            "sort_dir": "desc",
        },
        legacy_report_data={
            "gather_errors": [
                {
                    "message": "El servicio no cumple la validación. Ver más información en: https://example.test/help"
                }
            ],
            "object_errors": {},
        },
    )

    assert response["rows"] == [
        {
            "type": "error",
            "message": "El servicio no cumple la validación",
            "message_ui": "El servicio no cumple la validación",
            "count": 1,
            "actions": {"more_info_url": "https://example.test/help"},
        }
    ]


def test_resolve_report_guide_url_uses_nti_source_type():
    extras = {
        "source_type_at_run": "dge_rdf",
        "source_config_at_run": '{"profile": "dge_nti_profile"}',
    }

    def _extra_getter(job_id, key, default=None):
        assert job_id == "job-1"
        return extras.get(key, default)

    def _config_getter(key, default=None):
        assert key == "ckanext.dge_harvest.dge_nti.url"
        return default

    assert (
        resolve_report_guide_url(
            harvest_job_id="job-1",
            extra_getter=_extra_getter,
            config_getter=_config_getter,
        )
        == "https://datosgobes.github.io/NTI-RISP/"
    )


def test_resolve_report_guide_url_uses_dcat_source_type_with_override():
    extras = {
        "source_type_at_run": "dge_dcat_ap_es_rdf",
        "source_config_at_run": "{}",
    }

    def _extra_getter(job_id, key, default=None):
        assert job_id == "job-1"
        return extras.get(key, default)

    def _config_getter(key, default=None):
        assert key == "ckanext.dge_harvest.dge_dcat_ap_es.url"
        return "https://example.test/dcat"

    assert (
        resolve_report_guide_url(
            harvest_job_id="job-1",
            extra_getter=_extra_getter,
            config_getter=_config_getter,
        )
        == "https://example.test/dcat"
    )


def test_resolve_report_guide_url_falls_back_to_source_config():
    extras = {
        "source_type_at_run": "custom",
        "source_config_at_run": '{"application_profile": "dge_nti_profile"}',
    }

    def _extra_getter(job_id, key, default=None):
        return extras.get(key, default)

    def _config_getter(key, default=None):
        assert key == "ckanext.dge_harvest.dge_nti.url"
        return default

    assert (
        resolve_report_guide_url(
            harvest_job_id="job-1",
            extra_getter=_extra_getter,
            config_getter=_config_getter,
        )
        == "https://datosgobes.github.io/NTI-RISP/"
    )


def test_resolve_report_guide_url_returns_none_when_profile_is_unknown():
    extras = {
        "source_type_at_run": "custom",
        "source_config_at_run": '{"foo": "bar"}',
    }

    def _extra_getter(job_id, key, default=None):
        return extras.get(key, default)

    assert (
        resolve_report_guide_url(
            harvest_job_id="job-1",
            extra_getter=_extra_getter,
            config_getter=lambda key, default=None: default,
        )
        is None
    )


def test_resolve_report_guide_url_uses_fallback_source_context():
    def _extra_getter(job_id, key, default=None):
        return default

    assert (
        resolve_report_guide_url(
            harvest_job_id="job-1",
            extra_getter=_extra_getter,
            config_getter=lambda key, default=None: default,
            fallback_source_type="dge_dcat_ap_es_rdf",
            fallback_source_config="{}",
        )
        == "https://datosgobes.github.io/DCAT-AP-ES"
    )
