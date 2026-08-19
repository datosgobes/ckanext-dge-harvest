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
"""Functional classifier for technical harvest report messages.

Public contract:
    _get_technical_message_code(level, phase, reason=None, exception=None)

The public resolver never propagates classifier errors to callers. If the
resolution fails because of an invalid level, phase, reason, malformed internal
code, or unexpected bug, it logs the exception and returns a safe technical
fallback code.

Resolution priority:
    1. Specific code by reason.
    2. Specific code by exception.
    3. Default code for level + phase.
    4. Default code for level + fallback phase.
"""

import logging

from ckanext.dge_harvest.harvesters.dge_harvester_exceptions import (
    GatherConnectionError,
    GatherHookError,
    PrepareGatherContextError,
)
from ckanext.dge_harvest.rdf_store.rdf_store_exceptions import (
    RDFStoreConnectionException,
    RDFStoreException,
    RDFStoreInternalException,
    RDFStoreQueryException,
)
from ckanext.dge_harvest.services.report import (
    harvest_report_catalog_messages as catalog_messages,
)
from ckanext.dge_harvest.services.report.harvest_report_catalog_entry import entry
from ckanext.dge_harvest.services.report.harvest_report_code import (
    build_message_code,
)
from ckanext.dge_harvest.services.report.harvest_report_code_constants import (
    DOWNLOAD_PHASE_CODE,
    ERROR_LEVEL_CODE,
    FALLBACK_PHASE_CODE,
    IMPORT_PHASE_CODE,
    INFO_LEVEL_CODE,
    PREPROCESSING_PHASE_CODE,
    SETUP_PHASE_CODE,
    STORAGE_PHASE_CODE,
    TECHNICAL_FAMILY_CODE,
    VALIDATION_PHASE_CODE,
    WARN_LEVEL_CODE,
    LEVEL_TO_CODE,
    PHASE_TO_CODE
)
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_PHASE_DOWNLOAD,
    REPORT_PHASE_FALLBACK,
    REPORT_PHASE_IMPORT,
    REPORT_PHASE_PREPROCESSING,
    REPORT_PHASE_SETUP,
    REPORT_PHASE_STORAGE,
    REPORT_PHASE_VALIDATION,
)
from ckanext.dge_harvest.services.report.harvest_report_severity import (
    MESSAGE_LEVEL_ERROR,
    MESSAGE_LEVEL_INFO,
    MESSAGE_LEVEL_WARNING,
)

log = logging.getLogger(__name__)
def _build_technical_message_code(level_symbol, phase_symbol, case_number):
    """Build one technical-family code."""
    return build_message_code(level_symbol, phase_symbol, TECHNICAL_FAMILY_CODE, case_number)


def _build_error_technical_message_code(phase_code, case_number):
    return _build_technical_message_code(ERROR_LEVEL_CODE, phase_code, case_number)


def _build_warn_technical_message_code(phase_code, case_number):
    return _build_technical_message_code(WARN_LEVEL_CODE, phase_code, case_number)


def _build_info_technical_message_code(phase_code, case_number):
    return _build_technical_message_code(INFO_LEVEL_CODE, phase_code, case_number)


def _get_technical_message_code(level, phase, reason=None, exception=None):
    """Return a safe technical message code for the requested context.

    This is the only function new callers should use.
    """
    level_symbol = LEVEL_TO_CODE.get(level)

    try:
        if level_symbol is None:
            raise ValueError("Unsupported report level: {}".format(level))

        code = _get_technical_message_code_by_reason(level_symbol=level_symbol, phase=phase, reason=reason)
        if code:
            return code

        code = _get_technical_message_code_by_exception(level_symbol=level_symbol, phase=phase, exception=exception)
        if code:
            return code

        return _build_default_technical_message_code(level_symbol=level_symbol, phase=phase)

    except Exception:
        log.exception(
            "Failed to resolve technical harvest report message code. "
            "level=%r phase=%r reason=%r exception=%r",
            level, phase, reason, exception.__class__.__name__ if exception else None,
        )
        return _build_fallback_technical_message_code(level_symbol=level_symbol or ERROR_LEVEL_CODE)


