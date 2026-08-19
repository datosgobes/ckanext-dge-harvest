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

"""Shared harvest-stage exceptions for DGE RDF harvesters."""

from dataclasses import dataclass, field





class PrepareGatherContextError(Exception):
    """Raised when the minimum frozen gather context cannot be prepared."""



class DGEHarvestStageError(Exception):
    """Base error for gather-stage flow controlled by DGE harvesters."""

    report_kind = None
    report_reason = None
    report_phase = None
    report_level = "error"
    display_message = None

    def __init__(self, raw_message, display_message=None, context=None, kind=None):
        super().__init__(raw_message)
        self.raw_message = raw_message
        self.display_message = display_message
        self.context = context or {}
        self.kind = kind or self.report_kind


class RdfValidatorException(DGEHarvestStageError):
    "Raised when a RDF validation fails"

@dataclass
class GatherStageResult:
    """Collected non-blocking gather messages for one fetch step."""

    warnings: list[DGEHarvestStageError] = field(default_factory=list)
    infos: list[DGEHarvestStageError] = field(default_factory=list)

class GatherRdfFormatConfigError(DGEHarvestStageError):
    """Raised when the source RDF format config cannot be parsed."""


class GatherFileNotFoundError(DGEHarvestStageError):
    """Raised when a gather file path does not exist."""

    report_kind = "catalog_access_error"
    report_reason = "FileNotFoundError"


class GatherFileTooLargeError(DGEHarvestStageError):
    """Raised when a gather file exceeds the configured limit."""

    report_kind = "catalog_access_error"
    report_reason = "ContentTooLarge"


class GatherHTTPError(DGEHarvestStageError):
    """Raised when remote HTTP fetch fails."""

    report_kind = "catalog_access_error"
    report_reason = "HTTPError"


class GatherConnectionError(DGEHarvestStageError):
    """Raised when remote HTTP connection fails."""

    report_kind = "catalog_access_error"
    report_reason = "ConnectionError"


class GatherTimeoutError(DGEHarvestStageError):
    """Raised when remote HTTP fetch times out."""

    report_kind = "catalog_access_error"
    report_reason = "Timeout"


class GatherParserError(DGEHarvestStageError):
    """Raised when parser stage fails."""

    report_kind = "catalog_parser_error"
    report_reason = "ParserError"


class GatherHookError(DGEHarvestStageError):
    """Raised when a plugin hook fails during gather."""

    report_kind = "catalog_download_error"
    report_reason = "HookError"


class GatherSoftLimitInfo(DGEHarvestStageError):
    """Raised when file size exceeds soft limit but flow can continue."""

    report_kind = "catalog_file_soft_limit_info"
    report_reason = "soft_limit_exceeded"
    report_level = "warning"


class GatherStageExecutionError(DGEHarvestStageError):
    """Backward-compatible alias for blocking gather errors."""


class GatherStageInfoExecutionError(DGEHarvestStageError):
    """Backward-compatible alias for non-blocking gather info."""

class GatherCatalogError(DGEHarvestStageError):
    """Raised when one or more catalogs contain blocking errors during gather."""

    report_kind = "catalog_error"
    report_reason = "CatalogError"


class GatherCatalogValidationError(DGEHarvestStageError):
    """Raised when one or more catalogs do not pass catalog-level validation."""

    report_kind = "catalog_validation_error"
    report_reason = "CatalogValidationError"


class GatherCatalogsWithErrorsError(DGEHarvestStageError):
    """Raised when one or more catalogs contain errors but the source was readable."""

    report_kind = "catalogs_with_errors"
    report_reason = "CatalogsWithErrors"

class GatherResourceNoNameError(DGEHarvestStageError):
    """Raised when one resouce (dataset or dataservice) not contain a name."""

    report_kind = "catalog_error"
    report_reason = "CatalogError"
    
class GatherResourceMissingNameError(DGEHarvestStageError):
    report_kind = "resource_parse_error"
    report_reason = "ResourceMissingName"
    
class GatherResourceMissingIdentifierError(DGEHarvestStageError):
    report_kind = "resource_parse_error"
    report_reason = "ResourceMissingIdentifier"