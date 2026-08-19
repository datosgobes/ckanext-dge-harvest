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
"""Query helpers for the unified federation report action.

This module centralizes request normalization, mode detection and structured
row reads for the federation report action. It keeps CKAN action wiring thin
and isolates ORM access needed by the report contract.
"""

import logging
import re

from ckan.model import Session
from ckan.plugins import toolkit
from ckanext.dge_harvest.constants.constants import HarvesterConstants
from ckanext.dge_harvest.model import get_job_extra
from ckanext.dge_harvest.model import DgeHarvestReportRow
from ckanext.dge_harvest.services.report.harvest_report_severity import (
    MESSAGE_ALLOWED_LEVELS,
    REPORT_LEVEL_RANK,
)
from ckanext.dge_harvest.services.report.harvest_report_visible_message import (
    build_visible_report_message,
)
from ckanext.dge_harvest.services.report.harvest_report_text import (
    normalize_preserved_text,
)
from sqlalchemy import asc, case, desc
from werkzeug.routing import BuildError


log = logging.getLogger(__name__)


DEFAULT_REPORT_PAGE = 1
DEFAULT_REPORT_LIMIT = 20
MAX_REPORT_LIMIT = 100
DEFAULT_REPORT_SORT_BY = "count"
DEFAULT_REPORT_SORT_DIR = "desc"
ALLOWED_REPORT_SORT_BY = ("type", "message", "count")
ALLOWED_REPORT_SORT_DIR = ("asc", "desc")
ALLOWED_REPORT_MESSAGE_TYPES = MESSAGE_ALLOWED_LEVELS
REPORT_MODE_STRUCTURED = "structured"
REPORT_MODE_LEGACY = "legacy"
DCAT_AP_ES_GUIDE_URL = "https://datosgobes.github.io/DCAT-AP-ES"
DCAT_AP_ES_GUIDE_LABEL = "DCAT-AP-ES"
NTI_RISP_GUIDE_URL = "https://datosgobes.github.io/NTI-RISP/"
NTI_RISP_GUIDE_LABEL = "NTI-RISP"
LEGACY_WARNING_PREFIXES = (
    "[warning",
    "[warnings",
    "[shacl warning"
)
LEGACY_INFO_PREFIXES = (
    "[info",
)
LEGACY_MORE_INFO_PATTERN = re.compile(
    r"\s*ver más información en:\s*(https?://\S+)\s*$",
    re.IGNORECASE,
)


def normalize_report_query(data_dict):
    """Normalize request parameters for the unified report action.

    Args:
        data_dict: Raw action payload from the client.

    Returns:
        dict: Normalized query parameters with validated pagination, filtering
        and sorting fields.

    Raises:
        ValueError: If one of the supported parameters is invalid.
    """
    normalized = data_dict or {}
    default_limit = _get_report_default_limit()
    max_limit = _get_report_max_limit()
    default_sort_by = _get_report_default_sort_by()
    default_sort_dir = _get_report_default_sort_dir()
    page = _normalize_positive_int(
        normalized.get("page", DEFAULT_REPORT_PAGE),
        "page",
    )
    limit = _normalize_positive_int(
        normalized.get("limit", default_limit),
        "limit",
    )
    limit = min(limit, max_limit)
    message_type = _normalize_message_type(normalized.get("message_type"))
    sort_by = _normalize_choice(
        normalized.get("sort_by", default_sort_by),
        ALLOWED_REPORT_SORT_BY,
        "sort_by",
    )
    sort_dir = _normalize_choice(
        normalized.get("sort_dir", default_sort_dir),
        ALLOWED_REPORT_SORT_DIR,
        "sort_dir",
    )
    return {
        "page": page,
        "limit": limit,
        "message_type": message_type,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }


def resolve_report_mode(harvest_job_id, session=None):
    """Return the report mode for one harvest job.

    Jobs with materialized rows use ``structured`` mode. Jobs without them fall
    back to ``legacy`` mode.
    """
    active_session = session or Session
    structured_row = (
        active_session.query(DgeHarvestReportRow.id)
        .filter(DgeHarvestReportRow.harvest_job_id == harvest_job_id)
        .first()
    )
    if structured_row:
        return REPORT_MODE_STRUCTURED
    return REPORT_MODE_LEGACY


