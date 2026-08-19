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
"""Visible-message helpers for unified federation report outputs.

This module keeps presentation-safe message composition out of persistence.
The structured storage preserves ``display_message`` and ``message_code`` as
separate fields, while read paths can compose the final user-facing text for
UI and CSV without exposing internal raw payloads.
"""

from ckanext.dge_harvest.services.report.harvest_report_catalog import (
    get_message_catalog_entry,
)
from ckanext.dge_harvest.services.report.harvest_report_catalog_messages import (
    DEFAULT_GENERIC_CONTACT_ERROR_SUFFIX,
)


def build_visible_report_message(display_message, message_code=None):
    """Compose final visible message for report consumers.

    Args:
        display_message (str): Functional message persisted in structured
            storage.
        message_code (str | None): Optional diagnostic code for admins and
            support staff.

    Returns:
        str | None: Visible message ready for UI/CSV. When ``message_code`` is
        present it is appended in a stable suffix so rows with equal functional
        message but different code remain distinguishable to the user.
    """
    if not display_message:
        return display_message

    support_hint = _build_repeat_support_hint(message_code)

    if support_hint:
        display_message = "{}\n{}".format(display_message, support_hint)

    if not message_code:
        return display_message
    return "{}\n(Código: {})".format(display_message, message_code)


def _build_repeat_support_hint(message_code):
    """Return visible repeat hint when catalog marks the code for support."""
    if not message_code:
        return None

    catalog_entry = get_message_catalog_entry(message_code)
    if catalog_entry is None or not catalog_entry.requires_support_hint:
        return None

    return DEFAULT_GENERIC_CONTACT_ERROR_SUFFIX
