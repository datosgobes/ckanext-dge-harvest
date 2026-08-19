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
"""Functional classifier for SHACL validation results.

Public contract:
    get_shacl_message_code(level, phase, reason=None)

Backward-compatible contract:
    get_shacl_validation_message_code(level, constraint_value)

The public resolvers never propagate classifier errors to callers. If the
resolution fails because of an invalid level, phase, reason, malformed internal
code, or unexpected bug, the error is logged and a safe fallback code is
returned.

Resolution priority:
    1. Specific code by reason.
    2. Default code for level + phase.
    3. Default code for level + fallback phase.
"""

import logging

from ckanext.dge_harvest.services.report import (
    harvest_report_catalog_messages as catalog_messages,
)
from ckanext.dge_harvest.services.report.harvest_report_catalog_entry import entry
from ckanext.dge_harvest.services.report.harvest_report_code import (
    build_message_code,
)
from ckanext.dge_harvest.services.report.harvest_report_code_constants import (
    ERROR_LEVEL_CODE,
    FALLBACK_PHASE_CODE,
    INFO_LEVEL_CODE,
    LEVEL_TO_CODE,
    PHASE_TO_CODE,
    SHACL_FAMILY_CODE,
    VALIDATION_PHASE_CODE,
    WARN_LEVEL_CODE,
)
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_PHASE_VALIDATION,
)



log = logging.getLogger(__name__)


SHACL_MIN_COUNT_CONSTRAINT = "http://www.w3.org/ns/shacl#MinCountConstraintComponent"
SHACL_MAX_COUNT_CONSTRAINT = "http://www.w3.org/ns/shacl#MaxCountConstraintComponent"
SHACL_DATATYPE_CONSTRAINT = "http://www.w3.org/ns/shacl#DatatypeConstraintComponent"
SHACL_CLASS_CONSTRAINT = "http://www.w3.org/ns/shacl#ClassConstraintComponent"
SHACL_NODE_KIND_CONSTRAINT = "http://www.w3.org/ns/shacl#NodeKindConstraintComponent"
SHACL_IN_CONSTRAINT = "http://www.w3.org/ns/shacl#InConstraintComponent"
SHACL_PATTERN_CONSTRAINT = "http://www.w3.org/ns/shacl#PatternConstraintComponent"
SHACL_MIN_LENGTH_CONSTRAINT = "http://www.w3.org/ns/shacl#MinLengthConstraintComponent"
SHACL_MIN_INCLUSIVE_CONSTRAINT = "http://www.w3.org/ns/shacl#MinInclusiveConstraintComponent"
SHACL_UNIQUE_LANG_CONSTRAINT = "http://www.w3.org/ns/shacl#UniqueLangConstraintComponent"
SHACL_HAS_VALUE_CONSTRAINT = "http://www.w3.org/ns/shacl#HasValueConstraintComponent"
SHACL_CLOSED_CONSTRAINT = "http://www.w3.org/ns/shacl#ClosedConstraintComponent"
SHACL_NODE_CONSTRAINT = "http://www.w3.org/ns/shacl#NodeConstraintComponent"
SHACL_PROPERTY_CONSTRAINT = "http://www.w3.org/ns/shacl#PropertyConstraintComponent"
SHACL_OR_CONSTRAINT = "http://www.w3.org/ns/shacl#OrConstraintComponent"
SHACL_NOT_CONSTRAINT = "http://www.w3.org/ns/shacl#NotConstraintComponent"
SHACL_XONE_CONSTRAINT = "http://www.w3.org/ns/shacl#XoneConstraintComponent"
SHACL_QUALIFIED_MIN_COUNT_CONSTRAINT = "http://www.w3.org/ns/shacl#QualifiedMinCountConstraintComponent"
SHACL_SPARQL_CONSTRAINT = "http://www.w3.org/ns/shacl#SPARQLConstraintComponent"


SHACL_CONSTRAINT_COMPONENT_TO_CASE_NUMBER = {
    SHACL_MIN_COUNT_CONSTRAINT: 2,
    SHACL_MAX_COUNT_CONSTRAINT: 3,
    SHACL_DATATYPE_CONSTRAINT: 4,
    SHACL_CLASS_CONSTRAINT: 5,
    SHACL_NODE_KIND_CONSTRAINT: 6,
    SHACL_IN_CONSTRAINT: 7,
    SHACL_PATTERN_CONSTRAINT: 8,
    SHACL_MIN_LENGTH_CONSTRAINT: 9,
    SHACL_MIN_INCLUSIVE_CONSTRAINT: 10,
    SHACL_UNIQUE_LANG_CONSTRAINT: 11,
    SHACL_HAS_VALUE_CONSTRAINT: 12,
    SHACL_CLOSED_CONSTRAINT: 13,
    SHACL_NODE_CONSTRAINT: 14,
    SHACL_PROPERTY_CONSTRAINT: 15,
    SHACL_OR_CONSTRAINT: 16,
    SHACL_NOT_CONSTRAINT: 17,
    SHACL_XONE_CONSTRAINT: 18,
    SHACL_QUALIFIED_MIN_COUNT_CONSTRAINT: 19,
    SHACL_SPARQL_CONSTRAINT: 20,
}


