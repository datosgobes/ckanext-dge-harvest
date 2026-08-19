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

"""Functional classifier for common harvest report messages.

Public contract:
    _get_common_message_code(level, phase, reason=None, exception=None)

The public resolver never propagates classifier errors to callers. If the
resolution fails because of an invalid level, phase, reason, malformed internal
code, or unexpected bug, it logs the exception and returns a safe fallback code.

Resolution priority:
    1. Specific code by reason.
    2. Specific code by exception.
    3. Default code for level + phase.
    4. Default code for level + fallback phase.
"""

import logging

from ckanext.dcat.exceptions import RDFParserException

from ckanext.dge_harvest.decorators import log_info
from ckanext.dge_harvest.harvesters.dge_harvester_exceptions import (
    GatherCatalogsWithErrorsError,
    GatherFileNotFoundError,
    GatherFileTooLargeError,
    GatherHTTPError,
    GatherParserError,
    GatherSoftLimitInfo,
    GatherTimeoutError,
    RdfValidatorException,
)
from ckanext.dge_harvest.services.report import (
    harvest_report_catalog_messages as catalog_messages,
)
from ckanext.dge_harvest.services.report.harvest_report_catalog_entry import entry
from ckanext.dge_harvest.services.report.harvest_report_code import (
    build_message_code,
)
from ckanext.dge_harvest.services.report.harvest_report_code_constants import (
    COMMON_FAMILY_CODE,
    DOWNLOAD_PHASE_CODE,
    ERROR_LEVEL_CODE,
    FALLBACK_PHASE_CODE,
    INFO_LEVEL_CODE,
    PREPROCESSING_PHASE_CODE,
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

def _build_common_message_code(level_symbol, phase_symbol, case_number):
    """Build one common-family code."""
    return build_message_code(level_symbol, phase_symbol, COMMON_FAMILY_CODE, case_number)


def _build_error_common_message_code(phase_code, case_number):
    return _build_common_message_code(ERROR_LEVEL_CODE, phase_code, case_number)


def _build_warn_common_message_code(phase_code, case_number):
    return _build_common_message_code(WARN_LEVEL_CODE, phase_code, case_number)


def _build_info_common_message_code(phase_code, case_number):
    return _build_common_message_code(INFO_LEVEL_CODE, phase_code, case_number)


def _get_common_message_code(level, phase, reason=None, exception=None):
    """Return a safe common message code for the requested context.

    This is the only function new callers should use.
    """
    level_symbol = LEVEL_TO_CODE.get(level)

    try:
        if level_symbol is None:
            raise ValueError("Unsupported report level: {}".format(level))

        code = _get_common_message_code_by_reason(level_symbol=level_symbol, phase=phase, reason=reason )
        if code:
            return code

        code = _get_common_message_code_by_exception(level_symbol=level_symbol, phase=phase, exception=exception)
        if code:
            return code

        return _build_default_common_message_code(level_symbol=level_symbol, phase=phase)

    except Exception:
        log.exception(
            "Failed to resolve common harvest report message code. "
            "level=%r phase=%r reason=%r exception=%r",
            level, phase, reason, exception.__class__.__name__ if exception else None,
        )
        return _build_fallback_common_message_code(level_symbol=level_symbol or ERROR_LEVEL_CODE)


def get_common_error_message_code(phase, reason=None, exception=None):
    """Convenience wrapper for common error messages."""
    return _get_common_message_code(level=MESSAGE_LEVEL_ERROR, phase=phase, reason=reason, exception=exception)


def get_common_warning_message_code(phase, reason=None, exception=None):
    """Convenience wrapper for common warning messages."""
    return _get_common_message_code(level=MESSAGE_LEVEL_WARNING, phase=phase, reason=reason, exception=exception)


def get_common_info_message_code(phase, reason=None, exception=None):
    """Convenience wrapper for common info messages."""
    return _get_common_message_code(level=MESSAGE_LEVEL_INFO, phase=phase, reason=reason, exception=exception)


def _build_default_common_message_code(level_symbol, phase):
    """Return default common code for level + phase, falling back by phase."""
    phase_code = PHASE_TO_CODE.get(phase, FALLBACK_PHASE_CODE)
    return _build_common_message_code(level_symbol, phase_code, 1)


def _build_fallback_common_message_code(level_symbol):
    """Return guaranteed common fallback code for one level symbol."""
    return _build_common_message_code(level_symbol, FALLBACK_PHASE_CODE, 1)


def _get_common_message_code_by_reason(level_symbol, phase, reason):
    """Resolve common code from normalized reason when available."""
    if not reason:
        return None

    phase_reasons = COMMON_REASON_CASES.get((phase, level_symbol)) or {}
    case_number = phase_reasons.get(reason)

    if case_number is None:
        return None

    phase_code = PHASE_TO_CODE.get(phase, FALLBACK_PHASE_CODE)
    return _build_common_message_code(level_symbol, phase_code, case_number)


def _get_common_message_code_by_exception(level_symbol, phase, exception):
    """Resolve common code from exception when available.

    Exception-based classification is only meaningful for known errors/warnings.
    Info codes normally come from reason or default phase classification.
    """
    if exception is None:
        return None

    resolver = COMMON_EXCEPTION_RESOLVERS.get((phase, level_symbol))
    if resolver is None:
        return None

    return resolver(exception)

# ---------------------------------------------------------------------------
# Common constants
# ---------------------------------------------------------------------------

COMMON_REASON_JOB_RENEWED_BEFORE_FINISH = "finished_job"
COMMON_REASON_ABORTED_JOB = "aborted_job"

# ---------------------------------------------------------------------------
# Setup phase
# ---------------------------------------------------------------------------

SETUP_COMMON_ERROR_ENTRIES = (
    entry("E0001", catalog_messages.DEFAULT_COMMON_ERROR_MESSAGE, "Error funcional general durante la fase inicial de configuración", requires_support_hint=True),
)

SETUP_COMMON_WARN_ENTRIES = (
    entry("W0001", catalog_messages.DEFAULT_COMMON_WARN_MESSAGE, "Warning funcional general durante la fase inicial de configuración"),
)

SETUP_COMMON_INFO_ENTRIES = (
    entry("I0001", catalog_messages.DEFAULT_COMMON_INFO_MESSAGE, "Información funcional general durante la fase inicial de configuración"),
    entry("I0002", catalog_messages.DEFAULT_COMMON_FINISHED_JOB_INFO_MESSAGE,"Tarea de federación marcada como finalizada antes de procesarse por completo", requires_support_hint=True),
    entry("I0003", catalog_messages.DEFAULT_COMMON_ABORTED_JOB_INFO_MESSAGE,"Tarea de federación abortada", requires_support_hint=True),
)

SETUP_COMMON_INFO_REASON_CASES = {
    COMMON_REASON_JOB_RENEWED_BEFORE_FINISH: 2,
    COMMON_REASON_ABORTED_JOB: 3,
}

SETUP_COMMON_ENTRIES = (
    SETUP_COMMON_ERROR_ENTRIES
    + SETUP_COMMON_WARN_ENTRIES
    + SETUP_COMMON_INFO_ENTRIES
)


# ---------------------------------------------------------------------------
# Download phase
# ---------------------------------------------------------------------------

DOWNLOAD_COMMON_ERROR_ENTRIES = (
    entry("E1001", catalog_messages.DEFAULT_COMMON_ERROR_MESSAGE, "Error funcional general durante descarga", requires_support_hint=True),
    entry("E1002", catalog_messages.DEFAULT_COMMON_RDF_PARSER_ERROR_MESSAGE, "RDF mal formado"),
    entry("E1003", catalog_messages.DEFAULT_COMMON_FILE_NOT_FOUND_ERROR_MESSAGE, "Fichero RDF no encontrado"),
    entry("E1004", catalog_messages.DEFAULT_COMMON_FILE_TOO_LARGE_ERROR_MESSAGE, "Fichero RDF demasiado grande"),
    entry("E1005", catalog_messages.DEFAULT_COMMON_HTTP_ERROR_MESSAGE, "Error HTTP durante descarga"),
    entry("E1006", catalog_messages.DEFAULT_COMMON_TIMEOUT_ERROR_MESSAGE, "Timeout durante descarga"),
    entry("E1007", catalog_messages.DEFAULT_COMMON_GATHER_PARSER_ERROR_MESSAGE, "Error de parseo durante descarga"),
)

DOWNLOAD_COMMON_WARN_ENTRIES = (
    entry("W1001", catalog_messages.DEFAULT_COMMON_WARN_MESSAGE, "Warning funcional general durante descarga"),
    entry("W1002", catalog_messages.DEFAULT_COMMON_FILE_NEXT_TO_MAX_LARGE_WARN_MESSAGE, "Warning de fichero cerca del límite máximo"),
)

DOWNLOAD_COMMON_INFO_ENTRIES = (
    entry("I1001", catalog_messages.DEFAULT_COMMON_INFO_MESSAGE, "Información funcional general durante descarga"),
    entry("I1002", catalog_messages.DEFAULT_COMMON_FINISHED_JOB_INFO_MESSAGE,"Tarea de federación marcada como finalizada antes de procesarse por completo", requires_support_hint=True),
    entry("I1003", catalog_messages.DEFAULT_COMMON_ABORTED_JOB_INFO_MESSAGE,"Tarea de federación abortada", requires_support_hint=True),
)

DOWNLOAD_COMMON_INFO_REASON_CASES = {
    COMMON_REASON_JOB_RENEWED_BEFORE_FINISH: 2,
    COMMON_REASON_ABORTED_JOB: 3,
}

DOWNLOAD_COMMON_ENTRIES = (
    DOWNLOAD_COMMON_ERROR_ENTRIES
    + DOWNLOAD_COMMON_WARN_ENTRIES
    + DOWNLOAD_COMMON_INFO_ENTRIES
)


def _get_download_common_error_code_by_exception(exception):
    if isinstance(exception, (RDFParserException, SyntaxError)):
        return _build_error_common_message_code(DOWNLOAD_PHASE_CODE, 2)
    if isinstance(exception, GatherFileNotFoundError):
        return _build_error_common_message_code(DOWNLOAD_PHASE_CODE, 3)
    if isinstance(exception, GatherFileTooLargeError):
        return _build_error_common_message_code(DOWNLOAD_PHASE_CODE, 4)
    if isinstance(exception, GatherHTTPError):
        return _build_error_common_message_code(DOWNLOAD_PHASE_CODE, 5)
    if isinstance(exception, GatherTimeoutError):
        return _build_error_common_message_code(DOWNLOAD_PHASE_CODE, 6)
    if isinstance(exception, GatherParserError):
        return _build_error_common_message_code(DOWNLOAD_PHASE_CODE, 7)
    return None


def _get_download_common_warning_code_by_exception(exception):
    if isinstance(exception, GatherSoftLimitInfo):
        return _build_warn_common_message_code(DOWNLOAD_PHASE_CODE, 2)
    return None


# ---------------------------------------------------------------------------
# Storage phase
# ---------------------------------------------------------------------------

STORAGE_COMMON_ERROR_ENTRIES = (
    entry("E2001", catalog_messages.DEFAULT_COMMON_ERROR_MESSAGE, "Error funcional general durante el almacenamiento del RDF", requires_support_hint=True),
)

STORAGE_COMMON_WARN_ENTRIES = (
    entry("W2001", catalog_messages.DEFAULT_COMMON_WARN_MESSAGE, "Warning funcional general durante el almacenamiento del RDF"),
)

STORAGE_COMMON_INFO_ENTRIES = (
    entry("I2001", catalog_messages.DEFAULT_COMMON_INFO_MESSAGE, "Información funcional general durante el almacenamiento del RDF"),
    entry("I2002", catalog_messages.DEFAULT_COMMON_FINISHED_JOB_INFO_MESSAGE, "Tarea de federación marcada como finalizada antes de procesarse por completo", requires_support_hint=True),
    entry("I2003", catalog_messages.DEFAULT_COMMON_ABORTED_JOB_INFO_MESSAGE, "Tarea de federación abortada", requires_support_hint=True),
)

STORAGE_COMMON_INFO_REASON_CASES = {
    COMMON_REASON_JOB_RENEWED_BEFORE_FINISH: 2,
    COMMON_REASON_ABORTED_JOB: 3,
}

STORAGE_COMMON_ENTRIES = (
    STORAGE_COMMON_ERROR_ENTRIES
    + STORAGE_COMMON_WARN_ENTRIES
    + STORAGE_COMMON_INFO_ENTRIES
)


# ---------------------------------------------------------------------------
# Preprocessing phase
# ---------------------------------------------------------------------------

PREPROCESSING_COMMON_ERROR_ENTRIES = (
    entry("E3001", catalog_messages.DEFAULT_COMMON_ERROR_MESSAGE, "Error funcional general durante preprocesamiento", requires_support_hint=True),
    entry("E3002", catalog_messages.DEFAULT_COMMON_REASON_NON_CANONICAL_NAMESPACES_ERROR_MESSAGE, "Encontrandos namespaces no canónicos"),
    entry("E3003", catalog_messages.DEFAULT_COMMON_ERROR_MESSAGE, "Error al reemplazar Blank Nodes en RDF"),
    entry("E3004", catalog_messages.DEFAULT_COMMON_REASON_ROOT_CATALOG_URI_NOT_FOUND_ERROR_MESSAGE, "Catálogo raiz no encontrado en RDF"),
    entry("E3005", catalog_messages.DEFAULT_COMMON_ERROR_MESSAGE, "Preprocesamiento del RDF inválido"),
    entry("E3006", catalog_messages.DEFAULT_COMMON_ERROR_MESSAGE, "Error al hacer el backup del grafo de la fuente"),
)

PREPROCESSING_COMMON_WARN_ENTRIES = (
    entry("W3001", catalog_messages.DEFAULT_COMMON_WARN_MESSAGE, "Warning funcional general durante preprocesamiento"),
)

PREPROCESSING_COMMON_INFO_ENTRIES = (
    entry("I3001", catalog_messages.DEFAULT_COMMON_INFO_MESSAGE, "Información funcional general durante preprocesamiento"),
    entry("I3002",catalog_messages.DEFAULT_COMMON_FINISHED_JOB_INFO_MESSAGE, "Tarea de federación marcada como finalizada antes de procesarse por completo", requires_support_hint=True),
    entry("I3003", catalog_messages.DEFAULT_COMMON_ABORTED_JOB_INFO_MESSAGE, "Tarea de federación abortada", requires_support_hint=True),
    entry("I3004", catalog_messages.DEFAULT_COMMON_REASON_PORTAL_ORGANIZATION_DATA_MESSAGE, "Borrada información de organización sustituible por datos.gob.es"),
    entry("I3005", catalog_messages.DEFAULT_COMMON_REASON_UNREFERENCED_DATASET_MESSAGE, "Borrado dataset no referenciado en catálogo"),
    entry("I3006", catalog_messages.DEFAULT_COMMON_REASON_UNREFERENCED_DATASERVICE_MESSAGE, "Borrado dataservice no referenciado en catálogo"),
    entry("I3007", catalog_messages.DEFAULT_COMMON_REASON_UNDESCRIBED_DATASET_MESSAGE, "Borrado dataset no descrito"),
    entry("I3008", catalog_messages.DEFAULT_COMMON_REASON_UNDESCRIBED_DATASERVICE_MESSAGE, "Borrado dataservice no descrito"),
    entry("I3009", catalog_messages.DEFAULT_COMMON_REASON_UNREFERENCED_DESCRIBED_DATASET_MESSAGE, "Borrado dataset descrito no referenciado en catálogo"),
    entry("I3010", catalog_messages.DEFAULT_COMMON_REASON_UNREFERENCED_DESCRIBED_DATASERVICE_MESSAGE, "Borrado dataservice descrito no referenciado en catálogo"),
    entry("I3011", catalog_messages.DEFAULT_COMMON_REASON_UNREFERENCED_NODE_MESSAGE, "Borrado nodo no referenciado"),
    entry("I3012", catalog_messages.DEFAULT_COMMON_REASON_UNDESCRIBED_CATALOG_MESSAGE, "Borrado catálogo no descrito"),
    entry("I3013", catalog_messages.DEFAULT_COMMON_REASON_CATALOG_RECORD_MESSAGE, "Borrado CatalogRecord"),
    entry("I3014", catalog_messages.DEFAULT_COMMON_REASON_DATASET_REFERENCE_IN_MULTIPLE_CATALOGS_MESSAGE, "Borrado dataset referenciado en múltiples catálogos"),
    entry("I3015", catalog_messages.DEFAULT_COMMON_REASON_DATASERVICE_REFERENCE_IN_MULTIPLE_CATALOGS_MESSAGE, "Borrado dataservice referenciado en múltiples catálogos"),
)

# Preprocessing reasons.
PREPROCESSING_REASON_NON_CANONICAL_NAMESPACES = "non_canonical_namespaces"
PREPROCESSING_REASON_WRONG_REPLACEMENT_BNODES = "wrong_replacement_bnodes"
PREPROCESSING_REASON_ROOT_CATALOG_URI_NOT_FOUND =  "root_catalog_uri_not_found"
PREPROCESSING_REASON_INVALID_PREPROCESSING_OF_SOURCE_RDF = "invalid_preprocessing_of_source_rdf"
PREPROCESSING_REASON_ERROR_DOING_BACKUP_FROM_SOURCE_GRAPH = "error_doing_backup_from_source_graph"

PREPROCESSING_REASON_PORTAL_ORGANIZATION_DATA = "portal_organization_data"
PREPROCESSING_REASON_UNREFERENCED_DATASET = "unreferenced_dataset_in_catalog"
PREPROCESSING_REASON_UNREFERENCED_DATASERVICE = "unreferenced_dataservice_in_catalog"
PREPROCESSING_REASON_UNDESCRIBED_DATASET = "undescribed_dataset"
PREPROCESSING_REASON_UNDESCRIBED_DATASERVICE = "undescribed_dataservice"
PREPROCESSING_REASON_UNREFERENCED_DESCRIBED_DATASET = "unreferenced_described_dataset_in_catalog"
PREPROCESSING_REASON_UNREFERENCED_DESCRIBED_DATASERVICE = "unreferenced_described_dataservice_in_catalog"
PREPROCESSING_REASON_UNREFERENCED_NODE = "unreferenced_node"
PREPROCESSING_REASON_UNDESCRIBED_CATALOG = "undescribed_catalog"
PREPROCESSING_REASON_CATALOG_RECORD = "catalog_record"
PREPROCESSING_REASON_DATASET_REFERENCE_IN_MULTIPLE_CATALOGS = "dataset_referenced_in_multiple_catalogs"
PREPROCESSING_REASON_DATASERVICE_REFERENCE_IN_MULTIPLE_CATALOGS = "dataservice_referenced_in_multiple_catalogs"

PREPROCESSING_COMMON_ERROR_REASON_CASES = {
    PREPROCESSING_REASON_NON_CANONICAL_NAMESPACES: 2,
    PREPROCESSING_REASON_WRONG_REPLACEMENT_BNODES: 3,
    PREPROCESSING_REASON_ROOT_CATALOG_URI_NOT_FOUND: 4,
    PREPROCESSING_REASON_INVALID_PREPROCESSING_OF_SOURCE_RDF: 5,
    PREPROCESSING_REASON_ERROR_DOING_BACKUP_FROM_SOURCE_GRAPH: 6,
}

PREPROCESSING_COMMON_INFO_REASON_CASES = {
    COMMON_REASON_JOB_RENEWED_BEFORE_FINISH: 2,
    COMMON_REASON_ABORTED_JOB: 3,
    PREPROCESSING_REASON_PORTAL_ORGANIZATION_DATA: 4,
    PREPROCESSING_REASON_UNREFERENCED_DATASET: 5,
    PREPROCESSING_REASON_UNREFERENCED_DATASERVICE: 6,
    PREPROCESSING_REASON_UNDESCRIBED_DATASET: 7,
    PREPROCESSING_REASON_UNDESCRIBED_DATASERVICE: 8,
    PREPROCESSING_REASON_UNREFERENCED_DESCRIBED_DATASET: 9,
    PREPROCESSING_REASON_UNREFERENCED_DESCRIBED_DATASERVICE: 10,
    PREPROCESSING_REASON_UNREFERENCED_NODE: 11,
    PREPROCESSING_REASON_UNDESCRIBED_CATALOG: 12,
    PREPROCESSING_REASON_CATALOG_RECORD: 13,
    PREPROCESSING_REASON_DATASET_REFERENCE_IN_MULTIPLE_CATALOGS: 14,
    PREPROCESSING_REASON_DATASERVICE_REFERENCE_IN_MULTIPLE_CATALOGS: 15,
}


PREPROCESSING_COMMON_ENTRIES = (
    PREPROCESSING_COMMON_ERROR_ENTRIES
    + PREPROCESSING_COMMON_WARN_ENTRIES
    + PREPROCESSING_COMMON_INFO_ENTRIES
)


def _get_preprocessing_common_error_code_by_exception(exception):
    if isinstance(exception, RdfValidatorException):
        return _build_error_common_message_code(PREPROCESSING_PHASE_CODE, 1)
    return None


# ---------------------------------------------------------------------------
# Validation phase
# ---------------------------------------------------------------------------

VALIDATION_COMMON_ERROR_ENTRIES = (
    entry("E4001", catalog_messages.DEFAULT_COMMON_ERROR_MESSAGE, "Error funcional general durante validación", requires_support_hint=True),
    entry("E4002", catalog_messages.DEFAULT_COMMON_VALIDATION_ERROR_MESSAGE, "Error general de validación RDF"),
    entry("E4003", catalog_messages.DEFAULT_COMMON_WRONG_CATALOGS_ERROR_MESSAGE, "Hay catálogos con errores"),
    entry("E4004", catalog_messages.DEFAULT_COMMON_PARSER_ERROR_MESSAGE, "Errores de parseo en catálogo"),
    entry("E4005", catalog_messages.DEFAULT_COMMON_PARSER_ERROR_MESSAGE, "Errores de parseo en dataset"),
    entry("E4006", catalog_messages.DEFAULT_COMMON_PARSER_ERROR_MESSAGE, "Errores de parseo en dataservice"),
    entry("E4007", catalog_messages.DEFAULT_COMMON_PARSER_ERROR_MESSAGE, "Errores de parseo en distribution"),
    entry("E4008", catalog_messages.DEFAULT_COMMON_NO_VALID_DISTRIBUTION_IN_DASASET, "Dataset sin distribuciones válidas"),
)

VALIDATION_COMMON_WARN_ENTRIES = (
    entry("W4001", catalog_messages.DEFAULT_COMMON_WARN_MESSAGE, "Warning funcional general durante validación"),
    entry("W4004", catalog_messages.DEFAULT_COMMON_PARSER_WARN_MESSAGE, "Warnings de parseo en catálogo"),
    entry("W4005", catalog_messages.DEFAULT_COMMON_PARSER_WARN_MESSAGE, "Warnings de parseo en dataset"),
    entry("W4006", catalog_messages.DEFAULT_COMMON_PARSER_WARN_MESSAGE, "Warnings de parseo en dataservice"),
    entry("W4007", catalog_messages.DEFAULT_COMMON_PARSER_WARN_MESSAGE, "Warnings de parseo en distribution"),
)

VALIDATION_COMMON_INFO_ENTRIES = (
    entry("I4001", catalog_messages.DEFAULT_COMMON_INFO_MESSAGE, "Información funcional general durante validación"),
    entry("I4002",catalog_messages.DEFAULT_COMMON_FINISHED_JOB_INFO_MESSAGE, "Tarea de federación marcada como finalizada antes de procesarse por completo", requires_support_hint=True),
    entry("I4003", catalog_messages.DEFAULT_COMMON_ABORTED_JOB_INFO_MESSAGE, "Tarea de federación abortada", requires_support_hint=True),
    entry("I4004", catalog_messages.DEFAULT_COMMON_DELETED_RESOURCE_INFO_MESSAGE, "Información de recurso eliminado por no cumplir especificaciones"),
)

VALIDATION_REASON_NO_VALID_DISTRIBUTION_IN_DATASET = "no_valid_distribution_in_dataset"
VALIDATION_REASON_DELETED_NO_VALID_RESOURCE = "deleted_invalid_resource"
VALIDATION_REASON_WRONG_CATALOGS = "there_are_wrong_catalogs"
VALIDATION_REASON_INVALID_PARSE_CATALOG = "invalid_parse_catalog"
VALIDATION_REASON_INVALID_PARSE_DATASET = "invalid_parse_dataset"
VALIDATION_REASON_INVALID_PARSE_DATASERVICE = "invalid_parse_dataservice"
VALIDATION_REASON_INVALID_PARSE_DISTRIBUTION = "invalid_parse_distribution"

VALIDATION_REASON_WARNING_PARSE_CATALOG = "warning_parse_catalog"
VALIDATION_REASON_WARNING_PARSE_DATASET = "warning_parse_dataset"
VALIDATION_REASON_WARNING_PARSE_DATASERVICE = "warning_parse_dataservice"
VALIDATION_REASON_WARNING_PARSE_DISTRIBUTION = "warning_parse_distribution"

VALIDATION_COMMON_ERROR_REASON_CASES = {
    VALIDATION_REASON_WRONG_CATALOGS: 3,
    VALIDATION_REASON_INVALID_PARSE_CATALOG: 4,
    VALIDATION_REASON_INVALID_PARSE_DATASET: 5,
    VALIDATION_REASON_INVALID_PARSE_DATASERVICE: 6,
    VALIDATION_REASON_INVALID_PARSE_DISTRIBUTION: 7,
    VALIDATION_REASON_NO_VALID_DISTRIBUTION_IN_DATASET: 8,
}

VALIDATION_COMMON_WARNING_REASON_CASES = {
    VALIDATION_REASON_WARNING_PARSE_CATALOG: 4,
    VALIDATION_REASON_WARNING_PARSE_DATASET: 5,
    VALIDATION_REASON_WARNING_PARSE_DATASERVICE: 6,
    VALIDATION_REASON_WARNING_PARSE_DISTRIBUTION: 7,
}
VALIDATION_COMMON_INFO_REASON_CASES = {
    COMMON_REASON_JOB_RENEWED_BEFORE_FINISH: 2,
    COMMON_REASON_ABORTED_JOB: 3,
    VALIDATION_REASON_DELETED_NO_VALID_RESOURCE: 4,
}


VALIDATION_COMMON_ENTRIES = (
    VALIDATION_COMMON_ERROR_ENTRIES
    + VALIDATION_COMMON_WARN_ENTRIES
    + VALIDATION_COMMON_INFO_ENTRIES
)


def _get_validation_common_error_code_by_exception(exception):
    if isinstance(exception, RdfValidatorException):
        return _build_error_common_message_code(VALIDATION_PHASE_CODE, 2)
    if isinstance(exception, GatherCatalogsWithErrorsError):
        return _build_error_common_message_code(VALIDATION_PHASE_CODE, 3)
    return None


# ---------------------------------------------------------------------------
# Import phase
# ---------------------------------------------------------------------------

IMPORT_COMMON_ERROR_ENTRIES = (
    entry("E5001", catalog_messages.DEFAULT_COMMON_ERROR_MESSAGE, "Error funcional general durante importación", requires_support_hint=True),
)

IMPORT_COMMON_WARN_ENTRIES = (
    entry("W5001", catalog_messages.DEFAULT_COMMON_WARN_MESSAGE, "Warning funcional general durante importación"),
)

IMPORT_COMMON_INFO_ENTRIES = (
    entry("I5001", catalog_messages.DEFAULT_COMMON_INFO_MESSAGE, "Información funcional general durante importación"),
    entry("I5002",catalog_messages.DEFAULT_COMMON_FINISHED_JOB_INFO_MESSAGE, "Tarea de federación marcada como finalizada antes de procesarse por completo", requires_support_hint=True),
    entry("I5003", catalog_messages.DEFAULT_COMMON_ABORTED_JOB_INFO_MESSAGE, "Tarea de federación abortada", requires_support_hint=True),
)

IMPORT_COMMON_INFO_REASON_CASES = {
        COMMON_REASON_JOB_RENEWED_BEFORE_FINISH: 2,
        COMMON_REASON_ABORTED_JOB: 3,
    }

IMPORT_COMMON_ENTRIES = (
    IMPORT_COMMON_ERROR_ENTRIES
    + IMPORT_COMMON_WARN_ENTRIES
    + IMPORT_COMMON_INFO_ENTRIES
)


# ---------------------------------------------------------------------------
# Fallback phase
# ---------------------------------------------------------------------------

FALLBACK_COMMON_ERROR_ENTRIES = (
    entry("E9001", catalog_messages.DEFAULT_COMMON_ERROR_MESSAGE, "Error funcional general", requires_support_hint=True),
)

FALLBACK_COMMON_WARN_ENTRIES = (
    entry("W9001", catalog_messages.DEFAULT_COMMON_WARN_MESSAGE, "Warning funcional general"),
)

FALLBACK_COMMON_INFO_ENTRIES = (
    entry("I9001", catalog_messages.DEFAULT_COMMON_INFO_MESSAGE, "Información funcional general"),
    entry("I9002",catalog_messages.DEFAULT_COMMON_FINISHED_JOB_INFO_MESSAGE, "Tarea de federación marcada como finalizada antes de procesarse por completo", requires_support_hint=True),
    entry("I9003", catalog_messages.DEFAULT_COMMON_ABORTED_JOB_INFO_MESSAGE, "Tarea de federación abortada", requires_support_hint=True),
)

FALLBACK_COMMON_INFO_REASON_CASES = {
        COMMON_REASON_JOB_RENEWED_BEFORE_FINISH: 2,
        COMMON_REASON_ABORTED_JOB: 3,
    }

FALLBACK_COMMON_ENTRIES = (
    FALLBACK_COMMON_ERROR_ENTRIES
    + FALLBACK_COMMON_WARN_ENTRIES
    + FALLBACK_COMMON_INFO_ENTRIES
)


# ---------------------------------------------------------------------------
# Internal routing maps
# ---------------------------------------------------------------------------

COMMON_REASON_CASES = {
    # Finished / aborted job info messages by phase.
    (REPORT_PHASE_SETUP, INFO_LEVEL_CODE): SETUP_COMMON_INFO_REASON_CASES,
    (REPORT_PHASE_DOWNLOAD, INFO_LEVEL_CODE): DOWNLOAD_COMMON_INFO_REASON_CASES,
    (REPORT_PHASE_STORAGE, INFO_LEVEL_CODE): STORAGE_COMMON_ERROR_ENTRIES,
    (REPORT_PHASE_PREPROCESSING, INFO_LEVEL_CODE): PREPROCESSING_COMMON_INFO_REASON_CASES,
    (REPORT_PHASE_PREPROCESSING, ERROR_LEVEL_CODE): PREPROCESSING_COMMON_ERROR_REASON_CASES,
    (REPORT_PHASE_VALIDATION, ERROR_LEVEL_CODE): VALIDATION_COMMON_ERROR_REASON_CASES,
    (REPORT_PHASE_VALIDATION, WARN_LEVEL_CODE): VALIDATION_COMMON_WARNING_REASON_CASES,
    (REPORT_PHASE_VALIDATION, INFO_LEVEL_CODE): VALIDATION_COMMON_INFO_REASON_CASES,
    (REPORT_PHASE_IMPORT, INFO_LEVEL_CODE): IMPORT_COMMON_INFO_REASON_CASES,
    (REPORT_PHASE_FALLBACK, INFO_LEVEL_CODE): FALLBACK_COMMON_INFO_REASON_CASES,
}

COMMON_EXCEPTION_RESOLVERS = {
    (REPORT_PHASE_DOWNLOAD, ERROR_LEVEL_CODE): _get_download_common_error_code_by_exception,
    (REPORT_PHASE_DOWNLOAD, WARN_LEVEL_CODE): _get_download_common_warning_code_by_exception,
    (REPORT_PHASE_PREPROCESSING, ERROR_LEVEL_CODE): _get_preprocessing_common_error_code_by_exception,
    (REPORT_PHASE_VALIDATION, ERROR_LEVEL_CODE): _get_validation_common_error_code_by_exception,
}


COMMON_ENTRIES = (
    SETUP_COMMON_ENTRIES
    + DOWNLOAD_COMMON_ENTRIES
    + STORAGE_COMMON_ENTRIES
    + PREPROCESSING_COMMON_ENTRIES
    + VALIDATION_COMMON_ENTRIES
    + IMPORT_COMMON_ENTRIES
    + FALLBACK_COMMON_ENTRIES
)
