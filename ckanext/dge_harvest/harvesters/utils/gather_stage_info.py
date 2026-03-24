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

import logging

log = logging.getLogger(__name__)

class GatherStageInfo():
    def __init__(self) -> None:
        self.total_catalogs_with_warnings = 0
        self.total_wrong_catalogs = 0
        self.total_right_catalogs = 0
        self.total_datasets_with_warnings = 0
        self.total_wrong_datasets = 0
        self.total_right_datasets = 0
        self.total_dataservices_with_warnings = 0
        self.total_wrong_dataservices = 0
        self.total_right_dataservices = 0

    # catalogs
    def add_catalog(self, conforms):
        if conforms:
            self.total_right_catalogs += 1
        else:
            self.total_wrong_catalogs += 1

    # datasets
    def add_dataset(self, conforms):
        if conforms:
            self.total_right_datasets += 1
        else:
            self.total_wrong_datasets += 1

    # dataservices
    def add_dataservice(self, conforms):
        if conforms:
            self.total_right_dataservices += 1
        else:
            self.total_wrong_dataservices += 1

    def __str__(self):
        total_catalogs = self.total_right_catalogs + self.total_wrong_catalogs
        total_datasets = self.total_right_datasets + self.total_wrong_datasets
        total_dataservices = self.total_right_dataservices + self.total_wrong_dataservices
        result = f'''The gather stage info is: \n
            \t- Total number of catalogs: {total_catalogs}
            \t\t + Number of right catalogs: {self.total_right_catalogs}
            \t\t + Number of wrong catalogs: {self.total_wrong_catalogs}
            \t- Total number of datasets: {total_datasets}
            \t\t + Number of right datasets: {self.total_right_datasets}
            \t\t + Number of wrong datasets: {self.total_wrong_datasets}
            \t- Total number of dataservices: {total_dataservices}
            \t\t + Number of right dataservices: {self.total_right_dataservices}
            \t\t + Number of wrong dataservices: {self.total_wrong_dataservices}
        '''
        return result
        