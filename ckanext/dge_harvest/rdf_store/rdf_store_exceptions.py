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
"""Exception hierarchy for RDF store access in DGE harvest.

This module keeps Virtuoso transport, SPARQL execution, and generic RDF store
errors separated so higher layers can classify failures with more precision.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class RDFStoreException(Exception):
    """Base public exception for RDF store failures.

    Use this class for failures that callers must treat as RDF store related,
    while still allowing more specific subclasses for transport and query
    classification.
    """

    def __init__(
        self,
        msg: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(msg)
        self.msg = msg
        self.context = context or {}


class RDFStoreInternalException(RDFStoreException):
    """Base internal exception for RDF store implementation errors.

    Lower-level helpers raise this class or one of its subclasses. Public
    wrappers may re-raise it directly when the subclass already carries the
    desired classification.
    """

    def __init__(
        self,
        msg: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(msg, context=context)
        self.msg = msg


class RDFStoreConnectionException(RDFStoreInternalException):
    """Virtuoso transport or endpoint failure.

    Use for DNS, network, endpoint unreachable, timeout, or HTTP transport
    failures that prevent the query from being sent or answered correctly.
    """

    def __init__(
        self,
        msg: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(msg, context=context)
        self.msg = msg


class RDFStoreQueryException(RDFStoreInternalException):
    """Virtuoso query execution or response processing failure.

    Use for SPARQL execution errors, malformed responses, and other query-level
    failures once the endpoint is reachable.
    """

    def __init__(
        self,
        msg: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(msg, context=context)
        self.msg = msg