def build_empty_report_response(harvest_job_id, mode, query):
    """Build the base response contract for the unified report action."""
    return {
        "job_id": harvest_job_id,
        "mode": mode,
        "rows": [],
        "summary": {
            "total": 0,
            "error": 0,
            "warning": 0,
            "info": 0,
        },
        "total": 0,
        "page": query["page"],
        "limit": query["limit"],
        "message_type": query["message_type"],
        "sort_by": query["sort_by"],
        "sort_dir": query["sort_dir"],
        "guide_url": None,
        "csv_url": None,
    }


def resolve_report_guide_url(
    harvest_job_id,
    extra_getter=None,
    config_getter=None,
    fallback_source_type=None,
    fallback_source_config=None,
):
    """Resolve the profile guide URL for one harvest job.

    The guide is derived from the source context frozen at gather start. The
    current implementation uses ``source_type_at_run`` as the primary signal
    and falls back to coarse inspection of ``source_config_at_run`` only when
    the source type is not enough.

    Args:
        harvest_job_id (str): Harvest job identifier.
        extra_getter: Optional callable ``(job_id, key, default) -> value`` for
            tests.
        config_getter: Optional config accessor for tests.

    Returns:
        str | None: Resolved guide URL or ``None`` if the job profile cannot be
            determined.
    """
    resolved_extra_getter = extra_getter or get_job_extra
    resolved_config_getter = config_getter or toolkit.config.get

    source_type = resolved_extra_getter(
        harvest_job_id,
        HarvesterConstants.SOURCE_TYPE_AT_RUN,
        None,
    )
    source_config = resolved_extra_getter(
        harvest_job_id,
        HarvesterConstants.SOURCE_CONFIG_AT_RUN,
        None,
    )
    guide_key = _detect_guide_profile_key(
        source_type or fallback_source_type,
        source_config or fallback_source_config,
    )
    if guide_key == "nti":
        return (resolved_config_getter(
            "ckanext.dge_harvest.dge_nti.url",
            NTI_RISP_GUIDE_URL,
        ),
        resolved_config_getter(
            "ckanext.dge_harvest.dge_nti.label",
            NTI_RISP_GUIDE_LABEL,
        ))
    if guide_key == "dcat_ap_es":
        return (resolved_config_getter(
            "ckanext.dge_harvest.dge_dcat_ap_es.url",
            DCAT_AP_ES_GUIDE_URL,
        ),
        resolved_config_getter(
            "ckanext.dge_harvest.dge_dcat_ap_es.label",
            DCAT_AP_ES_GUIDE_LABEL,
        ))
    return None, None


def build_report_csv_url(source_name, harvest_job_id, query):
    """Build the CSV download URL aligned with the current report query.

    The CSV export preserves the active filter and ordering parameters, but it
    does not pin pagination because downloads should reflect the logical report
    contents instead of the current visible slice.

    Args:
        source_name (str): Harvest source name used by the route.
        harvest_job_id (str): Harvest job identifier.
        query (dict): Normalized report query parameters.

    Returns:
        str: Download URL for the CSV export route.
    """
    try:
        return toolkit.url_for(
            "dgeHarvester.report_csv",
            source=source_name,
            id=harvest_job_id,
            message_type=query["message_type"] or None,
            sort_by=query["sort_by"],
            sort_dir=query["sort_dir"],
        )
    except BuildError:
        log.exception(
            "CSV report route is not available for harvest job %s",
            harvest_job_id,
        )
        return None


def read_legacy_report_data(harvest_job_id, context, get_action=None):
    """Read the legacy harvest report payload for one job.

    The transitional fallback deliberately reuses ``ckanext-harvest`` legacy
    reporting so the new action can serve historical jobs before the legacy
    payload is adapted to the unified visual row contract.

    Args:
        harvest_job_id (str): Harvest job identifier.
        context (dict): CKAN action context.
        get_action: Optional injected action resolver for unit tests.

    Returns:
        dict: Raw legacy payload with ``gather_errors`` and ``object_errors``.
    """
    action_getter = get_action or toolkit.get_action
    return action_getter("harvest_job_report")(context, {"id": harvest_job_id})