def get_technical_error_message_code(phase, reason=None, exception=None):
    """Convenience wrapper for technical error messages."""
    return _get_technical_message_code(level=MESSAGE_LEVEL_ERROR, phase=phase, reason=reason, exception=exception)


def get_technical_warning_message_code(phase, reason=None, exception=None):
    """Convenience wrapper for technical warning messages."""
    return _get_technical_message_code(level=MESSAGE_LEVEL_WARNING, phase=phase, reason=reason, exception=exception)


def get_technical_info_message_code(phase, reason=None, exception=None):
    """Convenience wrapper for technical info messages."""
    return _get_technical_message_code(level=MESSAGE_LEVEL_INFO, phase=phase, reason=reason, exception=exception,)


def _build_default_technical_message_code(level_symbol, phase):
    """Return default technical code for level + phase, falling back by phase."""
    phase_code = PHASE_TO_CODE.get(phase, FALLBACK_PHASE_CODE)
    return _build_technical_message_code(level_symbol, phase_code, 1)


def _build_fallback_technical_message_code(level_symbol):
    """Return guaranteed technical fallback code for one level symbol."""
    return _build_technical_message_code(level_symbol, FALLBACK_PHASE_CODE, 1)


def _get_technical_message_code_by_reason(level_symbol, phase, reason):
    """Resolve technical code from normalized reason when available."""
    if not reason:
        return None

    phase_reasons = TECHNICAL_REASON_CASES.get((phase, level_symbol)) or {}
    case_number = phase_reasons.get(reason)

    if case_number is None:
        return None

    phase_code = PHASE_TO_CODE.get(phase, FALLBACK_PHASE_CODE)
    return _build_technical_message_code(level_symbol, phase_code, case_number)


def _get_technical_message_code_by_exception(level_symbol, phase, exception):
    """Resolve technical code from exception when available.

    Exception-based classification currently produces error codes only.
    Warnings and info messages should normally be classified by reason.
    """
    if exception is None or level_symbol != ERROR_LEVEL_CODE:
        return None

    resolver = TECHNICAL_EXCEPTION_RESOLVERS.get(phase)
    if resolver is None:
        return None

    return resolver(exception)


def _get_technical_error_code_for_rdf_store_exception(exception, phase_code):
    """Resolve RDF store exception variants for a concrete phase code."""
    if isinstance(exception, RDFStoreConnectionException):
        return _build_error_technical_message_code(phase_code, 3)
    if isinstance(exception, RDFStoreQueryException):
        return _build_error_technical_message_code(phase_code, 4)
    if isinstance(exception, RDFStoreInternalException):
        return _build_error_technical_message_code(phase_code, 5)
    if isinstance(exception, RDFStoreException):
        return _build_error_technical_message_code(phase_code, 2)
    return None


def _get_common_technical_error_code_for_exception_by_phase(exception, phase_code):
    """Resolve technical infrastructure exceptions shared by phases."""
    code = _get_technical_error_code_for_rdf_store_exception(
        exception=exception,
        phase_code=phase_code,
    )
    if code:
        return code

    if isinstance(exception, GatherConnectionError):
        return _build_error_technical_message_code(phase_code, 6)
    if isinstance(exception, GatherHookError):
        return _build_error_technical_message_code(phase_code, 7)

    return None


# ---------------------------------------------------------------------------
# Setup phase
# ---------------------------------------------------------------------------

