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

# coding=utf-8
import logging
import traceback
import inspect
import re
from typing import List
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from ..harvester_config_reader import HarvesterConfigReader
from ..constants.dcat_ap_es_constants import DCATAPESConfigConstants as ConfigConstants
from ..constants.dcat_ap_es_constants import NAMESPACES, RDF_PREFIX, DCT_PREFIX, DCAT_PREFIX
from ..helpers import dge_harvest_organizations_available
from ..decorators import log_debug, log_info

log = logging.getLogger(__name__)

class RDFXmlParserConstants:
# FILES PROCESSORS
    READ_MODE = 'r'
    READ_WRITE_MODE = 'r+'
    WRITE_MODE = 'w'
    APPEND_MODE = 'a'

    DEFAULT_NAMESPACES = NAMESPACES
    DATASET_TAG =  '{' + f'{DEFAULT_NAMESPACES[DCAT_PREFIX]}' + '}Dataset'
    DATASERVICE_TAG =  '{' + f'{DEFAULT_NAMESPACES[DCAT_PREFIX]}' + '}DataService'
    TEMPLATE_TAG = 'TEMPLATE'
    CATALOG_TAG = '{' + f'{DEFAULT_NAMESPACES[DCAT_PREFIX]}' + '}Catalog'
    CATALOG_TAG_NAMESPACE = 'dcat:Catalog'
    DATASET_REFERENCE_TAG_NAMESPACE = 'dcat:dataset'
    DATASET_TAG_NAMESPACE = 'dcat:Dataset'
    DATASERVICE_REFERENCE_TAG_NAMESPACE = 'dcat:service'
    DATASERVICE_TAG_NAMESPACE = 'dcat:DataService'
    CATALOG_RECORD_REFERENCE_TAG_NAMESPACE = 'dcat:record'
    CATALOG_RECORD_TAG_NAMESPACE = 'dcat:CatalogRecord'
    ROOT_TAG = 'Root'

    CLOSE_CATALOG_ELEMENT = '</dcat:Catalog>'
    CLOSE_RDF_ELEMENT = '</rdf:RDF>'
    CLOSE_ROOT_ELEMENT = '</Root>'
    OPEN_ROOT_ELEMENT= '<Root>'
    OPEN_CLOSE_TEMPLATE_ELEMENT = '<TEMPLATE />'

    END_CLOSE_ROOT_ELEMENT_LENGTH_FILE_POINTER= 7

    ENCODING = 'utf-8'

    XMLNS_REGEX = '\sxmlns[^"]+"[^"]+"'
    
    RDF_ABOUT_ATTRIB_KEY = '{' + f'{DEFAULT_NAMESPACES[RDF_PREFIX]}' + '}about'
    RDF_RESOURCE_ATTRIB_KEY = '{' + f'{DEFAULT_NAMESPACES[RDF_PREFIX]}' + '}resource'
    DCT_HAS_PART_ATTRIB_KEY = '{' + f'{DEFAULT_NAMESPACES[DCT_PREFIX]}' + '}hasPart'

