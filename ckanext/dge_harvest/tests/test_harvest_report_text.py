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

from ckanext.dge_harvest.services.report.harvest_report_text import (
    normalize_display_message,
)


def test_normalize_display_message_compacts_whitespace_and_line_breaks():
    assert (
        normalize_display_message("  Error \r\n técnico\t visible  ")
        == "Error técnico visible"
    )


def test_normalize_display_message_removes_null_bytes_and_empty_values():
    assert normalize_display_message("Error\x00 visible") == "Error visible"
    assert normalize_display_message(" \r\n\t ") is None