def _build_shacl_message_code(level_symbol, phase_symbol, case_number):
    """Build one SHACL-family code."""
    return build_message_code(level_symbol, phase_symbol, SHACL_FAMILY_CODE, case_number)


def _build_error_shacl_message_code(phase_code, case_number):
    return _build_shacl_message_code(ERROR_LEVEL_CODE, phase_code, case_number)


def _build_warn_shacl_message_code(phase_code, case_number):
    return _build_shacl_message_code(WARN_LEVEL_CODE, phase_code, case_number)


def _build_info_shacl_message_code(phase_code, case_number):
    return _build_shacl_message_code(INFO_LEVEL_CODE, phase_code, case_number)

'''
def get_shacl_error_message_code(phase, reason=None):
    """Return a safe SHACL error message code."""
    return get_shacl_message_code(level=MESSAGE_LEVEL_ERROR, phase=phase, reason=reason)


def get_shacl_warning_message_code(phase, reason=None):
    """Return a safe SHACL warning message code."""
    return get_shacl_message_code(level=MESSAGE_LEVEL_WARNING, phase=phase, reason=reason)


def get_shacl_info_message_code(phase, reason=None):
    """Return a safe SHACL info message code."""
    return get_shacl_message_code(level=MESSAGE_LEVEL_INFO, phase=phase, reason=reason)
'''

def get_shacl_message_code(level, phase, reason=None):
    """Return a safe SHACL message code for the requested context."""
    level_symbol = LEVEL_TO_CODE.get(level)

    try:
        if level_symbol is None:
            raise ValueError("Unsupported report level: {}".format(level))

        code = _get_shacl_message_code_by_reason(level_symbol=level_symbol, phase=phase, reason=reason)
        if code:
            return code

        return _build_default_shacl_message_code(level_symbol=level_symbol, phase=phase,)

    except Exception:
        log.exception(
            "Failed to resolve SHACL harvest report message code. "
            "level=%r phase=%r reason=%r",
            level, phase, reason)
        return _build_fallback_shacl_message_code(level_symbol=level_symbol or ERROR_LEVEL_CODE)


def _get_shacl_message_code_by_reason(level_symbol, phase, reason):
    """Resolve a SHACL code from a normalized reason when available."""
    if not reason:
        return None

    phase_reasons = SHACL_REASON_CASES.get((phase, level_symbol)) or {}
    case_number = phase_reasons.get(reason)

    if case_number is None:
        return None

    phase_code = PHASE_TO_CODE.get(phase, FALLBACK_PHASE_CODE)

    return _build_shacl_message_code(level_symbol, phase_code, case_number)


def _build_default_shacl_message_code(level_symbol, phase):
    """Return the default SHACL code for level + phase."""
    phase_code = PHASE_TO_CODE.get(phase, FALLBACK_PHASE_CODE)

    return _build_shacl_message_code(level_symbol, phase_code, 1)


def _build_fallback_shacl_message_code(level_symbol):
    """Return a guaranteed SHACL fallback code for one level symbol."""
    return _build_shacl_message_code(level_symbol, FALLBACK_PHASE_CODE, 1)


def _build_default_validation_shacl_message_code(level_symbol):
    """Return the default validation SHACL code for one level symbol."""
    return _build_shacl_message_code(level_symbol, VALIDATION_PHASE_CODE, 1)


####################################
####      VALIDATION PHASE      ####
####################################

