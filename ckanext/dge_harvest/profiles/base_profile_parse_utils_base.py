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

import logging
import json

from datetime import timedelta
from rdflib import term, URIRef, BNode, Literal, ConjunctiveGraph

from ckan.plugins.toolkit import config
from ckanext.dcat.processors import RDFParserException
from isodate import isoduration, ISO8601Error, Duration

log = logging.getLogger(__name__)

from ..constants.dcat_ap_es_constants import DCATAPESPrefixConstants
from ..constants.nti_constants import NTIHarvesterConstants, NTIDatasetConstants
from ..constants.dcat_ap_es_constants import (NAMESPACES, DCT, DCAT, FOAF, RDF, ADMS, XSD_NAMESPACE, TIME, TIME_TYPES, SKOS_NAMESPACE)
from ..decorators import log_debug

class BaseProfileParseUtilsBase():
    '''
    class containing utility methods for all profiles
    '''

    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    def __init__(self, graph):
        # profile's graph
        self._g = graph

    @log_debug
    def _get_frequency(self, subject, predicate):
        '''
        Returns a dict with details about dct:accrualPeriodicity
        depending on the format received
        '''
        if (subject, predicate, None) not in self._g:
            return None, None, None
        
        ftype = None
        fvalue = None
        is_duration = False
        accrual_periodicity = False
                
        for o in self._g.objects(subject, predicate):
            is_duration = False
            frequency = None
            if accrual_periodicity:
                raise RDFParserException(NTIHarvesterConstants.UNEXPECTED_MULTIPLE_OBJECTS)
            accrual_periodicity = True
            if isinstance(o, Literal) and o.datatype==XSD_NAMESPACE.duration:
                frequency = str(o)
                is_duration = True
            if isinstance(o, URIRef) or isinstance(o, BNode):
                if str(o).startswith(DCATAPESPrefixConstants.FREQUENCY_PREFIX):
                    frequency = str(o)
                    ftype = "uri"
                    fvalue = -1
                    return ftype, fvalue, frequency
                
                if '/bnode/' in str(o) or isinstance(o, BNode):
                    if (o, RDF.type, DCT.Frequency) in self._g:
                        num_rdf_value_nodes = 0
                        for period_value in self._g.objects(o, RDF.value):
                            num_rdf_value_nodes = num_rdf_value_nodes + 1
                            if num_rdf_value_nodes > 1:
                                raise RDFParserException(
                                    NTIHarvesterConstants.UNEXPECTED_MULTIPLE_SUBOBJECTS.format('rdf:value'))
                            if period_value is not None and (isinstance(period_value, URIRef) or isinstance(period_value, BNode)):
                                if (period_value, RDF.type, TIME.DurationDescription) in self._g:
                                    num_duration_description_value = 0
                                    for p, o in self._g.predicate_objects(period_value):
                                        if isinstance(p, URIRef) and p in TIME_TYPES:
                                            num_duration_description_value = num_duration_description_value + 1
                                            if num_duration_description_value > 1:
                                                raise RDFParserException(NTIHarvesterConstants.UNEXPECTED_MULTIPLE_SUB_SUBOBJECTS.format(
                                                    'time', 'time:DurationDescription'))
                                            ftype = str(p).split('#')[1]
                                            if isinstance(o, Literal):
                                                fvalue = str(o)
                            elif period_value is not None and isinstance(period_value, Literal) and period_value.datatype == XSD_NAMESPACE.duration:
                                frequency = str(period_value)
                                is_duration = True
                
            if is_duration and frequency:
                try:
                    duration = isoduration.parse_duration(frequency)
                    if isinstance(duration, Duration) or \
                            isinstance(duration, timedelta):
                        years = months = weeks = days = hours = minutes = seconds = 0
                        aux_value = 0

                        # years
                        if hasattr(duration, 'years'):
                            years = duration.years if duration.years else 0
                            aux_value = years
                            if duration.years:
                                if (duration.years > 0 or
                                        (duration.years == 0 and not ftype)):
                                    ftype = TIME.years.split('#')[1]
                                    fvalue = aux_value

                        # months
                        if hasattr(duration, 'months'):
                            months = duration.months if duration.months else 0
                            aux_value = years * 12 + months
                            if (duration.months > 0 or
                                    (duration.months == 0 and not ftype)):
                                ftype = TIME.months.split('#')[1]
                                fvalue = aux_value

                        # weeks
                        if hasattr(duration, 'weeks'):
                            weeks = duration.weeks if duration.weeks else 0
                            aux_value = years * 52 + \
                                months * 4 + \
                                weeks
                            if (duration.weeks > 0 or
                                    (duration.weeks == 0 and not ftype)):
                                ftype = TIME.weeks.split('#')[1]
                                fvalue = aux_value

                        # days
                        if hasattr(duration, 'days'):
                            days = duration.days if duration.days else 0
                            aux_value = years * 365 + \
                                months * 30 + \
                                weeks * 7 + \
                                days
                            if (duration.days > 0 or
                                    (duration.days == 0 and not ftype)):
                                ftype = TIME.days.split('#')[1]
                                fvalue = aux_value

                        # hours
                        if hasattr(duration, 'hours'):
                            hours = duration.hours if duration.hours else 0
                            aux_value = fvalue * 24 + hours
                            if (duration.hours > 0 or
                                    (duration.hours == 0 and not ftype)):
                                ftype = TIME.hours.split('#')[1]
                                fvalue = aux_value

                        # minutes
                        if hasattr(duration, 'minutes'):
                            minutes = duration.minutes if duration.minutes else 0
                            aux_value = fvalue * 60 + minutes
                            if (duration.minutes > 0 or
                                    (duration.minutes == 0 and not ftype)):
                                ftype = TIME.minutes.split('#')[1]
                                fvalue = aux_value

                        # seconds
                        if hasattr(duration, 'seconds'):
                            seconds = duration.seconds if duration.seconds else 0
                            aux_value = fvalue * 60 + seconds
                            if (duration.seconds > 0 or
                                    (duration.seconds == 0 and not ftype)):
                                ftype = TIME.seconds.split('#')[1]
                                fvalue = aux_value
                except TypeError as e:
                    errormsg = NTIHarvesterConstants.UNEXPECTED_COMPLETE_DEFINITION % (
                        'TypeError', e)
                    log.error(f"Exception {type(e)}: {str(e)}" , exc_info=True)
                    raise RDFParserException(errormsg)
                except ISO8601Error as e:
                    errormsg = NTIHarvesterConstants.UNEXPECTED_COMPLETE_DEFINITION % (
                        'ISO8601Error', e)
                    log.error(f"Exception {type(e)}: {str(e)}" , exc_info=True)
                    raise RDFParserException(errormsg)
                except:
                    errormsg = NTIHarvesterConstants.UNEXPECTED_DEFINITION
                    log.error(f"Exception {type(e)}: {str(e)}" , exc_info=True)
                    raise RDFParserException(errormsg)
        
            if ftype and fvalue is not None:
                try:
                    fvalue = int(float(fvalue))
                except ValueError as e:
                    errormsg = NTIHarvesterConstants.UNEXPECTED_INTEGER_VALUE % (e)
                    raise RDFParserException(str(e))
            else:
                errormsg = NTIHarvesterConstants.UNEXPECTED_INCOMPLETE_VALUE
                raise RDFParserException(errormsg)
            return ftype, fvalue, ""
