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

from ckanext.dge_harvest.services.report.harvest_report_fingerprint import (
    build_fingerprint_full,
    build_fingerprint_semantic,
)


def test_build_fingerprint_full_is_stable_for_same_visible_content():
    first = build_fingerprint_full(
        "error",
        "Mensaje visible",
        "https://example.test/guide",
    )
    second = build_fingerprint_full(
        "error",
        "Mensaje visible",
        "https://example.test/guide",
    )

    assert first == second
    assert first.startswith("full:")


def test_build_fingerprint_full_normalizes_whitespace():
    first = build_fingerprint_full("error", "Mensaje   visible", None)
    second = build_fingerprint_full("error", "Mensaje visible", "")

    assert first == second


def test_build_fingerprint_full_changes_when_visible_action_changes():
    first = build_fingerprint_full("error", "Mensaje visible", None)
    second = build_fingerprint_full("error", "Mensaje visible", "https://example.test")

    assert first != second


def test_build_fingerprint_full_changes_when_message_code_changes():
    first = build_fingerprint_full(
        "error",
        "Mensaje visible",
        None,
        message_code="E2501",
    )
    second = build_fingerprint_full(
        "error",
        "Mensaje visible",
        None,
        message_code="E2502",
    )

    assert first != second


def test_build_fingerprint_full_changes_when_support_hint_changes_visible_message():
    first = build_fingerprint_full(
        "error",
        "Mensaje visible",
        None,
        message_code="E2501",
    )
    second = build_fingerprint_full(
        "error",
        "Mensaje visible",
        None,
        message_code="E4201",
    )

    assert first != second


def test_build_fingerprint_semantic_uses_message_code_when_available():
    first = build_fingerprint_semantic(
        message_code="E3201",
        level="error",
        phase="validation",
        category="shacl",
        display_message="Mensaje visible",
    )
    second = build_fingerprint_semantic(
        message_code="E3201",
        level="warning",
        phase="storage",
        category="technical",
        display_message="Otro mensaje",
    )

    assert first == second
    assert first.startswith("semantic:")


def test_build_fingerprint_semantic_falls_back_to_functional_fields():
    first = build_fingerprint_semantic(
        level="error",
        phase="validation",
        category="shacl",
        display_message="Mensaje   visible",
    )
    second = build_fingerprint_semantic(
        level="error",
        phase="validation",
        category="shacl",
        display_message="Mensaje visible",
    )
    third = build_fingerprint_semantic(
        level="error",
        phase="storage",
        category="shacl",
        display_message="Mensaje visible",
    )

    assert first == second
    assert first != third