# E42xx
VALIDATION_SHACL_ERROR_ENTRIES = (
    entry("E4201", catalog_messages.DEFAULT_SHACL_ERROR_MESSAGE, "Error general de SHACL durante la validación del RDF"),
    entry("E4202", catalog_messages.DEFAULT_SHACL_MIN_COUNT_MESSAGE, "Propiedad obligatoria ausente"),
    entry("E4203", catalog_messages.DEFAULT_SHACL_MAX_COUNT_MESSAGE, "Cardinalidad máxima incumplida"),
    entry("E4204", catalog_messages.DEFAULT_SHACL_DATATYPE_MESSAGE, "Tipo de dato inválido"),
    entry("E4205", catalog_messages.DEFAULT_SHACL_CLASS_MESSAGE, "Clase RDF inválida"),
    entry("E4206", catalog_messages.DEFAULT_SHACL_NODE_KIND_MESSAGE, "Tipo de nodo inválido"),
    entry("E4207", catalog_messages.DEFAULT_SHACL_ALLOWED_VALUES_MESSAGE, "Valor no permitido"),
    entry("E4208", catalog_messages.DEFAULT_SHACL_PATTERN_MESSAGE, "Patrón o formato inválido"),
    entry("E4209", catalog_messages.DEFAULT_SHACL_MIN_LENGTH_MESSAGE, "Longitud mínima incumplida"),
    entry("E4210", catalog_messages.DEFAULT_SHACL_MIN_INCLUSIVE_MESSAGE, "Valor inferior al mínimo permitido"),
    entry("E4211", catalog_messages.DEFAULT_SHACL_UNIQUE_LANG_MESSAGE, "Idioma duplicado en valores literales"),
    entry("E4212", catalog_messages.DEFAULT_SHACL_HAS_VALUE_MESSAGE, "Valor requerido ausente"),
    entry("E4213", catalog_messages.DEFAULT_SHACL_CLOSED_MESSAGE, "Propiedad no permitida"),
    entry("E4214", catalog_messages.DEFAULT_SHACL_NODE_MESSAGE, "Restricción de nodo incumplida"),
    entry("E4215", catalog_messages.DEFAULT_SHACL_PROPERTY_MESSAGE, "Restricción de propiedad incumplida"),
    entry("E4216", catalog_messages.DEFAULT_SHACL_OR_MESSAGE, "Ninguna de las alternativas permitidas se cumple"),
    entry("E4217", catalog_messages.DEFAULT_SHACL_NOT_MESSAGE, "Restricción negativa incumplida"),
    entry("E4218", catalog_messages.DEFAULT_SHACL_XONE_MESSAGE, "Debe cumplirse exactamente una alternativa"),
    entry("E4219", catalog_messages.DEFAULT_SHACL_QUALIFIED_MIN_COUNT_MESSAGE, "Cardinalidad mínima cualificada incumplida"),
    entry("E4220", catalog_messages.DEFAULT_SHACL_SPARQL_MESSAGE, "Restricción SPARQL incumplida"),
)

# W42xx
VALIDATION_SHACL_WARN_ENTRIES = (
    entry("W4201", catalog_messages.DEFAULT_SHACL_WARN_MESSAGE, "Warning general de SHACL durante la validación del RDF"),
    entry("W4202", catalog_messages.DEFAULT_SHACL_MIN_COUNT_MESSAGE, "Propiedad recomendada ausente"),
    entry("W4203", catalog_messages.DEFAULT_SHACL_MAX_COUNT_MESSAGE, "Cardinalidad máxima recomendada incumplida"),
    entry("W4204", catalog_messages.DEFAULT_SHACL_DATATYPE_MESSAGE, "Tipo de dato recomendado inválido"),
    entry("W4205", catalog_messages.DEFAULT_SHACL_CLASS_MESSAGE, "Clase RDF recomendada inválida"),
    entry("W4206", catalog_messages.DEFAULT_SHACL_NODE_KIND_MESSAGE, "Tipo de nodo recomendado inválido"),
    entry("W4207", catalog_messages.DEFAULT_SHACL_ALLOWED_VALUES_MESSAGE, "Valor no recomendado"),
    entry("W4208", catalog_messages.DEFAULT_SHACL_PATTERN_MESSAGE, "Patrón o formato recomendado inválido"),
    entry("W4209", catalog_messages.DEFAULT_SHACL_MIN_LENGTH_MESSAGE, "Longitud mínima recomendada incumplida"),
    entry("W4210", catalog_messages.DEFAULT_SHACL_MIN_INCLUSIVE_MESSAGE, "Valor inferior al mínimo recomendado"),
    entry("W4211", catalog_messages.DEFAULT_SHACL_UNIQUE_LANG_MESSAGE, "Idioma duplicado en valores literales"),
    entry("W4212", catalog_messages.DEFAULT_SHACL_HAS_VALUE_MESSAGE, "Valor recomendado ausente"),
    entry("W4213", catalog_messages.DEFAULT_SHACL_CLOSED_MESSAGE, "Propiedad no recomendada"),
    entry("W4214", catalog_messages.DEFAULT_SHACL_NODE_MESSAGE, "Restricción de nodo recomendada incumplida"),
    entry("W4215", catalog_messages.DEFAULT_SHACL_PROPERTY_MESSAGE, "Restricción de propiedad recomendada incumplida"),
    entry("W4216", catalog_messages.DEFAULT_SHACL_OR_MESSAGE, "Ninguna de las alternativas recomendadas se cumple"),
    entry("W4217", catalog_messages.DEFAULT_SHACL_NOT_MESSAGE, "Restricción negativa recomendada incumplida"),
    entry("W4218", catalog_messages.DEFAULT_SHACL_XONE_MESSAGE, "Debe cumplirse exactamente una alternativa recomendada"),
    entry("W4219", catalog_messages.DEFAULT_SHACL_QUALIFIED_MIN_COUNT_MESSAGE, "Cardinalidad mínima cualificada recomendada incumplida"),
    entry("W4220", catalog_messages.DEFAULT_SHACL_SPARQL_MESSAGE, "Restricción SPARQL recomendada incumplida"),
)