"""
    rdf: string in rdf format getting from serialized a block of catalogs, datasets and dataservices and their metadata
"""
class RDFXmlParserBase:

    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    @log_debug
    def __init__(self, filepath_rdf_root_catalog:str, config_reader:HarvesterConfigReader, available_organizations: dict[str, List[str]] = None):        
        # Final catalog file that contains all export data
        self._filepath_final_rdf = filepath_rdf_root_catalog 
        self._file_final_rdf = None
        
        # Template file where refactor and process datasets and metadata
        self._filepath_rdf_root_catalog_template = config_reader.get_property(ConfigConstants.SECTION_RDF_EXPORT, 'rdf.export.root_catalog_template.filepath', '/mnt/gmv/sync/datosgobes.rdf')
        self._file_rdf_root_catalog_template = None
        
        # Template file where refactor and process catalog with manual and NTI datatets and dataservices
        self._filepath_rdf_internal_subcatalog_template = config_reader.get_property(ConfigConstants.SECTION_RDF_EXPORT, 'rdf.export.internal_subcatalog_template.filepath', '/mnt/gmv/sync/datosgobes_subcatalog.rdf')
        self._file_rdf_internal_subcatalog_template = None
        
        # Datasets and dataservices file
        self._filepath_datasets_dataservices = config_reader.get_property(ConfigConstants.SECTION_RDF_EXPORT,'rdf.export.datasets_dataservices.filepath', '/mnt/gmv/sync/datasets_dataservices.xml')
        self._file_datasets_and_dataservices = None
        
        # Metadata file: distributions, language...
        self._filepath_metadata = config_reader.get_property(ConfigConstants.SECTION_RDF_EXPORT,'rdf.export.metadata.filepath', '/mnt/gmv/sync/metadata.xml')
        self._file_metadata = None
        
        # Subtalogs file
        self._filepath_subcatalogs = config_reader.get_property(ConfigConstants.SECTION_RDF_EXPORT,'rdf.export.subcatalogs.filepath', '/mnt/gmv/sync/subcatalogs.xml')
        self._file_subcatalogs_rdf_template = None

        self._namespaces = RDFXmlParserConstants.DEFAULT_NAMESPACES
        self._available_organizations =  available_organizations or dge_harvest_organizations_available()
        self._used_organizations = {}

    def _write_line(self, file, line):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            file.write(line)
        except Exception as e:
            log.error(f'{method_log_prefix} Error writting line in file {file.name if file else "None"}, line {line}. Exception {type(e)}: {str(e)}')
            self._close_files()
        return file

    def _open_rdf_final_file(self):
        self._file_final_rdf = self._open_file(self._filepath_final_rdf, RDFXmlParserConstants.WRITE_MODE)

    def _open_rdf_root_catalog_template_file(self):
        self._file_rdf_root_catalog_template = self._open_file(self._filepath_rdf_root_catalog_template, RDFXmlParserConstants.READ_MODE)

    def _open_rdf_root_catalog_template_file_write_mode(self):
        self._file_rdf_root_catalog_template = self._open_file(self._filepath_rdf_root_catalog_template, RDFXmlParserConstants.WRITE_MODE)

    def _open_rdf_root_catalog_template_file_edit_mode(self):
        self._file_rdf_root_catalog_template = self._open_file(self._filepath_rdf_root_catalog_template, RDFXmlParserConstants.APPEND_MODE)

    def _open_rdf_internal_subcatalog_template_file(self):
        self._file_rdf_internal_subcatalog_template = self._open_file(self._filepath_rdf_internal_subcatalog_template, RDFXmlParserConstants.READ_MODE)

    def _open_rdf_internal_subcatalog_template_file_write_mode(self):
        self._file_rdf_internal_subcatalog_template = self._open_file(self._filepath_rdf_internal_subcatalog_template, RDFXmlParserConstants.WRITE_MODE)

    def _open_internal_subcatalog_template_file_edit_mode(self):
        self._file_rdf_internal_subcatalog_template = self._open_file(self._filepath_rdf_internal_subcatalog_template, RDFXmlParserConstants.APPEND_MODE)
    
    def _open_subcatalogs_file_write_mode(self):
        self._file_subcatalogs = self._open_file(self._filepath_subcatalogs, RDFXmlParserConstants.WRITE_MODE)

    def _open_subcatalogs_file_edit_mode(self):
        self._file_subcatalogs = self._open_file(self._filepath_subcatalogs, RDFXmlParserConstants.READ_WRITE_MODE)

    def _open_subcatalogs_file_append_mode(self):
        self._file_subcatalogs = self._open_file(self._filepath_subcatalogs, RDFXmlParserConstants.APPEND_MODE)

    def _open_datasets_and_dataservices_file_write_mode(self):
        self._file_datasets_and_dataservices = self._open_file(self._filepath_datasets_dataservices, RDFXmlParserConstants.WRITE_MODE)

    def _open_datasets_and_dataservices_file_edit_mode(self):
        self._file_datasets_and_dataservices = self._open_file(self._filepath_datasets_dataservices, RDFXmlParserConstants.READ_WRITE_MODE)

    def _open_datasets_and_dataservices_file_append_mode(self):
        self._file_datasets_and_dataservices = self._open_file(self._filepath_datasets_dataservices, RDFXmlParserConstants.APPEND_MODE)

    def _open_metadata_file_write_mode(self):
        self._file_metadata = self._open_file(self._filepath_metadata, RDFXmlParserConstants.WRITE_MODE)

    def _open_metadata_file_edit_mode(self):
        self._file_metadata = self._open_file(self._filepath_metadata, RDFXmlParserConstants.READ_WRITE_MODE)

    def _open_metadata_file_append_mode(self):
        self._file_metadata = self._open_file(self._filepath_metadata, RDFXmlParserConstants.APPEND_MODE)

    def _open_file(self, filepath, mode):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        file = None
        try:
            file = open(filepath, mode)
        except Exception as e:
            log.error(f'{method_log_prefix} Error opening file {filepath}: {str(e)}')
            self._close_files()
        return file

    @log_debug
    def _close_files(self):
        self._close_file(self._file_final_rdf)
        self._close_file(self._file_rdf_root_catalog_template)
        self._close_file(self._file_rdf_internal_subcatalog_template)
        self._close_file(self._file_datasets_and_dataservices)
        self._close_file(self._file_metadata)
        self._close_file(self._file_subcatalogs)

    def _close_file(self, file):
        if file and not file.closed:
            file.close()

    @log_debug
    def _clean_file(self, filepath):
        file = self._open_file(filepath, RDFXmlParserConstants.WRITE_MODE)
        self._close_file(file)

    @log_debug
    def _clean_files(self):
        self._clean_file(self._filepath_rdf_root_catalog_template)
        self._clean_file(self._filepath_rdf_internal_subcatalog_template)
        self._clean_file(self._filepath_datasets_dataservices)
        self._clean_file(self._filepath_metadata)
        self._clean_file(self._filepath_subcatalogs)

    ## Initialize data blocks files
    @log_debug
    def _initialize_subcatalogs_data_block(self):
        """
        Refactor rdf and take only subcatalogs and write them into self._filepath_subcatalogs.
        Warning this function overwrite the file.
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.debug(f'{method_log_prefix} Writting subcatalogs into {self._filepath_subcatalogs}' )
        self._open_subcatalogs_file_write_mode()
        self._initialize_template_file(self._file_subcatalogs)

    @log_debug
    def _initialize_datasets_and_dataservices_data_block(self):
        """
        Refactor rdf and take only datasets and dataservices and write them into self._filepath_datasets_dataservices.
        Warning this function overwrite the file.
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.debug(f'{method_log_prefix} Writting datasets into %s', self._filepath_datasets_dataservices)
        self._open_datasets_and_dataservices_file_write_mode()
        self._initialize_template_file(self._file_datasets_and_dataservices)

    @log_debug
    def _initialize_metadata_block(self):
        """
        Refactor rdf and take only metadata datasets and write them into self._filepath_metadata.
        Warning this function overwrite the file.
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.debug(f'{method_log_prefix} Writting metadata datasets into %s', self._filepath_metadata)
        self._open_metadata_file_write_mode()
        self._initialize_template_file(self._file_metadata)

    ### xml
    def _initialize_template_file(self, file):
        template_xml = self._get_template_xml()
        self._write_line( file, template_xml)
        self._close_file(file)

    def _get_template_xml(self):
        _root_datasets = ET.Element(RDFXmlParserConstants.ROOT_TAG)
        _root_datasets.append(ET.Element('TEMPLATE'))
        return self._refactor_xml_string_template(_root_datasets)

    def _refactor_xml_string_template(self, template):
        template_string = ET.tostring(template, encoding=RDFXmlParserConstants.ENCODING).decode(RDFXmlParserConstants.ENCODING)
        return template_string.replace(RDFXmlParserConstants.OPEN_ROOT_ELEMENT, RDFXmlParserConstants.OPEN_ROOT_ELEMENT + '\n').replace(RDFXmlParserConstants.OPEN_CLOSE_TEMPLATE_ELEMENT, RDFXmlParserConstants.OPEN_CLOSE_TEMPLATE_ELEMENT + '\n').replace(RDFXmlParserConstants.CLOSE_ROOT_ELEMENT, '')

    def _refactor_xml_string_xmlns(self, data):
        data_string = ET.tostring(data, encoding=RDFXmlParserConstants.ENCODING, xml_declaration=False).decode(RDFXmlParserConstants.ENCODING)
        return re.sub(RDFXmlParserConstants.XMLNS_REGEX, '', data_string)
    
    # namespaces
    def _get_namespaces(self):
        return self._namespaces

    def parse_namespace_and_element(self, uri):
        split_uri = urlsplit(uri)
        if split_uri.fragment: 
            namespace_uri, element_name = uri.rsplit("#", 1)
            namespace_uri += "#"
        else:
            namespace_uri, element_name = uri.rsplit("/", 1)
            namespace_uri += "/"
        return namespace_uri, element_name
    
    def generate_prefix(self, namespace_uri):
        prefix_candidate = namespace_uri.split("/")[-2] if "/" in namespace_uri else namespace_uri.split("#")[0]

        if not re.match(r'^[a-zA-Z_][\w.-]*$', prefix_candidate):
            prefix_candidate = f"ns_{prefix_candidate}"

        return prefix_candidate
    
    def add_namespace(self, prefix:str, namespace_uri:str):
        HTTP_SCHEMA = 'http://'
        HTTPS_SCHEMA = 'https://'

        if namespace_uri:
            namespace_uri = str(namespace_uri)
            http_namespace_uri = namespace_uri.replace(HTTPS_SCHEMA, HTTP_SCHEMA) if namespace_uri.startswith(HTTPS_SCHEMA) else namespace_uri
            https_namespace_uri = namespace_uri.replace(HTTP_SCHEMA, HTTPS_SCHEMA) if namespace_uri.startswith(HTTP_SCHEMA) else namespace_uri
            existent_prefix = self._get_prefix_from_namespace_uri(http_namespace_uri) or self._get_prefix_from_namespace_uri(https_namespace_uri)
            if not existent_prefix:
                if not prefix or prefix.startswith('ns'):
                    prefix = self.generate_prefix(namespace_uri)
                
                self._namespaces[prefix] = namespace_uri
                self._set_namespaces()
            else:
                prefix = existent_prefix
        return prefix, namespace_uri
    
    def _get_prefix_from_namespace_uri(self, namespace_uri):
            for prefix, uri in self._get_namespaces().items():
                if uri == namespace_uri:
                    return prefix 
            return None

    def _set_namespaces(self):
        for k, v in self._get_namespaces().items():
            try:
                ET.register_namespace(k, v)
            except Exception as e:
                log.error(f'Exception trying to register namespace {k}:{v}. Exception {type(e)}: {str(e)}')
                raise e
            
    ##################################
    ###      write_catalog_rdf     ###
    ##################################
    @log_debug
    def _set_close_tag_in_datasets_and_dataservices_files(self):
        self._open_subcatalogs_file_append_mode()
        self._write_line(self._file_subcatalogs,RDFXmlParserConstants.CLOSE_ROOT_ELEMENT + '\n')
        self._open_datasets_and_dataservices_file_append_mode()
        self._write_line(self._file_datasets_and_dataservices,RDFXmlParserConstants.CLOSE_ROOT_ELEMENT + '\n')
        self._open_metadata_file_append_mode()
        self._write_line(self._file_metadata,RDFXmlParserConstants.CLOSE_ROOT_ELEMENT + '\n')
        self._close_files()

    def _open_files_process_catalog(self):
        self._open_rdf_final_file()
        self._open_rdf_root_catalog_template_file()

    @log_debug
    def _write_catalog_in_file(self):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.debug(f'{method_log_prefix} Writting catalog in file {self._filepath_final_rdf}')
        for line in self._file_rdf_root_catalog_template:
            self._write_internal_subcatalogs_in_file_output(line)
            self._write_subcatalogs_in_file_output(line)
            self._write_datasets_and_dataservices_in_file_output(line)
            self._write_metadata_in_file_output(line)
            self._write_line(self._file_final_rdf, line)

    def _write_internal_subcatalogs_in_file_output(self, line):
        if RDFXmlParserConstants.CLOSE_RDF_ELEMENT in line:
            self._write_internal_subcatalogs_into_file()

    def _write_internal_subcatalogs_into_file(self):
        _filepath = self._filepath_rdf_internal_subcatalog_template
        if self._check_empty_file(_filepath):
            return
        try:
            for _, elem in ET.iterparse(_filepath):
                if RDFXmlParserConstants.CATALOG_TAG == elem.tag:
                    self._write_line(self._file_final_rdf, self._refactor_xml_string_xmlns(elem))
        except ET.ParseError as e:
            log.error(f'Error writing content of {_filepath}. {type(e)}:{e}')
            raise e

    def _write_subcatalogs_in_file_output(self, line):
        if RDFXmlParserConstants.CLOSE_RDF_ELEMENT in line:
            self._write_subcatalogs_into_file()

    def _write_subcatalogs_into_file(self):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        _filepath = self._filepath_subcatalogs
        if self._check_empty_file(_filepath):
            return
        try:
            for _, elem in ET.iterparse(_filepath):
                if RDFXmlParserConstants.CATALOG_TAG == elem.tag:
                    self._write_line(self._file_final_rdf, self._refactor_xml_string_xmlns(elem))
        except ET.ParseError as e:
            log.error(f'{method_log_prefix} Error writing content of {_filepath}. {type(e)}:{e}')
            raise e

    def _write_datasets_and_dataservices_in_file_output(self, line):
        if RDFXmlParserConstants.CLOSE_RDF_ELEMENT in line:
            self._write_datasets_and_dataservices_into_file()

    def _write_datasets_and_dataservices_into_file(self):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        _filepath = self._filepath_datasets_dataservices
        if self._check_empty_file(_filepath):
            return
        try:
            for _, elem in ET.iterparse(_filepath):
                if RDFXmlParserConstants.DATASET_TAG == elem.tag or RDFXmlParserConstants.DATASERVICE_TAG == elem.tag:
                    self._write_line(self._file_final_rdf, self._refactor_xml_string_xmlns(elem))
        except ET.ParseError as e:
            log.error(f'{method_log_prefix} Error writing datasets and dataservices content of {_filepath}. {type(e)}:{e}')
            raise e

    def _write_metadata_in_file_output(self, line):
        if RDFXmlParserConstants.CLOSE_RDF_ELEMENT in line:
            self._write_miscelaneous_metadata_into_file()

    def _write_miscelaneous_metadata_into_file(self):
        tree = ET.parse(self._filepath_metadata)
        root = tree.getroot()
        for elem in root:
            if RDFXmlParserConstants.TEMPLATE_TAG not in elem.tag and RDFXmlParserConstants.ROOT_TAG not in elem.tag:
                self._write_line(self._file_final_rdf,  self._refactor_xml_string_xmlns(elem))

    def _check_empty_file(self, filepath):
        empty_file = True
        if filepath:
            with open(filepath, RDFXmlParserConstants.READ_MODE) as file:
                content = file.read().strip()
                if content != '':
                    empty_file = False
        return empty_file