SETUP_TECHNICAL_ERROR_ENTRIES = (
    entry("E0501", catalog_messages.DEFAULT_TECHNICAL_ERROR_MESSAGE, "Configuración: error técnico general", requires_support_hint=True),
    entry("E0502", catalog_messages.DEFAULT_RDFSTORE_ERROR_MESSAGE, "Configuración: error RDFStore", requires_support_hint=True),
    entry("E0503", catalog_messages.DEFAULT_RDFSTORE_CONNECTION_ERROR_MESSAGE, "Configuración: conexión RDFStore", requires_support_hint=True),
    entry("E0504", catalog_messages.DEFAULT_RDFSTORE_QUERY_ERROR_MESSAGE, "Configuración: consulta RDFStore", requires_support_hint=True),
    entry("E0505", catalog_messages.DEFAULT_RDFSTORE_INTERNAL_ERROR_MESSAGE, "Configuración: error interno RDFStore", requires_support_hint=True),
    entry("E0506", catalog_messages.DEFAULT_TECHNICAL_SETUP_ERROR_MESSAGE, "Configuración: preparación de contexto", requires_support_hint=True),
    entry("E0507", catalog_messages.DEFAULT_TECHNICAL_SETUP_ERROR_MESSAGE, "Configuración: formato RDF no configurado", requires_support_hint=True),
    entry("E0508", catalog_messages.DEFAULT_TECHNICAL_ERROR_MESSAGE, "Configuración: error técnico al obtener el contexto", requires_support_hint=True),
)

SETUP_TECHNICAL_WARN_ENTRIES = (
    entry("W0501", catalog_messages.DEFAULT_TECHNICAL_WARN_MESSAGE, "Warning general técnico durante la fase inicial de configuración"),
)

SETUP_TECHNICAL_INFO_ENTRIES = (
    entry("I0501", catalog_messages.DEFAULT_TECHNICAL_INFO_MESSAGE, "Información general técnica durante la fase inicial de configuración"),
)

SETUP_TECHNICAL_ENTRIES = (
    SETUP_TECHNICAL_ERROR_ENTRIES
    + SETUP_TECHNICAL_WARN_ENTRIES
    + SETUP_TECHNICAL_INFO_ENTRIES
)


def _get_setup_technical_error_code_by_exception(exception):
    code = _get_common_technical_error_code_for_exception_by_phase(
        exception=exception,
        phase_code=SETUP_PHASE_CODE,
    )
    if code:
        return code

    if isinstance(exception, PrepareGatherContextError):
        return _build_error_technical_message_code(SETUP_PHASE_CODE, 8)

    return None


# ---------------------------------------------------------------------------
# Download phase
# ---------------------------------------------------------------------------

DOWNLOAD_TECHNICAL_ERROR_ENTRIES = (
    entry("E1501", catalog_messages.DEFAULT_TECHNICAL_ERROR_MESSAGE, "Descarga: error técnico general", requires_support_hint=True),
    entry("E1502", catalog_messages.DEFAULT_RDFSTORE_ERROR_MESSAGE, "Descarga: error RDFStore", requires_support_hint=True),
    entry("E1503", catalog_messages.DEFAULT_RDFSTORE_CONNECTION_ERROR_MESSAGE, "Descarga: conexión RDFStore", requires_support_hint=True),
    entry("E1504", catalog_messages.DEFAULT_RDFSTORE_QUERY_ERROR_MESSAGE, "Descarga: consulta RDFStore", requires_support_hint=True),
    entry("E1505", catalog_messages.DEFAULT_RDFSTORE_INTERNAL_ERROR_MESSAGE, "Descarga: error interno RDFStore", requires_support_hint=True),
    entry("E1506", catalog_messages.DEFAULT_TECHNICAL_CONNECTION_ERROR_MESSAGE, "Descarga: error de conexión", requires_support_hint=True),
    entry("E1507", catalog_messages.DEFAULT_TECHNICAL_HOOK_ERROR_MESSAGE, "Descarga: error de hook", requires_support_hint=True),
)

DOWNLOAD_TECHNICAL_WARN_ENTRIES = (
    entry("W1501", catalog_messages.DEFAULT_TECHNICAL_WARN_MESSAGE, "Warning general técnico durante la descarga del RDF"),
)

