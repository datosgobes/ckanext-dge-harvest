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

"""Unit tests for vocabulary functional classification."""

from ckanext.dge_harvest.services.report.harvest_report_vocabulary_classifier import (
    build_vocabulary_message_code,
    REPORT_PHASE_VALIDATION,
    VOCABULARY_REASON_INVALID_VALUE,
    get_vocabulary_error_message_code,
)


def test_get_vocabulary_error_message_code_returns_current_code():
    code = get_vocabulary_error_message_code(
            phase=REPORT_PHASE_VALIDATION,
            reason=VOCABULARY_REASON_INVALID_VALUE,
        )

    assert code == build_vocabulary_message_code("E", "4", 2)


def test_get_vocabulary_fallback_error_message_codefor_phase_uses_validation_default():
    code = get_vocabulary_error_message_code(phase="validation")

    assert code == build_vocabulary_message_code("E", "4", 1)


def test_get_vocabulary_fallback_error_message_codefor_phase_falls_back_for_unknown_phase():
    code = get_vocabulary_error_message_code(phase="storage")

    assert code == build_vocabulary_message_code("E", "4", 1)
