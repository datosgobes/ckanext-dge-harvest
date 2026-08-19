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

"""Unit tests for SHACL-to-report message adaptation."""

from ckanext.dge_harvest.services.report.harvest_report_projection import (
    LEGACY_PROJECTION_GATHER,
    LEGACY_PROJECTION_NONE,
    LEGACY_STAGE_GATHER,
)
from ckanext.dge_harvest.services.report.harvest_report_shacl_adapter import (
    DEFAULT_SHACL_DISPLAY_MESSAGE,
    adapt_shacl_result_to_report_message,
    adapt_shacl_results_to_report_messages,
)
from ckanext.dge_harvest.services.report.harvest_report_shacl_classifier import (
    SHACL_MAX_COUNT_CONSTRAINT,
    SHACL_MIN_COUNT_CONSTRAINT,
    SHACL_PATTERN_CONSTRAINT,
    get_shacl_validation_message_code,
)


def test_adapt_shacl_result_builds_report_message_payload():
    adapted = adapt_shacl_result_to_report_message(
        {
            "severity": "Violation",
            "message": "  Falta \n título  ",
            "more_info_url": "https://example.test/guide",
            "constraint": SHACL_MIN_COUNT_CONSTRAINT,
        }
    )

    assert adapted.message.level == "error"
    assert adapted.message.phase == "validation"
    assert adapted.message.origin == "dcat_ap_es_harvester"
    assert adapted.message.category == "shacl"
    assert adapted.message.message_code == get_shacl_validation_message_code(
        "E",
        SHACL_MIN_COUNT_CONSTRAINT,
    )
    assert adapted.message.display_message == "Falta título"
    assert adapted.raw_message == "Falta título"
    assert adapted.details_json["level"] == "error"
    assert adapted.details_json["phase"] == "validation"
    assert adapted.details_json["origin"] == "dcat_ap_es_harvester"
    assert adapted.details_json["kind"] == "shacl_validation_result"
    assert adapted.details_json["reason"] == SHACL_MIN_COUNT_CONSTRAINT
    assert adapted.details_json["payload"]["shacl_result"]["constraint"] == (
        SHACL_MIN_COUNT_CONSTRAINT
    )
    assert adapted.more_info_url == "https://example.test/guide"
    assert adapted.legacy_projection == LEGACY_PROJECTION_GATHER
    assert adapted.legacy_stage == LEGACY_STAGE_GATHER


def test_adapt_shacl_result_uses_default_display_message_when_visible_text_missing():
    adapted = adapt_shacl_result_to_report_message(
        {
            "severity": "Warning",
            "constraint": SHACL_MAX_COUNT_CONSTRAINT,
            "more_info_url": " https://example.test/shape-help ",
        }
    )

    assert adapted.message.display_message == DEFAULT_SHACL_DISPLAY_MESSAGE
    assert adapted.legacy_projection == LEGACY_PROJECTION_NONE
    assert adapted.message.message_code == get_shacl_validation_message_code(
        "W",
        SHACL_MAX_COUNT_CONSTRAINT,
    )
    assert adapted.more_info_url == "https://example.test/shape-help"


def test_adapt_shacl_result_uses_constraint_name_fallback_for_display():
    adapted = adapt_shacl_result_to_report_message(
        {
            "severity": "Info",
            "constraint": SHACL_PATTERN_CONSTRAINT,
        }
    )

    assert adapted.message.display_message == DEFAULT_SHACL_DISPLAY_MESSAGE
    assert adapted.message.message_code == get_shacl_validation_message_code(
        "I",
        SHACL_PATTERN_CONSTRAINT,
    )


def test_adapt_shacl_result_uses_default_display_message_as_last_fallback():
    adapted = adapt_shacl_result_to_report_message({"severity": "Info"})

    assert adapted.message.display_message == DEFAULT_SHACL_DISPLAY_MESSAGE
    assert adapted.message.message_code == get_shacl_validation_message_code(
        "I",
        None,
    )


def test_adapt_shacl_results_to_report_messages_keeps_order():
    adapted = adapt_shacl_results_to_report_messages(
        [
            {"severity": "Warning", "message": "Uno"},
            {"severity": "Violation", "message": "Dos"},
        ]
    )

    assert [item.message.display_message for item in adapted] == ["Uno", "Dos"]


def test_adapted_message_as_service_kwargs_exposes_common_contract():
    adapted = adapt_shacl_result_to_report_message(
        {"severity": "Violation", "message": "Falta título"}
    )

    assert adapted.as_service_kwargs()["message"].as_dict() == {
        "level": "error",
        "phase": "validation",
        "origin": "dcat_ap_es_harvester",
        "category": "shacl",
        "message_code": get_shacl_validation_message_code("E", None),
        "display_message": "Falta título"
    }


def test_adapt_shacl_result_uses_first_more_info_url_when_primary_is_missing():
    adapted = adapt_shacl_result_to_report_message(
        {
            "severity": "Violation",
            "message": "Falta licencia",
            "more_info_url": " https://example.test/help/license ",
            "constraint": SHACL_MIN_COUNT_CONSTRAINT,
        }
    )

    assert adapted.more_info_url == "https://example.test/help/license"