DOWNLOAD_TECHNICAL_INFO_ENTRIES = (
    entry("I1501", catalog_messages.DEFAULT_TECHNICAL_INFO_MESSAGE, "Información general técnica durante la descarga del RDF"),
)

DOWNLOAD_TECHNICAL_ENTRIES = (
    DOWNLOAD_TECHNICAL_ERROR_ENTRIES
    + DOWNLOAD_TECHNICAL_WARN_ENTRIES
    + DOWNLOAD_TECHNICAL_INFO_ENTRIES
)


def _get_download_technical_error_code_by_exception(exception):
    return _get_common_technical_error_code_for_exception_by_phase(
        exception=exception,
        phase_code=DOWNLOAD_PHASE_CODE,
    )


# ---------------------------------------------------------------------------
# Storage phase
# ---------------------------------------------------------------------------

STORAGE_TECHNICAL_ERROR_ENTRIES = (
    entry("E2501", catalog_messages.DEFAULT_TECHNICAL_STORAGE_ERROR_MESSAGE, "Almacenamiento: error técnico general", requires_support_hint=True),
    entry("E2502", catalog_messages.DEFAULT_RDFSTORE_ERROR_MESSAGE, "Almacenamiento: error RDFStore", requires_support_hint=True),
    entry("E2503", catalog_messages.DEFAULT_RDFSTORE_CONNECTION_ERROR_MESSAGE, "Almacenamiento: conexión RDFStore", requires_support_hint=True),
    entry("E2504", catalog_messages.DEFAULT_RDFSTORE_QUERY_ERROR_MESSAGE, "Almacenamiento: consulta RDFStore", requires_support_hint=True),
    entry("E2505", catalog_messages.DEFAULT_RDFSTORE_INTERNAL_ERROR_MESSAGE, "Almacenamiento: error interno RDFStore", requires_support_hint=True),
    entry("E2506", catalog_messages.DEFAULT_TECHNICAL_CONNECTION_ERROR_MESSAGE, "Almacenamiento: error de conexión", requires_support_hint=True),
    entry("E2507", catalog_messages.DEFAULT_TECHNICAL_HOOK_ERROR_MESSAGE, "Almacenamiento: error de hook", requires_support_hint=True),
)

STORAGE_TECHNICAL_WARN_ENTRIES = (
    entry("W2501", catalog_messages.DEFAULT_TECHNICAL_WARN_MESSAGE, "Warning general técnico durante el almacenamiento del RDF"),
)

STORAGE_TECHNICAL_INFO_ENTRIES = (
    entry("I2501", catalog_messages.DEFAULT_TECHNICAL_INFO_MESSAGE, "Información general técnica durante el almacenamiento del RDF"),
)

STORAGE_TECHNICAL_ENTRIES = (
    STORAGE_TECHNICAL_ERROR_ENTRIES
    + STORAGE_TECHNICAL_WARN_ENTRIES
    + STORAGE_TECHNICAL_INFO_ENTRIES
)


def _get_storage_technical_error_code_by_exception(exception):
    return _get_common_technical_error_code_for_exception_by_phase(
        exception=exception,
        phase_code=STORAGE_PHASE_CODE,
    )


# ---------------------------------------------------------------------------
# Preprocessing phase
# ---------------------------------------------------------------------------

