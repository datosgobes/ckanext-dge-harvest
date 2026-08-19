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

"""Unit tests for SHACL functional classification."""

from ckanext.dge_harvest.services.report.harvest_report_shacl_classifier import (
    SHACL_MAX_COUNT_CONSTRAINT,
    SHACL_NODE_KIND_CONSTRAINT,
    SHACL_OR_CONSTRAINT,
    SHACL_UNIQUE_LANG_CONSTRAINT,
    build_shacl_message_code,
    get_shacl_validation_message_code,
)


def test_get_shacl_validation_message_code_uses_or_constraint_case():
    code = get_shacl_validation_message_code(
        level="E",
        constraint_value=SHACL_OR_CONSTRAINT,
    )

    assert code == build_shacl_message_code("E", "4", 16)


def test_get_shacl_validation_message_code_uses_node_kind_case():
    code = get_shacl_validation_message_code(
        level="E",
        constraint_value=SHACL_NODE_KIND_CONSTRAINT,
    )

    assert code == build_shacl_message_code("E", "4", 6)


def test_get_shacl_validation_message_code_uses_unique_lang_case():
    code = get_shacl_validation_message_code(
        level="E",
        constraint_value=SHACL_UNIQUE_LANG_CONSTRAINT,
    )

    assert code == build_shacl_message_code("E", "4", 11)


def test_get_shacl_validation_message_code_uses_max_count_warning_case():
    code = get_shacl_validation_message_code(
        level="W",
        constraint_value=SHACL_MAX_COUNT_CONSTRAINT,
    )

    assert code == build_shacl_message_code("W", "4", 3)
