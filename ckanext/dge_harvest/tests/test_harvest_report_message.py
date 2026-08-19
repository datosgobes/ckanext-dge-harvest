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

import pytest

from ckanext.dge_harvest.services.report.harvest_report_message import (
    HarvestReportMessage,
)


def test_harvest_report_message_normalizes_common_fields():
    message = HarvestReportMessage(
        level="error",
        phase="validation",
        origin="shacl  validator",
        category="shacl",
        message_code=" E3201 ",
        display_message_ui=" Mensaje \r\n  visible ",
    )

    assert message.origin == "shacl validator"
    assert message.message_code == "E3201"
    assert message.display_message == "Mensaje visible"
    assert message.display_message_ui == " Mensaje \n  visible "


def test_harvest_report_message_requires_allowed_level_and_phase():
    with pytest.raises(ValueError):
        HarvestReportMessage(
            level="fatal",
            phase="validation",
            origin="shacl",
            category="shacl",
            display_message_ui="Mensaje visible",
        )

    with pytest.raises(ValueError):
        HarvestReportMessage(
            level="error",
            phase="import",
            origin="shacl",
            category="shacl",
            display_message_ui="Mensaje visible",
        )


def test_harvest_report_message_accepts_fetch_phase():
    message = HarvestReportMessage(
        level="error",
        phase="fetch",
        origin="harvester",
        category="technical",
        display_message_ui="Mensaje visible",
    )

    assert message.phase == "fetch"


def test_harvest_report_message_as_dict_returns_common_contract():
    message = HarvestReportMessage(
        level="warning",
        phase="preprocessing",
        origin="vocabulary",
        category="vocabulary",
        display_message_ui="Mensaje visible",
    )

    assert message.as_dict() == {
        "level": "warning",
        "phase": "preprocessing",
        "origin": "vocabulary",
        "category": "vocabulary",
        "message_code": None,
        "display_message": "Mensaje visible",
        "display_message_ui": "Mensaje visible",
    }
