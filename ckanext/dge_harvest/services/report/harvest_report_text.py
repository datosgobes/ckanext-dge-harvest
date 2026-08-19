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
"""Text normalization helpers for structured harvest report messages.

This module centralizes text coercion, low-level cleaning and report-specific
normalization rules.

Terminology:
- preserved text keeps line breaks and tabs for UI-oriented fields.
- single-line text collapses all whitespace for grouping, fingerprints and CSV.
"""

DISPLAY_MESSAGE_UI_MAX_LENGTH = 2048


def coerce_text(value):
    """Convert arbitrary text-like values to ``str``.

    Bytes are decoded as UTF-8 with replacement. ``None`` is preserved.
    """
    if value is None:
        return None

    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")

    return str(value)


def clean_text(value):
    """Remove persistence-hostile characters and normalize line endings.

    This function does not collapse whitespace. It preserves line breaks and
    tabs after normalizing CRLF/CR line endings to LF.
    """
    value = coerce_text(value)

    if value is None:
        return None

    return value.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")


def truncate_text(value, max_length, suffix):
    """Limit text length while preserving an explicit truncation marker."""
    if value is None:
        return None

    value = coerce_text(value)

    if len(value) <= max_length:
        return value

    if max_length <= len(suffix):
        return suffix[:max_length]

    return value[: max_length - len(suffix)] + suffix


def normalize_optional_text(value):
    """Compact optional text values and coerce blank values to ``None``."""
    value = clean_text(value)

    if value is None:
        return None

    normalized = " ".join(value.split())

    if not normalized:
        return None

    return normalized

def normalize_required_text(field_name, value):
    """Normalize required compact text and reject missing values."""
    normalized = normalize_optional_text(value)

    if normalized is None:
        raise ValueError("{} is required".format(field_name))

    return normalized

def normalize_single_line_text(value):
    """Normalize text to a single line.

    Use this for stable grouping, fingerprints, CSV values and compact raw
    technical summaries.
    """
    return normalize_optional_text(value)

def normalize_preserved_text(value):
    """Normalize text while preserving visible formatting.

    Line breaks and tabs are preserved. Empty or blank-only values become
    ``None``.
    """
    cleaned = clean_text(value)

    if cleaned is None:
        return None

    if not cleaned.strip():
        return None

    return cleaned


def normalize_display_message(value):
    """Normalize the functional visible message.

    The result is single-line and stable. It is suitable for grouping,
    fingerprints, ordering, CSV export and legacy projection.
    """
    return normalize_single_line_text(value)

def normalize_display_message_ui(value, max_length=DISPLAY_MESSAGE_UI_MAX_LENGTH):
    """Normalize the UI visible message.

    The result preserves line breaks and tabs, but is bounded for persistence.
    """
    normalized = normalize_preserved_text(value)

    if normalized is None:
        return None

    return truncate_text(
        normalized,
        max_length=max_length,
        suffix="...[truncated]",
    )