PREPROCESSING_TECHNICAL_ERROR_ENTRIES = (
    entry("E3501", catalog_messages.DEFAULT_TECHNICAL_PREPROCESSING_ERROR_MESSAGE, "Preprocesado: error técnico general", requires_support_hint=True),
    entry("E3502", catalog_messages.DEFAULT_RDFSTORE_ERROR_MESSAGE, "Preprocesado: error RDFStore", requires_support_hint=True),
    entry("E3503", catalog_messages.DEFAULT_RDFSTORE_CONNECTION_ERROR_MESSAGE, "Preprocesado: conexión RDFStore", requires_support_hint=True),
    entry("E3504", catalog_messages.DEFAULT_RDFSTORE_QUERY_ERROR_MESSAGE, "Preprocesado: consulta RDFStore", requires_support_hint=True),
    entry("E3505", catalog_messages.DEFAULT_RDFSTORE_INTERNAL_ERROR_MESSAGE, "Preprocesado: error interno RDFStore", requires_support_hint=True),
    entry("E3506", catalog_messages.DEFAULT_TECHNICAL_CONNECTION_ERROR_MESSAGE, "Preprocesado: error de conexión", requires_support_hint=True),
    entry("E3507", catalog_messages.DEFAULT_TECHNICAL_HOOK_ERROR_MESSAGE, "Preprocesado: error de hook", requires_support_hint=True),
)

PREPROCESSING_TECHNICAL_WARN_ENTRIES = (
    entry("W3501", catalog_messages.DEFAULT_TECHNICAL_WARN_MESSAGE, "Warning general técnico durante el preprocesamiento del RDF"),
)

PREPROCESSING_TECHNICAL_INFO_ENTRIES = (
    entry("I3501", catalog_messages.DEFAULT_TECHNICAL_INFO_MESSAGE, "Información general técnica durante el preprocesamiento del RDF"),
)

PREPROCESSING_TECHNICAL_ENTRIES = (
    PREPROCESSING_TECHNICAL_ERROR_ENTRIES
    + PREPROCESSING_TECHNICAL_WARN_ENTRIES
    + PREPROCESSING_TECHNICAL_INFO_ENTRIES
)


def _get_preprocessing_technical_error_code_by_exception(exception):
    return _get_common_technical_error_code_for_exception_by_phase(
        exception=exception,
        phase_code=PREPROCESSING_PHASE_CODE,
    )


# ---------------------------------------------------------------------------
# Validation phase
# ---------------------------------------------------------------------------

VALIDATION_TECHNICAL_ERROR_ENTRIES = (
    entry("E4501", catalog_messages.DEFAULT_TECHNICAL_VALIDATION_ERROR_MESSAGE, "Validación: error técnico general", requires_support_hint=True),
    entry("E4502", catalog_messages.DEFAULT_RDFSTORE_ERROR_MESSAGE, "Validación: error RDFStore", requires_support_hint=True),
    entry("E4503", catalog_messages.DEFAULT_RDFSTORE_CONNECTION_ERROR_MESSAGE, "Validación: conexión RDFStore", requires_support_hint=True),
    entry("E4504", catalog_messages.DEFAULT_RDFSTORE_QUERY_ERROR_MESSAGE, "Validación: consulta RDFStore", requires_support_hint=True),
    entry("E4505", catalog_messages.DEFAULT_RDFSTORE_INTERNAL_ERROR_MESSAGE, "Validación: error interno RDFStore", requires_support_hint=True),
    entry("E4506", catalog_messages.DEFAULT_TECHNICAL_CONNECTION_ERROR_MESSAGE, "Validación: error de conexión", requires_support_hint=True),
    entry("E4507", catalog_messages.DEFAULT_TECHNICAL_HOOK_ERROR_MESSAGE, "Validación: error de hook", requires_support_hint=True),
)

VALIDATION_TECHNICAL_WARN_ENTRIES = (
    entry("W4501", catalog_messages.DEFAULT_TECHNICAL_WARN_MESSAGE, "Warning general técnico durante la validación del RDF"),
)

VALIDATION_TECHNICAL_INFO_ENTRIES = (
    entry("I4501", catalog_messages.DEFAULT_TECHNICAL_INFO_MESSAGE, "Información general técnica durante la validación del RDF"),
)

VALIDATION_TECHNICAL_ENTRIES = (
    VALIDATION_TECHNICAL_ERROR_ENTRIES
    + VALIDATION_TECHNICAL_WARN_ENTRIES
    + VALIDATION_TECHNICAL_INFO_ENTRIES
)


