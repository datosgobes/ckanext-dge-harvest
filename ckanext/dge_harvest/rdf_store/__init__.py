# Copyright (C) 2025 Entidad Pública Empresarial Red.es
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

from .rdf_store import RDFStore, RDFStoreException, RDFStoreInternalException
from .rdf_store_helper import RDFStoreHelper
from .rdf_store_insert_or_update import RDFStoreInsertOrUpdate
from .rdf_store_delete import RDFStoreDelete
from .rdf_store_query import RDFStoreQuery

import logging

log = logging.getLogger(__name__)

class RDFStoreComplete():
    def __init__(self, graph_uri):
        self.rdf_store_query = RDFStoreQuery(graph_uri)
        self.rdf_store_insert_or_update = RDFStoreInsertOrUpdate(graph_uri)
        self.rdf_store_delete = RDFStoreDelete(graph_uri)
        self.rdf_store_helper = RDFStoreHelper(graph_uri)
        self.rdf_store_base = RDFStore(graph_uri)

    def update_graph_uri(self, graph_uri):
        self.rdf_store_query.update_graph_uri(graph_uri)
        self.rdf_store_insert_or_update.update_graph_uri(graph_uri)
        self.rdf_store_delete.update_graph_uri(graph_uri)
        self.rdf_store_helper.update_graph_uri(graph_uri)
        self.rdf_store_base.update_graph_uri(graph_uri)