def build_legacy_report_response(harvest_job_id, query, legacy_report_data):
    """Build the visual report payload for a legacy harvest job.

    Legacy gather and object errors are adapted to the same table contract used
    by structured jobs. The original legacy payload is still exposed under
    ``legacy_report`` for compatibility during the transition.

    Args:
        harvest_job_id (str): Harvest job identifier.
        query (dict): Normalized report query parameters.
        legacy_report_data (dict): Raw payload from ``harvest_job_report``.

    Returns:
        dict: Legacy-mode response carrying adapted rows and the raw fallback
            payload.
    """
    legacy_rows = _build_legacy_visual_rows(legacy_report_data)
    filtered_rows = _apply_legacy_message_type_filter(legacy_rows, query)
    ordered_rows = _sort_report_rows(filtered_rows, query)
    offset = (query["page"] - 1) * query["limit"]
    paginated_rows = ordered_rows[offset:offset + query["limit"]]
    response = build_empty_report_response(
        harvest_job_id=harvest_job_id,
        mode=REPORT_MODE_LEGACY,
        query=query,
    )
    response["rows"] = paginated_rows
    response["summary"] = _build_report_summary(legacy_rows)
    response["total"] = len(ordered_rows)
    response["legacy_report"] = legacy_report_data
    return response


def build_csv_report_rows(
    harvest_job_id,
    query,
    context,
    session=None,
    get_action=None,
):
    """Return all report rows for CSV export using the unified row contract.

    Args:
        harvest_job_id (str): Harvest job identifier.
        query (dict): Normalized query with filter and ordering fields.
        context (dict): CKAN action context, used for legacy fallback reads.
        session: Optional SQLAlchemy session override for tests.
        get_action: Optional action getter override for tests.

    Returns:
        list[dict]: Complete set of filtered and ordered rows aligned with the
            visual table contract.
    """
    active_session = session or Session
    mode = resolve_report_mode(harvest_job_id=harvest_job_id, session=active_session)
    if mode == REPORT_MODE_STRUCTURED:
        return _build_all_structured_csv_rows(
            harvest_job_id=harvest_job_id,
            query=query,
            session=active_session,
        )
    legacy_report_data = read_legacy_report_data(
        harvest_job_id=harvest_job_id,
        context=context,
        get_action=get_action,
    )
    legacy_rows = _build_legacy_visual_rows(legacy_report_data)
    filtered_rows = _apply_legacy_message_type_filter(legacy_rows, query)
    return _sort_report_rows(filtered_rows, query)


def _build_all_structured_csv_rows(harvest_job_id, query, session=None):
    """Read all structured rows for CSV export without pagination."""
    active_session = session or Session
    base_query = (
        active_session.query(DgeHarvestReportRow)
        .filter(DgeHarvestReportRow.harvest_job_id == harvest_job_id)
    )
    if _is_stub_query(base_query):
        filtered_rows = _apply_structured_message_type_filter_to_rows(
            base_query._rows,
            query,
        )
        ordered_rows = _sort_report_rows(filtered_rows, query)
        return [_serialize_structured_gather_report_row(row) for row in ordered_rows]
    base_query = _apply_structured_message_type_filter(base_query, query)
    base_query = base_query.order_by(*_build_structured_ordering(query))
    return [
        _serialize_structured_gather_report_row(row)
        for row in base_query.all()
    ]