def _get_validation_technical_error_code_by_exception(exception):
    return _get_common_technical_error_code_for_exception_by_phase(
        exception=exception,
        phase_code=VALIDATION_PHASE_CODE,
    )


# ---------------------------------------------------------------------------
# Import phase
# ---------------------------------------------------------------------------

IMPORT_TECHNICAL_ERROR_ENTRIES = (
    entry("E5501", catalog_messages.DEFAULT_TECHNICAL_IMPORT_ERROR_MESSAGE, "Importación: error técnico general", requires_support_hint=True),
    entry("E5502", catalog_messages.DEFAULT_RDFSTORE_ERROR_MESSAGE, "Importación: error RDFStore", requires_support_hint=True),
    entry("E5503", catalog_messages.DEFAULT_RDFSTORE_CONNECTION_ERROR_MESSAGE, "Importación: conexión RDFStore", requires_support_hint=True),
    entry("E5504", catalog_messages.DEFAULT_RDFSTORE_QUERY_ERROR_MESSAGE, "Importación: consulta RDFStore", requires_support_hint=True),
    entry("E5505", catalog_messages.DEFAULT_RDFSTORE_INTERNAL_ERROR_MESSAGE, "Importación: error interno RDFStore", requires_support_hint=True),
    entry("E5506", catalog_messages.DEFAULT_TECHNICAL_CONNECTION_ERROR_MESSAGE, "Importación: error de conexión", requires_support_hint=True),
    entry("E5507", catalog_messages.DEFAULT_TECHNICAL_HOOK_ERROR_MESSAGE, "Importación: error de hook", requires_support_hint=True),
    entry("E5511", catalog_messages.DEFAULT_REASON_EMPTY_OBJECT_CONTENT_MESSAGE, "Contenido vacío del objeto al importar"),
    entry("E5512", catalog_messages.DEFAULT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT_MESSAGE, "Errores al parsear el contenido del objeto a importar"),
    entry("E5513", catalog_messages.DEFAULT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_THAT_SERVES_DATASET_MESSAGE, "Dataservices relacionados con el dataset no encontrados"),
    entry("E5514", catalog_messages.DEFAULT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_ACCESSED_BY_DISTRIBUTION_MESSAGE, "Dataservices relacionados con la distribución no encontrados"),
    entry("E5515", catalog_messages.DEFAULT_REASON_DELETED_DATASET_MESSAGE, "Borrado dataset no válido"),
    entry("E5516", catalog_messages.DEFAULT_REASON_DELETED_DATASERVICE_MESSAGE, "Borrado dataservice no válido"),
)

IMPORT_TECHNICAL_WARN_ENTRIES = (
    entry("W5501", catalog_messages.DEFAULT_TECHNICAL_WARN_MESSAGE, "Warning general técnico durante la importación"),
    entry("W5511", catalog_messages.DEFAULT_REASON_EMPTY_OBJECT_CONTENT_MESSAGE, "Contenido vacío del objeto al importar"),
    entry("W5512", catalog_messages.DEFAULT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT_MESSAGE, "Errores al parsear el contenido del objeto a importar"),
    entry("W5513", catalog_messages.DEFAULT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_THAT_SERVES_DATASET_MESSAGE, "Dataservices relacionados con el dataset no encontrados"),
    entry("W5514", catalog_messages.DEFAULT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_ACCESSED_BY_DISTRIBUTION_MESSAGE, "Dataservices relacionados con la distribución no encontrados"),
    entry("W5515", catalog_messages.DEFAULT_REASON_DELETED_DATASET_MESSAGE, "Borrado dataset no válido"),
    entry("W5516", catalog_messages.DEFAULT_REASON_DELETED_DATASERVICE_MESSAGE, "Borrado dataservice no válido"),
)

