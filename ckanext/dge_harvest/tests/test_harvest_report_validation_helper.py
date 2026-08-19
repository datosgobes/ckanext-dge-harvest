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

"""Unit tests for gather-stage validation report helpers."""

from ckanext.dge_harvest.harvesters.utils.gather_stage_validation_report_helper import (
    GatherStageValidationMessageHelperMixin,
)


class _ValidationHelperStub(GatherStageValidationMessageHelperMixin):
    pass


def test_save_shacl_report_message_uses_display_message_ui(monkeypatch):
    captured = {}

    def _fake_save(self, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        _ValidationHelperStub,
        "_save_structured_global_report_error",
        _fake_save,
    )

    _ValidationHelperStub()._save_shacl_report_message(
        shacl_messages=["Linea 1\n\tLinea 2"],
        entity_type="dataset",
        entity_uri="https://example.test/dataset/1",
        harvest_job=object(),
        default_payload={},
    )

    assert captured["display_message_ui"] == (
        "Error de SHACL en conjunto de datos https://example.test/dataset/1. "
        "Linea 1\n\tLinea 2"
    )