def build_structured_gather_report_response(harvest_job_id, query, session=None):
    """Build the paginated response for one structured harvest report.

    Args:
        harvest_job_id (str): Harvest job identifier.
        query (dict): Normalized report query parameters.
        session: Optional SQLAlchemy session override for tests.

    Returns:
        dict: Structured-mode response with paginated rows and total count.
    """
    active_session = session or Session
    base_query = (
        active_session.query(DgeHarvestReportRow)
        .filter(DgeHarvestReportRow.harvest_job_id == harvest_job_id)
    )
    if _is_stub_query(base_query):
        return _build_structured_gather_report_response_from_stub_rows(
            harvest_job_id=harvest_job_id,
            query=query,
            rows=base_query._rows,
        )
    base_query = _apply_structured_message_type_filter(base_query, query)
    base_query = base_query.order_by(*_build_structured_ordering(query))
    total = base_query.count()
    rows = (
        base_query.offset((query["page"] - 1) * query["limit"])
        .limit(query["limit"])
        .all()
    )
    response = build_empty_report_response(
        harvest_job_id=harvest_job_id,
        mode=REPORT_MODE_STRUCTURED,
        query=query,
    )
    response["rows"] = [_serialize_structured_gather_report_row(row) for row in rows]
    response["summary"] = _build_report_summary(
        active_session.query(DgeHarvestReportRow)
        .filter(DgeHarvestReportRow.harvest_job_id == harvest_job_id)
        .all()
    )
    response["total"] = total
    return response


def _apply_structured_message_type_filter(base_query, query):
    """Apply the optional structured ``message_type`` filter."""
    if query["message_type"] is None:
        return base_query
    return base_query.filter(DgeHarvestReportRow.level == query["message_type"])


def _build_structured_ordering(query):
    """Build SQLAlchemy ordering expressions for structured rows."""
    direction = asc if query["sort_dir"] == "asc" else desc
    if query["sort_by"] == "type":
        level_order = case(
            REPORT_LEVEL_RANK,
            value=DgeHarvestReportRow.level,
            else_=len(REPORT_LEVEL_RANK),
        )
        return (
            direction(level_order),
            asc(DgeHarvestReportRow.display_message),
            asc(DgeHarvestReportRow.message_code),
        )
    if query["sort_by"] == "message":
        return (
            direction(DgeHarvestReportRow.display_message),
            direction(DgeHarvestReportRow.message_code),
            desc(DgeHarvestReportRow.message_count),
        )
    return (
        direction(DgeHarvestReportRow.message_count),
        asc(DgeHarvestReportRow.display_message),
        asc(DgeHarvestReportRow.message_code),
    )


def _build_structured_gather_report_response_from_stub_rows(
    harvest_job_id, query, rows
):
    """Emulate structured filtering, sorting and pagination for unit tests."""
    filtered_rows = _apply_structured_message_type_filter_to_rows(rows, query)
    ordered_rows = _sort_report_rows(filtered_rows, query)
    offset = (query["page"] - 1) * query["limit"]
    paginated_rows = ordered_rows[offset:offset + query["limit"]]
    response = build_empty_report_response(
        harvest_job_id=harvest_job_id,
        mode=REPORT_MODE_STRUCTURED,
        query=query,
    )
    response["rows"] = [
        _serialize_structured_gather_report_row(row) for row in paginated_rows
    ]
    response["summary"] = _build_report_summary(rows)
    response["total"] = len(ordered_rows)
    return response


def _apply_structured_message_type_filter_to_rows(rows, query):
    """Filter structured rows in memory for unit tests."""
    if query["message_type"] is None:
        return list(rows)
    return [row for row in rows if row.level == query["message_type"]]


def _sort_structured_rows(rows, query):
    """Deprecated compatibility wrapper over the shared row sorter."""
    return _sort_report_rows(rows, query)


def _sort_report_rows(rows, query):
    """Sort report rows in memory using the unified report semantics."""
    if query["sort_by"] == "type":
        ordered = sorted(
            rows,
            key=lambda row: _get_row_message_value(row),
        )
        return sorted(
            ordered,
            key=lambda row: REPORT_LEVEL_RANK.get(
                _get_row_type_value(row), len(REPORT_LEVEL_RANK)
            ),
            reverse=query["sort_dir"] == "desc",
        )
    if query["sort_by"] == "message":
        ordered = sorted(
            rows,
            key=lambda row: _get_row_count_value(row),
            reverse=True,
        )
        return sorted(
            ordered,
            key=lambda row: _get_row_message_value(row),
            reverse=query["sort_dir"] == "desc",
        )
    ordered = sorted(rows, key=lambda row: _get_row_message_value(row))
    return sorted(
        ordered,
        key=lambda row: _get_row_count_value(row),
        reverse=query["sort_dir"] == "desc",
    )