IMPORT_TECHNICAL_INFO_ENTRIES = (
    entry("I5501", catalog_messages.DEFAULT_TECHNICAL_INFO_MESSAGE, "Información general técnica durante la importación"),
    entry("I5511", catalog_messages.DEFAULT_REASON_EMPTY_OBJECT_CONTENT_MESSAGE, "Contenido vacío del objeto al importar"),
    entry("I5512", catalog_messages.DEFAULT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT_MESSAGE, "Errores al parsear el contenido del objeto a importar"),
    entry("I5513", catalog_messages.DEFAULT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_THAT_SERVES_DATASET_MESSAGE, "Dataservices relacionados con el dataset no encontrados"),
    entry("I5514", catalog_messages.DEFAULT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_ACCESSED_BY_DISTRIBUTION_MESSAGE, "Dataservices relacionados con la distribución no encontrados"),
    entry("I5515", catalog_messages.DEFAULT_REASON_DELETED_DATASET_MESSAGE, "Borrado dataset no válido"),
    entry("I5516", catalog_messages.DEFAULT_REASON_DELETED_DATASERVICE_MESSAGE, "Borrado dataservice no válido"),
)

IMPORT_TECHNICAL_ENTRIES = (
    IMPORT_TECHNICAL_ERROR_ENTRIES
    + IMPORT_TECHNICAL_WARN_ENTRIES
    + IMPORT_TECHNICAL_INFO_ENTRIES
)


IMPORT_REASON_EMPTY_OBJECT_CONTENT = "empty_object_content"
IMPORT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT = "value_error_json_load"
IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_THAT_SERVES_DATASET = "not_found_allowed_dataservice_that_serves_dataset"
IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_ACCESSED_BY_DISTRIBUTION = "not_found_allowed_dataservice_accessed_by_distribution"
IMPORT_REASON_DELETED_DATASET = "deleted_dataset"
IMPORT_REASON_DELETED_DATASERVICE = "deleted_dataservice"

IMPORT_TECHNICAL_ERROR_REASON_CASES={
        IMPORT_REASON_EMPTY_OBJECT_CONTENT: 11,
        IMPORT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT: 12,
        IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_THAT_SERVES_DATASET: 13,
        IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_ACCESSED_BY_DISTRIBUTION: 14,
        IMPORT_REASON_DELETED_DATASET: 15,
        IMPORT_REASON_DELETED_DATASERVICE: 16,
    }
IMPORT_TECHNICAL_WARN_REASON_CASES = {
        IMPORT_REASON_EMPTY_OBJECT_CONTENT: 11,
        IMPORT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT: 12,
        IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_THAT_SERVES_DATASET: 13,
        IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_ACCESSED_BY_DISTRIBUTION: 14,
        IMPORT_REASON_DELETED_DATASET: 15,
        IMPORT_REASON_DELETED_DATASERVICE: 16,
    }

IMPORT_TECHNICAL_INFO_REASON_CASES = {
        IMPORT_REASON_EMPTY_OBJECT_CONTENT: 11,
        IMPORT_REASON_WRONG_PARSE_LOAD_OBJECT_CONTENT: 12,
        IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_THAT_SERVES_DATASET: 13,
        IMPORT_REASON_NOT_FOUND_ALLOWED_DATASERVICE_ACCESSED_BY_DISTRIBUTION: 14,
        IMPORT_REASON_DELETED_DATASET: 15,
        IMPORT_REASON_DELETED_DATASERVICE: 16,
    }

def _get_import_technical_error_code_by_exception(exception):
    return _get_common_technical_error_code_for_exception_by_phase(
        exception=exception,
        phase_code=IMPORT_PHASE_CODE,
    )


# ---------------------------------------------------------------------------
# Fallback phase
# ---------------------------------------------------------------------------

