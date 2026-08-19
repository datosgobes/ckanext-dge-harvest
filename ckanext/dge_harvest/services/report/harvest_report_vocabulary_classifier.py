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
"""Functional classifier for vocabulary validation messages.

Public contract:
    get_vocabulary_error_message_code(phase, reason=None)
    get_vocabulary_warning_message_code(phase, reason=None)
    get_vocabulary_info_message_code(phase, reason=None)

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
    VALIDATION_PHASE_CODE,
    VOCABULARY_FAMILY_CODE,
    WARN_LEVEL_CODE,
)
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_PHASE_VALIDATION,
)
from ckanext.dge_harvest.services.report.harvest_report_severity import (
    MESSAGE_LEVEL_ERROR,
    MESSAGE_LEVEL_INFO,
    MESSAGE_LEVEL_WARNING,
)


log = logging.getLogger(__name__)


VOCABULARY_REASON_INVALID_VALUE = "invalid_vocabulary_value"


def _build_vocabulary_message_code(level_symbol, phase_symbol, case_number):
    """Build one vocabulary-family code."""
    return build_message_code(level_symbol, phase_symbol, VOCABULARY_FAMILY_CODE, case_number)


def _build_error_vocabulary_message_code(phase_code, case_number):
    return _build_vocabulary_message_code(ERROR_LEVEL_CODE, phase_code, case_number)


def _build_warn_vocabulary_message_code(phase_code, case_number):
    return _build_vocabulary_message_code(WARN_LEVEL_CODE, phase_code, case_number)


def _build_info_vocabulary_message_code(phase_code, case_number):
    return _build_vocabulary_message_code(INFO_LEVEL_CODE, phase_code, case_number)


def get_vocabulary_error_message_code(phase, reason=None):
    """Return a safe vocabulary error message code."""
    return _get_vocabulary_message_code(level=MESSAGE_LEVEL_ERROR, phase=phase, reason=reason)


def get_vocabulary_warning_message_code(phase, reason=None):
    """Return a safe vocabulary warning message code."""
    return _get_vocabulary_message_code(level=MESSAGE_LEVEL_WARNING, phase=phase, reason=reason)


def get_vocabulary_info_message_code(phase, reason=None):
    """Return a safe vocabulary info message code."""
    return _get_vocabulary_message_code(level=MESSAGE_LEVEL_INFO, phase=phase, reason=reason)


def _get_vocabulary_message_code(level, phase, reason=None):
    """Return a safe vocabulary message code for the requested context."""
    level_symbol = LEVEL_TO_CODE.get(level)

    try:
        if level_symbol is None:
            raise ValueError("Unsupported report level: {}".format(level))

        code = _get_vocabulary_message_code_by_reason(level_symbol=level_symbol, phase=phase, reason=reason)
        if code:
            return code

        return _build_default_vocabulary_message_code(level_symbol=level_symbol, phase=phase)

    except Exception:
        log.exception(
            "Failed to resolve vocabulary harvest report message code. "
            "level=%r phase=%r reason=%r",
            level, phase, reason)
        return _build_fallback_vocabulary_message_code(level_symbol=level_symbol or ERROR_LEVEL_CODE)


def _get_vocabulary_message_code_by_reason(level_symbol, phase, reason):
    """Resolve a vocabulary code from a normalized reason when available."""
    if not reason:
        return None

    phase_reasons = VOCABULARY_REASON_CASES.get((phase, level_symbol)) or {}
    case_number = phase_reasons.get(reason)

    if case_number is None:
        return None

    phase_code = PHASE_TO_CODE.get(phase, FALLBACK_PHASE_CODE)

    return _build_vocabulary_message_code(level_symbol, phase_code, case_number)


def _build_default_vocabulary_message_code(level_symbol, phase):
    """Return the default vocabulary code for level + phase."""
    phase_code = PHASE_TO_CODE.get(phase, FALLBACK_PHASE_CODE)

    return _build_vocabulary_message_code(level_symbol, phase_code, 1)


def _build_fallback_vocabulary_message_code(level_symbol):
    """Return a guaranteed vocabulary fallback code for one level symbol."""
    return _build_vocabulary_message_code(level_symbol, FALLBACK_PHASE_CODE, 1)



####################################
####      VALIDATION PHASE      ####
####################################

# E43xx
VALIDATION_VOCABULARY_ERROR_ENTRIES = (
    entry("E4301", catalog_messages.DEFAULT_VOCABULARY_ERROR_MESSAGE, "Error general de vocabularios durante la validación del RDF"),
    entry("E4302", catalog_messages.DEFAULT_VOCABULARY_INVALID_VALUE_ERROR_MESSAGE,"Valor fuera de vocabulario controlado"),
)

# W43xx
VALIDATION_VOCABULARY_WARN_ENTRIES = (
    entry("W4301", catalog_messages.DEFAULT_VOCABULARY_WARN_MESSAGE, "Warning general de vocabularios durante la validación del RDF"),
    entry("W4302", catalog_messages.DEFAULT_VOCABULARY_INVALID_VALUE_ERROR_MESSAGE,"Valor no recomendado en vocabulario controlado"),
)

# I43xx
VALIDATION_VOCABULARY_INFO_ENTRIES = (
    entry("I4301", catalog_messages.DEFAULT_VOCABULARY_INFO_MESSAGE,"Información general de vocabularios durante la validación del RDF"),
    entry("I4302", catalog_messages.DEFAULT_VOCABULARY_INVALID_VALUE_ERROR_MESSAGE, "Información sobre valor de vocabulario controlado",),
)


VALIDATION_VOCABULARY_ERROR_REASON_CASES = {
    VOCABULARY_REASON_INVALID_VALUE: 2,
}

VALIDATION_VOCABULARY_WARNING_REASON_CASES = {
    VOCABULARY_REASON_INVALID_VALUE: 2,
}

VALIDATION_VOCABULARY_INFO_REASON_CASES = {
    VOCABULARY_REASON_INVALID_VALUE: 2,
}


VALIDATION_VOCABULARY_ENTRIES = (
    VALIDATION_VOCABULARY_ERROR_ENTRIES
    + VALIDATION_VOCABULARY_WARN_ENTRIES
    + VALIDATION_VOCABULARY_INFO_ENTRIES
)


VOCABULARY_REASON_CASES = {
    (REPORT_PHASE_VALIDATION, ERROR_LEVEL_CODE): (
        VALIDATION_VOCABULARY_ERROR_REASON_CASES
    ),
    (REPORT_PHASE_VALIDATION, WARN_LEVEL_CODE): (
        VALIDATION_VOCABULARY_WARNING_REASON_CASES
    ),
    (REPORT_PHASE_VALIDATION, INFO_LEVEL_CODE): (
        VALIDATION_VOCABULARY_INFO_REASON_CASES
    ),
}


VOCABULARY_ENTRIES = (
    VALIDATION_VOCABULARY_ENTRIES
)