def _build_report_summary(rows):
    """Build global severity totals for the report header.

    The summary is calculated from the complete logical report contents before
    pagination so the UI can render stable chips for `Todos`, `Errores`,
    `Warnings` e `Info` independently of the current page or active filter.

    Args:
        rows (list): Structured ORM rows or already adapted dict-based rows.

    Returns:
        dict: Severity totals plus an overall `total` count.
    """
    summary = {
        "total": 0,
        "error": 0,
        "warning": 0,
        "info": 0,
    }
    for row in rows:
        row_type = _get_row_type_value(row)
        row_count = _get_row_count_value(row) or 0
        if row_type in summary:
            summary[row_type] += row_count
        summary["total"] += row_count
    return summary


def _is_stub_query(query):
    """Return whether the received query object is the in-memory test stub."""
    return hasattr(query, "_rows")


def _serialize_structured_gather_report_row(row):
    """Adapt one materialized row to the visual table contract.

    Args:
        row (DgeHarvestReportRow): Materialized row from the structured store.

    Returns:
        dict: Row contract consumed by the future UI and CSV export.
    """
    return {
        "type": row.level,
        "message": build_visible_report_message(
            row.display_message,
            getattr(row, "message_code", None),
        ),
        "message_ui": build_visible_report_message(
            _get_row_display_message_ui_value(row),
            getattr(row, "message_code", None),
        ),
        "count": row.message_count,
        "actions": {
            "more_info_url": row.more_info_url,
        },
    }


def _build_legacy_visual_rows(legacy_report_data):
    """Aggregate the legacy harvest payload into the unified row contract."""
    grouped_rows = {}
    for gather_error in legacy_report_data.get("gather_errors", []):
        _increment_legacy_row(
            grouped_rows=grouped_rows,
            message=_normalize_legacy_message(gather_error.get("message")),
            message_ui=_normalize_legacy_message_ui(gather_error.get("message")),
        )
    for object_data in legacy_report_data.get("object_errors", {}).values():
        for object_error in object_data.get("errors", []):
            message = _normalize_legacy_message(
                object_error.get("message"),
                line=object_error.get("line"),
            )
            _increment_legacy_row(
                grouped_rows=grouped_rows,
                message=message,
                message_ui=_normalize_legacy_message_ui(
                    object_error.get("message"),
                    line=object_error.get("line"),
                ),
            )
    return list(grouped_rows.values())


def _increment_legacy_row(grouped_rows, message, message_ui):
    """Increase the aggregated count for one legacy message."""
    cleaned_message, more_info_url = _extract_legacy_more_info_url(message)
    row_type = _parse_legacy_row_type(cleaned_message)
    row_key = (row_type, cleaned_message, more_info_url)
    if row_key not in grouped_rows:
        grouped_rows[row_key] = {
            "type": row_type,
            "message": cleaned_message,
            "message_ui": message_ui,
            "count": 0,
            "actions": {"more_info_url": more_info_url},
        }
    grouped_rows[row_key]["count"] += 1


def _normalize_legacy_message(message, line=None):
    """Normalize one legacy message for visual grouping and display."""
    normalized = " ".join(str(message or "").split())
    if line is not None:
        return "{} (line {})".format(normalized, line)
    return normalized


def _normalize_legacy_message_ui(message, line=None):
    """Preserve one legacy message for UI rendering."""
    normalized = normalize_preserved_text(message) or ""
    if line is not None:
        return "{} (line {})".format(normalized, line)
    return normalized


def _parse_legacy_row_type(message):
    """Infer the visual severity from one legacy textual message."""
    normalized = (message or "").strip().lower()
    if normalized.startswith(LEGACY_WARNING_PREFIXES):
        return "warning"
    if normalized.startswith(LEGACY_INFO_PREFIXES):
        return "info"
    return "error"


def _extract_legacy_more_info_url(message):
    """Split the optional legacy help suffix from the visible message."""
    normalized_message = message or ""
    match = LEGACY_MORE_INFO_PATTERN.search(normalized_message)
    if not match:
        return normalized_message, None
    cleaned_message = LEGACY_MORE_INFO_PATTERN.sub("", normalized_message)
    return cleaned_message.rstrip(" ."), match.group(1)