# I42xx
VALIDATION_SHACL_INFO_ENTRIES = (
    entry("I4201", catalog_messages.DEFAULT_SHACL_INFO_MESSAGE, "Información general de SHACL durante la validación del RDF"),
    entry("I4202", catalog_messages.DEFAULT_SHACL_MIN_COUNT_MESSAGE, "Información sobre propiedad ausente"),
    entry("I4203", catalog_messages.DEFAULT_SHACL_MAX_COUNT_MESSAGE, "Información sobre cardinalidad máxima"),
    entry("I4204", catalog_messages.DEFAULT_SHACL_DATATYPE_MESSAGE, "Información sobre tipo de dato"),
    entry("I4205", catalog_messages.DEFAULT_SHACL_CLASS_MESSAGE, "Información sobre clase RDF"),
    entry("I4206", catalog_messages.DEFAULT_SHACL_NODE_KIND_MESSAGE, "Información sobre tipo de nodo"),
    entry("I4207", catalog_messages.DEFAULT_SHACL_ALLOWED_VALUES_MESSAGE, "Información sobre valores permitidos"),
    entry("I4208", catalog_messages.DEFAULT_SHACL_PATTERN_MESSAGE, "Información sobre patrón o formato"),
    entry("I4209", catalog_messages.DEFAULT_SHACL_MIN_LENGTH_MESSAGE, "Información sobre longitud mínima"),
    entry("I4210", catalog_messages.DEFAULT_SHACL_MIN_INCLUSIVE_MESSAGE, "Información sobre valor mínimo permitido"),
    entry("I4211", catalog_messages.DEFAULT_SHACL_UNIQUE_LANG_MESSAGE, "Información sobre idiomas duplicados"),
    entry("I4212", catalog_messages.DEFAULT_SHACL_HAS_VALUE_MESSAGE, "Información sobre valor requerido"),
    entry("I4213", catalog_messages.DEFAULT_SHACL_CLOSED_MESSAGE, "Información sobre propiedades no permitidas"),
    entry("I4214", catalog_messages.DEFAULT_SHACL_NODE_MESSAGE, "Información sobre restricción de nodo"),
    entry("I4215", catalog_messages.DEFAULT_SHACL_PROPERTY_MESSAGE, "Información sobre restricción de propiedad"),
    entry("I4216", catalog_messages.DEFAULT_SHACL_OR_MESSAGE, "Información sobre alternativas permitidas"),
    entry("I4217", catalog_messages.DEFAULT_SHACL_NOT_MESSAGE, "Información sobre restricción negativa"),
    entry("I4218", catalog_messages.DEFAULT_SHACL_XONE_MESSAGE, "Información sobre alternativa exclusiva"),
    entry("I4219", catalog_messages.DEFAULT_SHACL_QUALIFIED_MIN_COUNT_MESSAGE, "Información sobre cardinalidad mínima cualificada"),
    entry("I4220", catalog_messages.DEFAULT_SHACL_SPARQL_MESSAGE, "Información sobre restricción SPARQL"),
)

VALIDATION_SHACL_CONSTRAINT_REASON_CASES = (
    SHACL_CONSTRAINT_COMPONENT_TO_CASE_NUMBER
)

VALIDATION_SHACL_ENTRIES = (
    VALIDATION_SHACL_ERROR_ENTRIES
    + VALIDATION_SHACL_WARN_ENTRIES
    + VALIDATION_SHACL_INFO_ENTRIES
)


SHACL_REASON_CASES = {
    (REPORT_PHASE_VALIDATION, ERROR_LEVEL_CODE): VALIDATION_SHACL_CONSTRAINT_REASON_CASES,
    (REPORT_PHASE_VALIDATION, WARN_LEVEL_CODE): VALIDATION_SHACL_CONSTRAINT_REASON_CASES,
    (REPORT_PHASE_VALIDATION, INFO_LEVEL_CODE): VALIDATION_SHACL_CONSTRAINT_REASON_CASES,
}


SHACL_ENTRIES = (
    VALIDATION_SHACL_ENTRIES
)
