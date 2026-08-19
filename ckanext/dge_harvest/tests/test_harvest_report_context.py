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

"""Unit tests for structured report context envelopes."""

from ckanext.dge_harvest.services.report.harvest_report_context import (
    build_report_context,
)


def test_build_report_context_keeps_required_and_optional_fields():
    context = build_report_context(
        level="error",
        phase="validation",
        origin="shacl",
        kind="shacl_validation_result",
        reason="MinCountConstraintComponent",
        field="dct:title",
        metadata_uri="http://purl.org/dc/terms/title",
        term_uri="http://example.test/term/1",
        node_id="node-1",
        resource_uri="http://example.test/dataset/1",
        payload={"raw": True},
    )

    assert context == {
        "level": "error",
        "phase": "validation",
        "origin": "shacl",
        "kind": "shacl_validation_result",
        "reason": "MinCountConstraintComponent",
        "field": "dct:title",
        "metadata_uri": "http://purl.org/dc/terms/title",
        "term_uri": "http://example.test/term/1",
        "node_id": "node-1",
        "resource_uri": "http://example.test/dataset/1",
        "payload": {"raw": True},
    }
