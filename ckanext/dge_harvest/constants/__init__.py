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

from .constants import ConfigConstants
from .constants import PrefixConstants
from .constants import CatalogConstants
from .constants import CommonPackageConstants    
from .constants import DatasetConstants
from .constants import DataserviceConstants
from .constants import HarvesterConstants
from .constants import ExportCatalogConstants
from .constants import RDFStoreConstants

from .nti_constants import NTIPrefixConstants
from .nti_constants import NTICatalogConstants
from .nti_constants import NTIDatasetConstants
from .nti_constants import NTIHarvesterConstants

from .dcat_ap_es_constants import DCATAPESConfigConstants
from .dcat_ap_es_constants import DCATAPESPrefixConstants
from .dcat_ap_es_constants import DCATAPESCatalogConstants
from .dcat_ap_es_constants import DCATAPESDatasetConstants
from .dcat_ap_es_constants import DCATAPESDistributionConstants
from .dcat_ap_es_constants import DCATAPESDataserviceConstants
from .dcat_ap_es_constants import DCATAPESHarvesterConstants
from .dcat_ap_es_constants import DCATAPESSerializerConstants
from .dcat_ap_es_constants import DcatClassNameEnum
from .dcat_ap_es_constants import HarvestObjectExtraKeyConstants