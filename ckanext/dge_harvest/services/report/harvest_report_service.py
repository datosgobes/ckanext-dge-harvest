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
"""Persistence service for the structured federation report.

This module concentrates the write path for canonical messages, updates
materialized rows, computes fingerprints and coordinates catalog and
legacy-projection helpers.
"""

import datetime
import logging
from ckan.model import Session
from ckan.model.types import make_uuid
from sqlalchemy.exc import IntegrityError

from ckanext.dge_harvest.services.report.harvest_report_catalog import (
    resolve_catalog_message,
)
from ckanext.dge_harvest.model import DgeHarvestMessage, DgeHarvestReportRow
from ckanext.dge_harvest.services.report.harvest_report_fingerprint import (
    build_fingerprint_full,
    build_fingerprint_semantic,
)
from ckanext.dge_harvest.services.report.harvest_report_message import (
    HarvestReportMessage,
)
from ckanext.dge_harvest.services.report.harvest_report_adapter import (
    AdaptedHarvestReportMessage,
)
from ckanext.dge_harvest.services.report.harvest_report_projection import (
    project_legacy_message,
    resolve_legacy_projection,
)
from ckanext.dge_harvest.services.report.harvest_report_text import (
    normalize_display_message_ui,
    normalize_preserved_text,
    normalize_display_message,
)

from ...decorators import log_info
log = logging.getLogger(__name__)

