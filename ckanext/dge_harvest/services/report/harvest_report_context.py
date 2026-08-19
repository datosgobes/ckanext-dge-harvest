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

"""Helpers to build minimal structured context for report message details.

This module standardizes the minimum context that adapted pipeline messages
should preserve in ``details_json`` beyond the visible text. It is the common
entrypoint for future integrations that need to keep functional clues without
coupling them to free-form message strings.
"""
from ckanext.dge_harvest.services.report.harvest_report_text import (
    normalize_optional_text,
)

def build_report_context(
    level,
    phase,
    origin,
    kind=None,
    reason=None,
    field=None,
    metadata_uri=None,
    term_uri=None,
    node_id=None,
    resource_uri=None,
    payload=None,
):
    """Build the minimum structured context envelope for one report message.

    Args:
        level: Structured severity such as ``error`` or ``warning``.
        phase: Structured phase such as ``validation`` or ``preprocessing``.
        origin: Technical origin emitting the message.
        kind: Optional normalized kind of issue.
        reason: Optional normalized reason or subtype.
        field: Optional affected field name.
        metadata_uri: Optional affected predicate or metadata URI.
        term_uri: Optional problematic controlled term URI.
        node_id: Optional identifier of the affected node.
        resource_uri: Optional identifier of the affected resource.
        payload: Optional source-specific nested payload to preserve.

    Returns:
        dict: Context envelope ready to serialize into ``details_json``.
    """
    context = {
        "level": normalize_optional_text(level),
        "phase": normalize_optional_text(phase),
        "origin": normalize_optional_text(origin),
    }

    for field_name, value in (
        ("kind", kind),
        ("reason", reason),
        ("field", field),
        ("metadata_uri", metadata_uri),
        ("term_uri", term_uri),
        ("node_id", node_id),
        ("resource_uri", resource_uri),
    ):
        normalized = normalize_optional_text(value)
        if normalized is not None:
            context[field_name] = normalized

    if payload is not None:
        context["payload"] = payload

    return context