def _apply_legacy_message_type_filter(rows, query):
    """Filter legacy visual rows by normalized type."""
    if query["message_type"] is None:
        return list(rows)
    return [
        row for row in rows if row.get("type") == query["message_type"]
    ]


def _get_row_type_value(row):
    """Return the normalized type for either ORM or dict-based rows."""
    return getattr(row, "level", None) or row.get("type")


def _get_row_message_value(row):
    """Return the message value for either ORM or dict-based rows."""
    if hasattr(row, "display_message"):
        return build_visible_report_message(
            getattr(row, "display_message", None),
            getattr(row, "message_code", None),
        )
    return row.get("message")


def _get_row_display_message_ui_value(row):
    """Return the formatted message value for either ORM or dict-based rows."""
    if hasattr(row, "display_message_ui"):
        return getattr(row, "display_message_ui", None) or getattr(
            row,
            "display_message",
            None,
        )
    return row.get("message_ui") or row.get("message")


def _get_row_count_value(row):
    """Return the count value for either ORM or dict-based rows."""
    return getattr(row, "message_count", None) or row.get("count")


def _normalize_positive_int(value, field_name):
    """Normalize one positive integer query parameter."""
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise ValueError("{} must be an integer".format(field_name))
    if normalized < 1:
        raise ValueError("{} must be greater than 0".format(field_name))
    return normalized


def _get_report_default_limit():
    """Return the configured default page size for the report UI."""
    return _get_positive_int_config(
        "ckanext.dge_harvest.report.default_limit",
        DEFAULT_REPORT_LIMIT,
    )


def _get_report_max_limit():
    """Return the configured maximum page size for the report UI."""
    return _get_positive_int_config(
        "ckanext.dge_harvest.report.max_limit",
        MAX_REPORT_LIMIT,
    )


def _get_report_default_sort_by():
    """Return the configured default sort field for the report UI."""
    configured = toolkit.config.get(
        "ckanext.dge_harvest.report.default_sort_by",
        DEFAULT_REPORT_SORT_BY,
    )
    normalized = str(configured).strip().lower()
    if normalized not in ALLOWED_REPORT_SORT_BY:
        return DEFAULT_REPORT_SORT_BY
    return normalized


def _get_report_default_sort_dir():
    """Return the configured default sort direction for the report UI."""
    configured = toolkit.config.get(
        "ckanext.dge_harvest.report.default_sort_dir",
        DEFAULT_REPORT_SORT_DIR,
    )
    normalized = str(configured).strip().lower()
    if normalized not in ALLOWED_REPORT_SORT_DIR:
        return DEFAULT_REPORT_SORT_DIR
    return normalized


def _get_positive_int_config(config_key, default_value):
    """Read a positive integer config value with safe fallback."""
    configured = toolkit.config.get(config_key, default_value)
    try:
        normalized = int(configured)
    except (TypeError, ValueError):
        return default_value
    if normalized < 1:
        return default_value
    return normalized


def _normalize_message_type(value):
    """Normalize the optional message type filter."""
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    if normalized not in ALLOWED_REPORT_MESSAGE_TYPES:
        raise ValueError(
            "message_type must be one of {}".format(
                ALLOWED_REPORT_MESSAGE_TYPES
            )
        )
    return normalized


def _detect_guide_profile_key(source_type, source_config):
    """Infer the profile guide key from frozen source context."""
    normalized_type = (source_type or "").strip().lower()
    normalized_config = (source_config or "").strip().lower()

    if normalized_type == "dge_rdf":
        return "nti"
    if normalized_type == "dge_dcat_ap_es_rdf":
        return "dcat_ap_es"
    if "dge_nti_profile" in normalized_config or "nti-risp" in normalized_config:
        return "nti"
    if "dcat_ap_es" in normalized_config or "dcat-ap-es" in normalized_config:
        return "dcat_ap_es"
    return None


def _normalize_choice(value, allowed_values, field_name):
    """Normalize one closed-set string parameter."""
    normalized = str(value).strip().lower()
    if normalized not in allowed_values:
        raise ValueError(
            "{} must be one of {}".format(field_name, allowed_values)
        )
    return normalized
