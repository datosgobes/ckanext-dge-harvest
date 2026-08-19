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

"""Helpers around the ``LFTNN`` message code convention.

This module centralizes the message-code convention, the available functional
families and the rule that functional reuse is driven by ``FTNN`` while the
severity is represented by ``L``.
"""

from dataclasses import dataclass

from ckanext.dge_harvest.services.report.harvest_report_code_constants import (
    CODE_TO_LEVEL,
    CODE_TO_PHASE,
    FAMILY_CODE_TO_CATEGORY,
    MESSAGE_CODE_PATTERN,
    COMMON_FAMILY_CODE,
    SHACL_FAMILY_CODE,
    VOCABULARY_FAMILY_CODE,
    TECHNICAL_FAMILY_CODE,

)
from ckanext.dge_harvest.services.report.harvest_report_dimensions import (
    REPORT_CATEGORY_COMMON,
    REPORT_CATEGORY_SHACL,
    REPORT_CATEGORY_TECHNICAL,
    REPORT_CATEGORY_VOCABULARY,
)

@dataclass(frozen=True)
class HarvestReportCodeFamily(object):
    """Definition of one functional family inside the LFTNN code space."""

    symbol: str
    category: str
    label: str
    description: str


HARVEST_REPORT_CODE_FAMILIES = (
    HarvestReportCodeFamily(
        symbol=COMMON_FAMILY_CODE,
        category=REPORT_CATEGORY_COMMON,
        label="Común",
        description="Mensajes funcionales reutilizables entre perfiles o validadores.",
    ),
    HarvestReportCodeFamily(
        symbol=SHACL_FAMILY_CODE,
        category=REPORT_CATEGORY_SHACL,
        label="SHACL",
        description="Incumplimientos u observaciones emitidas por validaciones SHACL.",
    ),
    HarvestReportCodeFamily(
        symbol=VOCABULARY_FAMILY_CODE,
        category=REPORT_CATEGORY_VOCABULARY,
        label="Vocabularios",
        description="Problemas de vocabularios controlados, taxonomías y términos normalizados.",
    ),
    HarvestReportCodeFamily(
        symbol=TECHNICAL_FAMILY_CODE,
        category=REPORT_CATEGORY_TECHNICAL,
        label="Infraestructura técnica",
        description="Fallos técnicos controlados de descarga, proceso, validación o almacenamiento.",
    )
)

MESSAGE_CODE_FAMILY_BY_CATEGORY = {
    family.category: family for family in HARVEST_REPORT_CODE_FAMILIES
}
MESSAGE_CODE_FAMILY_BY_SYMBOL = {
    family.symbol: family for family in HARVEST_REPORT_CODE_FAMILIES
}


def normalize_message_code(message_code):
    """Normalize one candidate code to canonical uppercase ``LFTNN`` form."""
    if message_code is None:
        return None
    normalized = "".join(str(message_code).split()).upper()
    if not normalized:
        return None
    return normalized


def parse_message_code(message_code):
    """Parse and validate one normalized ``LFTNN`` code.

    Returns a decoded dictionary so higher-level services can reason in terms
    of semantic attributes instead of raw character positions.
    """
    normalized_code = normalize_message_code(message_code)
    if normalized_code is None:
        return None

    match = MESSAGE_CODE_PATTERN.match(normalized_code)
    if not match:
        raise ValueError(f"message_code must follow LFTNN convention. Current code: {normalized_code}")

    groups = match.groupdict()
    return {
        "code": normalized_code,
        "level_symbol": groups["level"],
        "phase_symbol": groups["phase"],
        "family_symbol": groups["family"],
        "case": groups["case"],
        "level": CODE_TO_LEVEL[groups["level"]],
        "phase": CODE_TO_PHASE[groups["phase"]],
        "category": FAMILY_CODE_TO_CATEGORY[groups["family"]],
    }


def build_message_code(level_symbol, phase_symbol, family_symbol, case_number):
    """Build one normalized ``LFTNN`` code from symbolic parts."""
    level_symbol = _normalize_symbol(level_symbol)
    phase_symbol = _normalize_symbol(phase_symbol)
    family_symbol = _normalize_symbol(family_symbol)
    case_number = str(case_number).zfill(2)

    code = "{}{}{}{}".format(
        level_symbol,
        phase_symbol,
        family_symbol,
        case_number,
    )
    return parse_message_code(code)["code"]


def build_message_code_reuse_key(message_code):
    """Build the functional reuse key ``FTNN`` for one message code.

    The returned key intentionally ignores severity because the same
    functional problem should reuse the same ``FTNN`` even when the visible
    severity changes.
    """
    parsed = parse_message_code(message_code)
    if parsed is None:
        return None

    return "{}{}{}".format(
        parsed["phase_symbol"],
        parsed["family_symbol"],
        parsed["case"],
    )


def should_reuse_message_code(message_code, other_message_code):
    """Return whether two codes represent the same functional problem."""
    left_key = build_message_code_reuse_key(message_code)
    right_key = build_message_code_reuse_key(other_message_code)
    if left_key is None or right_key is None:
        return False
    return left_key == right_key


def get_message_code_family(symbol=None, category=None):
    """Return one registered code family by symbol or category."""
    if symbol is not None and category is not None:
        raise ValueError("provide symbol or category, not both")

    if symbol is not None:
        family = MESSAGE_CODE_FAMILY_BY_SYMBOL.get(_normalize_symbol(symbol))
    elif category is not None:
        normalized_category = "".join(str(category).split()).lower()
        family = MESSAGE_CODE_FAMILY_BY_CATEGORY.get(normalized_category)
    else:
        raise ValueError("symbol or category is required")

    if family is None:
        raise ValueError("unknown message code family")

    return family


def _normalize_symbol(symbol):
    """Normalize one symbolic code component and reject empty values."""
    if symbol is None:
        raise ValueError("message code symbol is required")
    normalized = "".join(str(symbol).split()).upper()
    if not normalized:
        raise ValueError("message code symbol is required")
    return normalized
