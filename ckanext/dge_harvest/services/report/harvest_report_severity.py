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
"""Shared severity vocabulary for the harvest federation report.

This module centralizes the currently supported message levels together with
their visual ranking in report queries. The ranking is kept explicit so future
levels such as ``critical`` or ``notice`` can be inserted without spreading
ordering rules across multiple modules.
"""

MESSAGE_LEVEL_ERROR = "error"
MESSAGE_LEVEL_WARNING = "warning"
MESSAGE_LEVEL_INFO = "info"

MESSAGE_ALLOWED_LEVELS = (
    MESSAGE_LEVEL_ERROR,
    MESSAGE_LEVEL_WARNING,
    MESSAGE_LEVEL_INFO,
)

REPORT_LEVEL_RANK = {
    MESSAGE_LEVEL_ERROR: 0,
    MESSAGE_LEVEL_WARNING: 1,
    MESSAGE_LEVEL_INFO: 2,
}