class DgeHarvestReportService(object):
    """Common persistence entrypoint for structured harvest report messages."""

    def __init__(self, session=None):
        """Create the service bound to a SQLAlchemy session-like object."""
        self.session = session or Session

    def create_adapted_message(
        self,
        adapted_message,
        harvest_job_id=None,
        harvest_job=None,
        harvest_object_id=None,
        harvest_object=None,
    ):
        """Create one canonical message from a common adapter output."""
        return self.create_message(
            message=adapted_message.message,
            harvest_job_id=harvest_job_id,
            harvest_job=harvest_job,
            harvest_object_id=harvest_object_id,
            harvest_object=harvest_object,
            raw_message=adapted_message.raw_message,
            details_json=adapted_message.details_json,
            more_info_url=adapted_message.more_info_url,
            legacy_projection=adapted_message.legacy_projection,
            legacy_stage=adapted_message.legacy_stage,
        )

    @log_info
    def create_message(
        self,
        message=None,
        harvest_job_id=None,
        harvest_job=None,
        harvest_object_id=None,
        harvest_object=None,
        level=None,
        phase=None,
        origin=None,
        category=None,
        message_code=None,
        display_message=None,
        raw_message=None,
        details_json=None,
        more_info_url=None,
        fingerprint_full=None,
        fingerprint_semantic=None,
        legacy_projection=None,
        legacy_stage=None,
    ):
        """Create one canonical message and keep all derived stores in sync.

        The method accepts either a normalized ``HarvestReportMessage`` or raw
        fields, resolves catalog defaults, sanitizes the visible message,
        computes grouping fingerprints, persists the canonical event, updates
        the materialized row and, when requested, projects the message to the
        legacy harvest error tables.
        """
        if message is not None:
            self._merge_message_fields(
                message,
                level,
                phase,
                origin,
                category,
                message_code,
                display_message,
            )
            level = message.level
            phase = message.phase
            origin = message.origin
            category = message.category
            message_code = message.message_code
            display_message = message.display_message
            if details_json is None:
                details_json = getattr(message, "context", None)
        #received_message=display_message
        level, resolved_display_message = resolve_catalog_message(
            message_code=message_code,
            level=level,
            display_message=display_message,
        )
        created = datetime.datetime.utcnow()
        display_message_ui = _require_value(
            "display_message_ui",
            normalize_display_message_ui(resolved_display_message)
        )
        display_message = _require_value(
            "display_message",
            normalize_display_message(display_message_ui),
        )
        level = _require_value("level", level)
        phase = _require_value("phase", phase)
        category = _require_value("category", category)
        legacy_projection = resolve_legacy_projection(
            level=level,
            legacy_projection=legacy_projection,
        )
        fingerprint_full = fingerprint_full or build_fingerprint_full(
            level,
            display_message,
            more_info_url,
            message_code=message_code,
        )
        fingerprint_semantic = (
            fingerprint_semantic
            or build_fingerprint_semantic(
                message_code=message_code,
                level=level,
                phase=phase,
                category=category,
                display_message=display_message,
            )
        )
        message = DgeHarvestMessage(
            id=make_uuid(),
            harvest_job_id=_resolve_harvest_job_id(
                harvest_job_id,
                harvest_job,
                harvest_object,
            ),
            harvest_object_id=_resolve_id(harvest_object_id, harvest_object),
            level=level,
            phase=phase,
            origin=_require_value("origin", origin),
            category=category,
            message_code=message_code,
            display_message=display_message,
            display_message_ui=display_message_ui,
            raw_message=raw_message,
            details_json=details_json,
            more_info_url=more_info_url,
            fingerprint_full=fingerprint_full,
            fingerprint_semantic=fingerprint_semantic,
            legacy_projection=legacy_projection,
            created=created,
        )
        self.session.add(message)
        self._flush_session()
        self._upsert_report_row(message, created)
        project_legacy_message(
            legacy_projection=legacy_projection,
            display_message=display_message,
            harvest_job=harvest_job,
            harvest_object=harvest_object,
            phase=phase,
            legacy_stage=legacy_stage,
        )
        return message

    def _upsert_report_row(self, message, timestamp):
        """Insert or increment the visible report row for one message."""
        row = self._find_report_row(message)
        if row:
            row.message_count += 1
            row.last_message_id = message.id
            row.last_seen = timestamp
            row.modified = timestamp
            return row

        if self._supports_nested_transactions():
            try:
                with self.session.begin_nested():
                    row = self._build_report_row(message, timestamp)
                    self.session.add(row)
                    self._flush_session()
                return row
            except IntegrityError:
                row = self._find_report_row(message)
                if row is None:
                    raise
                row.message_count += 1
                row.last_message_id = message.id
                row.last_seen = timestamp
                row.modified = timestamp
                return row

        row = self._build_report_row(message, timestamp)
        self.session.add(row)
        return row

    def _find_report_row(self, message):
        """Return the visible row for one fingerprint when it already exists."""
        return (
            self.session.query(DgeHarvestReportRow)
            .filter_by(
                harvest_job_id=message.harvest_job_id,
                fingerprint_full=message.fingerprint_full,
            )
            .first()
        )

    def _build_report_row(self, message, timestamp):
        """Build the materialized row payload for one canonical message."""
        return DgeHarvestReportRow(
            harvest_job_id=message.harvest_job_id,
            fingerprint_full=message.fingerprint_full,
            fingerprint_semantic=message.fingerprint_semantic,
            level=message.level,
            phase=message.phase,
            origin=message.origin,
            category=message.category,
            message_code=message.message_code,
            display_message=message.display_message,
            display_message_ui=message.display_message_ui,
            more_info_url=message.more_info_url,
            message_count=1,
            first_message_id=message.id,
            last_message_id=message.id,
            first_seen=timestamp,
            last_seen=timestamp,
            created=timestamp,
            modified=timestamp,
        )

    def _supports_nested_transactions(self):
        """Return True when the session can isolate a retryable write block."""
        return hasattr(self.session, "begin_nested") and hasattr(
            self.session,
            "flush",
        )

    def _flush_session(self):
        """Flush pending ORM state when the session implementation supports it."""
        flush = getattr(self.session, "flush", None)
        if flush is not None:
            flush()

    def _merge_message_fields(
        self,
        message,
        level,
        phase,
        origin,
        category,
        message_code,
        display_message,
    ):
        """Reject conflicting duplicates when message object and kwargs mix."""
        if not isinstance(message, HarvestReportMessage):
            raise TypeError("message must be a HarvestReportMessage instance")

        conflicting_fields = []
        for field_name, current_value in (
            ("level", level),
            ("phase", phase),
            ("origin", origin),
            ("category", category),
            ("message_code", message_code),
            ("display_message", display_message),
        ):
            message_value = getattr(message, field_name)
            if field_name == "display_message_ui" and current_value not in (
                None,
                "",
            ):
                current_value = normalize_preserved_text(current_value)
            if current_value not in (None, "") and current_value != message_value:
                conflicting_fields.append(field_name)

        if conflicting_fields:
            raise ValueError(
                "Conflicting message fields: {}".format(
                    ", ".join(conflicting_fields)
                )
            )


def create_adapted_harvest_message(session=None, adapted_message=None, **kwargs):
    """Create a structured harvest message from a common adapter output."""
    return DgeHarvestReportService(session=session).create_adapted_message(
        adapted_message=adapted_message,
        **kwargs
    )

def create_harvest_message(session=None, **kwargs):
    """Create a structured harvest message using the common service."""
    return DgeHarvestReportService(session=session).create_message(**kwargs)


def _resolve_harvest_job_id(harvest_job_id, harvest_job, harvest_object):
    """Resolve the owning harvest job from explicit ids or linked objects."""
    resolved_id = _resolve_id(harvest_job_id, harvest_job)
    if resolved_id:
        return resolved_id
    return _require_value(
        "harvest_job_id",
        getattr(harvest_object, "harvest_job_id", None),
    )


def _resolve_id(explicit_id, domain_object):
    """Prefer an explicit id and fall back to the object's ``id`` attribute."""
    if explicit_id:
        return explicit_id
    return getattr(domain_object, "id", None)


def _require_value(field_name, value):
    """Raise a stable error when a required field is empty."""
    if value is None or value == "":
        raise ValueError("{} is required".format(field_name))
    return value
