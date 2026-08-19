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

"""Unit tests for vocabulary-to-report message adaptation."""

from ckanext.dge_harvest.services.report.harvest_report_projection import (
    LEGACY_PROJECTION_GATHER,
    LEGACY_STAGE_GATHER,
)
from ckanext.dge_harvest.services.report.harvest_report_vocabulary_adapter import (
    DEFAULT_VOCABULARY_DISPLAY_MESSAGE,
    REPORT_PHASE_VALIDATION,
    VOCABULARY_REASON_INVALID_VALUE,
    adapt_vocabulary_result_to_report_message,
    adapt_vocabulary_results_to_report_messages,
)
from ckanext.dge_harvest.services.report.harvest_report_vocabulary_classifier import (
    get_vocabulary_error_message_code,
)


def test_adapt_vocabulary_result_builds_report_payload():
    adapted = adapt_vocabulary_result_to_report_message(
        "  Valor fuera de vocabulario \n controlado  "
    )

    assert adapted.message.level == "error"
    assert adapted.message.phase == "validation"
    assert adapted.message.origin == "dcat_ap_es_harvester"
    assert adapted.message.category == "vocabulary"
    assert (
        adapted.message.message_code
        == get_vocabulary_error_message_code(
            phase=REPORT_PHASE_VALIDATION,
            reason=VOCABULARY_REASON_INVALID_VALUE,
        )
    )
    assert adapted.message.display_message == "Valor fuera de vocabulario controlado"
    assert adapted.raw_message == "Valor fuera de vocabulario controlado"
    assert adapted.details_json == {
        "level": "error",
        "phase": "validation",
        "origin": "dcat_ap_es_harvester",
        "kind": "vocabulary_validation_result",
        "reason": "invalid_vocabulary_value",
        "payload": {
            "vocabulary_result": "  Valor fuera de vocabulario \n controlado  ",
            "vocabulary_message": "Valor fuera de vocabulario controlado",
        },
    }
    assert adapted.more_info_url is None
    assert adapted.legacy_projection == LEGACY_PROJECTION_GATHER
    assert adapted.legacy_stage == LEGACY_STAGE_GATHER


def test_adapt_vocabulary_result_accepts_entity_context_and_extra_payload():
    adapted = adapt_vocabulary_result_to_report_message(
        result="Término obsoleto",
        entity_type="dataset",
        entity_uri="https://example.test/dataset/1",
        metadata_uri="https://example.test/field/title",
        extra_payload={"validator": "custom"},
    )

    assert adapted.message.level == "error"
    assert adapted.message.phase == "validation"
    assert adapted.message.origin == "dcat_ap_es_harvester"
    assert adapted.details_json == {
        "level": "error",
        "phase": "validation",
        "origin": "dcat_ap_es_harvester",
        "kind": "vocabulary_validation_result",
        "reason": "invalid_vocabulary_value",
        "metadata_uri": "https://example.test/field/title",
        "resource_uri": "https://example.test/dataset/1",
        "payload": {
            "vocabulary_result": "Término obsoleto",
            "vocabulary_message": "Término obsoleto",
            "entity_type": "dataset",
            "entity_uri": "https://example.test/dataset/1",
            "validator": "custom",
        },
    }
    assert adapted.message.display_message == (
        "En el conjunto de datos https://example.test/dataset/1 "
        "para el metadato https://example.test/field/title: Término obsoleto"
    )


def test_adapt_vocabulary_result_uses_default_visible_message():
    adapted = adapt_vocabulary_result_to_report_message(" \n ")

    assert adapted.message.display_message == DEFAULT_VOCABULARY_DISPLAY_MESSAGE
    assert adapted.raw_message == DEFAULT_VOCABULARY_DISPLAY_MESSAGE
    assert adapted.details_json == {
        "level": "error",
        "phase": "validation",
        "origin": "dcat_ap_es_harvester",
        "kind": "vocabulary_validation_result",
        "reason": "invalid_vocabulary_value",
        "payload": {
            "vocabulary_result": " \n ",
            "vocabulary_message": DEFAULT_VOCABULARY_DISPLAY_MESSAGE,
        },
    }


def test_adapt_vocabulary_results_to_report_messages_keeps_order():
    adapted = adapt_vocabulary_results_to_report_messages(
        ["Uno", "Dos"],
    )

    assert [item.message.display_message for item in adapted] == ["Uno", "Dos"]
    assert [item.message.level for item in adapted] == ["error", "error"]


def test_adapted_vocabulary_message_as_service_kwargs_exposes_common_contract():
    adapted = adapt_vocabulary_result_to_report_message("Término no permitido")

    assert adapted.message.as_dict() == {
        "level": "error",
        "phase": "validation",
        "origin": "dcat_ap_es_harvester",
        "category": "vocabulary",
        "message_code": get_vocabulary_error_message_code(
            phase=REPORT_PHASE_VALIDATION,
            reason=VOCABULARY_REASON_INVALID_VALUE,
        ),
        "display_message": "Término no permitido",
    }