FALLBACK_TECHNICAL_ERROR_ENTRIES = (
    entry("E9501", catalog_messages.DEFAULT_TECHNICAL_ERROR_MESSAGE, "Error general técnico", requires_support_hint=True),
    entry("E9502", catalog_messages.DEFAULT_FALLBACK_SETUP_ERROR_MESSAGE, "Fallback no controlado en configuración", requires_support_hint=True),
    entry("E9503", catalog_messages.DEFAULT_FALLBACK_DOWNLOAD_ERROR_MESSAGE, "Fallback no controlado en descarga", requires_support_hint=True),
    entry("E9504", catalog_messages.DEFAULT_FALLBACK_PREPROCESSING_ERROR_MESSAGE, "Fallback no controlado en preprocesado", requires_support_hint=True),
    entry("E9505", catalog_messages.DEFAULT_FALLBACK_VALIDATION_ERROR_MESSAGE, "Fallback no controlado en validación", requires_support_hint=True),
    entry("E9506", catalog_messages.DEFAULT_FALLBACK_STORAGE_ERROR_MESSAGE, "Fallback no controlado en almacenamiento", requires_support_hint=True),
    entry("E9507", catalog_messages.DEFAULT_FALLBACK_IMPORT_ERROR_MESSAGE, "Fallback no controlado en importación", requires_support_hint=True),
    entry("E9508", catalog_messages.DEFAULT_FALLBACK_UNKNOWN_ERROR_MESSAGE, "Fallback no controlado en fase no clasificada", requires_support_hint=True),
)

FALLBACK_TECHNICAL_WARN_ENTRIES = (
    entry("W9501", catalog_messages.DEFAULT_TECHNICAL_WARN_MESSAGE, "Warning general técnico"),
)

FALLBACK_TECHNICAL_INFO_ENTRIES = (
    entry("I9501", catalog_messages.DEFAULT_TECHNICAL_INFO_MESSAGE, "Información general técnica"),
)

FALLBACK_TECHNICAL_ENTRIES = (
    FALLBACK_TECHNICAL_ERROR_ENTRIES
    + FALLBACK_TECHNICAL_WARN_ENTRIES
    + FALLBACK_TECHNICAL_INFO_ENTRIES
)


def _get_fallback_technical_error_code_by_exception(exception):
    return _get_common_technical_error_code_for_exception_by_phase(
        exception=exception,
        phase_code=FALLBACK_PHASE_CODE,
    )


# ---------------------------------------------------------------------------
# Internal routing maps
# ---------------------------------------------------------------------------

TECHNICAL_REASON_CASES = {
    (REPORT_PHASE_IMPORT, ERROR_LEVEL_CODE): IMPORT_TECHNICAL_ERROR_REASON_CASES,
    (REPORT_PHASE_IMPORT, WARN_LEVEL_CODE): IMPORT_TECHNICAL_WARN_REASON_CASES,
    (REPORT_PHASE_IMPORT, INFO_LEVEL_CODE): IMPORT_TECHNICAL_ERROR_REASON_CASES,
}

TECHNICAL_EXCEPTION_RESOLVERS = {
    REPORT_PHASE_SETUP: _get_setup_technical_error_code_by_exception,
    REPORT_PHASE_DOWNLOAD: _get_download_technical_error_code_by_exception,
    REPORT_PHASE_STORAGE: _get_storage_technical_error_code_by_exception,
    REPORT_PHASE_PREPROCESSING: _get_preprocessing_technical_error_code_by_exception,
    REPORT_PHASE_VALIDATION: _get_validation_technical_error_code_by_exception,
    REPORT_PHASE_IMPORT: _get_import_technical_error_code_by_exception,
    REPORT_PHASE_FALLBACK: _get_fallback_technical_error_code_by_exception,
}


TECHNICAL_ENTRIES = (
    SETUP_TECHNICAL_ENTRIES
    + DOWNLOAD_TECHNICAL_ENTRIES
    + STORAGE_TECHNICAL_ENTRIES
    + PREPROCESSING_TECHNICAL_ENTRIES
    + VALIDATION_TECHNICAL_ENTRIES
    + IMPORT_TECHNICAL_ENTRIES
    + FALLBACK_TECHNICAL_ENTRIES
)
