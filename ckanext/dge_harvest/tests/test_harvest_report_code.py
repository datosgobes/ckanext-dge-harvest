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

import pytest

from ckanext.dge_harvest.services.report.harvest_report_code import (
    build_message_code_reuse_key,
    build_message_code,
    get_message_code_family,
    normalize_message_code,
    parse_message_code,
    should_reuse_message_code,
)


def test_normalize_message_code_compacts_and_uppercases():
    assert normalize_message_code(" e 3 2 01 ") == "E3201"


def test_parse_message_code_returns_decoded_parts():
    parsed = parse_message_code("E3201")

    assert parsed == {
        "code": "E3201",
        "level_symbol": "E",
        "phase_symbol": "3",
        "family_symbol": "2",
        "case": "01",
        "level": "error",
        "phase": "validation",
        "category": "shacl",
    }


def test_parse_message_code_rejects_invalid_format():
    with pytest.raises(ValueError):
        parse_message_code("error-3201")

    with pytest.raises(ValueError):
        parse_message_code("E3501")


def test_build_message_code_creates_valid_lftnn_code():
    assert build_message_code("e", "3", "2", 1) == "E3201"


def test_get_message_code_family_resolves_by_symbol_and_category():
    family_by_symbol = get_message_code_family(symbol="2")
    family_by_category = get_message_code_family(category="technical")

    assert family_by_symbol.category == "shacl"
    assert family_by_symbol.label == "SHACL"
    assert family_by_category.symbol == "5"


def test_build_message_code_reuse_key_ignores_severity():
    assert build_message_code_reuse_key("E3201") == "3201"
    assert build_message_code_reuse_key("W3201") == "3201"


def test_should_reuse_message_code_when_functional_problem_is_the_same():
    assert should_reuse_message_code("E3201", "W3201") is True
    assert should_reuse_message_code("E3201", "I3201") is True
    assert should_reuse_message_code("E3201", "E3202") is False
    assert should_reuse_message_code("E3201", "E3301") is False
