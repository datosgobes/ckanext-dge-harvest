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

# coding=utf-8
import logging
import inspect
from typing import List
from ckan.plugins.toolkit import config
import xml.etree.ElementTree as ET
from ..constants.dcat_ap_es_constants import RDF, FOAF, DCT, DCAT
from ..constants import DCATAPESConfigConstants as ConfigConstants, DCATAPESPrefixConstants
from .rdf_xml_parser_base import RDFXmlParserBase, RDFXmlParserConstants
from ..harvester_config_reader import HarvesterConfigReader
from rdflib import Graph, URIRef, Literal
from ..decorators import log_debug, log_info
log = logging.getLogger(__name__)

"""
    rdf: string in rdf format getting from serialized a block of catalogs, datasets and dataservices and their metadata
"""
class RDFXmlParser(RDFXmlParserBase):
    @log_info
    def __init__(self, filepath_rdf_root_catalog:str, config_reader:HarvesterConfigReader, template:str, available_organizations: dict[str, List[str]] = None):
        super().__init__(filepath_rdf_root_catalog, config_reader, available_organizations)
        self._clean_files()
        self._initialize_subcatalogs_data_block()
        self._initialize_datasets_and_dataservices_data_block()
        self._initialize_metadata_block()
        self._initialize_root_catalog_rdf_template(template)
        self.default_datasets_per_page = int(config.get('ckanext.dcat.datasets_per_page', ConfigConstants.DATASETS_PER_PAGE))
        self._datasets_size = 0
        self._dataservices_size = 0
        self._subcatalogs_size = 0
        self._subcatalogs_of_main_catalog = set() # subcatalogs included in main catalog as dct:haPart


    @log_info
    def write_catalog_rdf(self):    
        """
        Write catalog in _filepath_rdf getting the information from _filepath_datasets_dataservices and _filepath_miscelaneous_metadata.
        Use the first block of datasets generated as template: _filepath_rdf_template.
        """
        self._append_organization_metadata()
        self._complete_namespaces_and_subcatalogs()
        self._set_close_tag_in_datasets_and_dataservices_files()
        self._open_files_process_catalog()
        self._write_catalog_in_file()
        self._close_files()

    @log_debug
    def _complete_namespaces_and_subcatalogs(self):
        """
        Complete rdf_file_template with namespaces used in all subcatalgos and subcatalogs
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        _filepath = self._filepath_rdf_root_catalog_template
        log.debug(f'{method_log_prefix} Complete namespaces and subcatalogs in {_filepath}')
        # Get existing namespaces in file
        existing_namespaces = {}
        for _, elem in ET.iterparse(_filepath, events=("start-ns",)):
            prefix, uri = elem
            existing_namespaces[prefix] = uri

        # Parse file to add namespaces and subcaatlog
        _tree = ET.parse(_filepath)
        _root = _tree.getroot()

        # Add additional namespaces
        for prefix, uri in self._get_namespaces().items():
            if prefix not in existing_namespaces or existing_namespaces[prefix] != uri:
                _root.set(f"xmlns:{prefix}", uri)
            ET.register_namespace(prefix, uri)

        ## Get catalog and add subcatalogs as dct:hasPart
        catalog = _root.find(RDFXmlParserConstants.CATALOG_TAG_NAMESPACE,self._get_namespaces())
        for subcatalog_uri in self._subcatalogs_of_main_catalog:
            ET.SubElement(catalog, RDFXmlParserConstants.DCT_HAS_PART_ATTRIB_KEY, {RDFXmlParserConstants.RDF_RESOURCE_ATTRIB_KEY: f"{subcatalog_uri}"})
        ET.indent(_root)
        _tree.write(file_or_filename=_filepath, encoding="utf-8", xml_declaration=True)

    @log_info
    def append_subcatalog(self, rdf, subcatalog_uri):
        """
        Refactor rdf and take only subcatalogs and append a block of datasets into self._filepath_metadata.
        """
        self._subcatalogs_of_main_catalog.add(subcatalog_uri)
        subcatalog = rdf
        if isinstance(rdf, str):
            subcatalog = self.replace_rdf_description_and_adjust_namespaces(RDFXmlParserConstants.RDF_RESOURCE_ATTRIB_KEY)
        elif isinstance(rdf, bytes):
            subcatalog = self.replace_rdf_description_and_adjust_namespaces(rdf.decode(RDFXmlParserConstants.ENCODING)) 
        self._append_subcatalogs_data_block_file(subcatalog)
        self._append_datasets_and_dataservices_data_block_file(subcatalog)
        self._append_metadata_data_block_file(subcatalog)
        self._close_files()

    @log_info
    def append_datasets_and_dataservices(self, rdf):
        """
        Refactor rdf and take only datasets and dataservices and append a block of datasets into self._filepath_metadata.
        """
        processed_rdf = self.replace_rdf_description_and_adjust_namespaces(rdf)
        self._append_datasets_and_dataservices_references_to_internal_catalog_template(processed_rdf)
        self._append_datasets_and_dataservices_data_block_file(processed_rdf)
        self._append_metadata_data_block_file(processed_rdf)
        self._close_files()

    @log_debug
    def _initialize_root_catalog_rdf_template(self, catalog):
        """
        Write catalog in _filepath_rdf_template.
        """
        processed_catalog = self._process_catalog_rdf(catalog)
        self._open_rdf_root_catalog_template_file_write_mode()       
        self._write_line(self._file_rdf_root_catalog_template, processed_catalog)
        self._close_files()

    @log_info
    def initialize_internal_subcatalog_rdf_template(self, catalog, catalog_uri):
        """
        Write catalog in _filepath_rdf_template.
        """
        self._subcatalogs_of_main_catalog.add(catalog_uri)
        processed_catalog = self._process_catalog_rdf(catalog)
        self._open_rdf_internal_subcatalog_template_file_write_mode()
        self._write_line(self._file_rdf_internal_subcatalog_template, processed_catalog)
        self._close_files()
        self._subcatalogs_size += 1

    @log_debug
    def _process_catalog_rdf(self, catalog):
        """
        Write catalog in _filepath_rdf_template)
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        modified_catalog = catalog
        if isinstance(catalog, bytes):
            catalog = catalog.decode(RDFXmlParserConstants.ENCODING)
        modified_catalog = self.replace_rdf_description_and_adjust_namespaces(catalog)
        _root_element = ET.fromstring(modified_catalog)
        # Append metadata to metadata block
        metadata_elements_rdf_about_value = self._append_metadata_data_block_file(modified_catalog, True)
        # Deleted from rdf elements added to metadata_block
        for rdf_about_value in metadata_elements_rdf_about_value or []:
            try:
                element = _root_element.find(f".//*[@rdf:about='{rdf_about_value}']", self._namespaces)
                _root_element.remove(element) 
            except ValueError as e:
                log.warn(f'{method_log_prefix} Error removing element with rdf_about = {rdf_about_value}. Exception {type(e)}: {str(e)}')
        processed_catalog = ET.tostring(_root_element).decode(RDFXmlParserConstants.ENCODING)
        return processed_catalog

    #####################################
    ### append_subcatalogs_data_block ###
    #####################################
    @log_debug
    def _append_subcatalogs_data_block_file(self,  rdf):
        self._open_subcatalogs_file_append_mode()
        self._append_subcatalogs_to_file(rdf)
        self._close_files()

    @log_debug
    def _append_subcatalogs_to_file(self, rdf):
        _root_element = ET.fromstring(rdf)
        for catalog in _root_element.findall(RDFXmlParserConstants.CATALOG_TAG_NAMESPACE,self._get_namespaces()):
            self._write_line(self._file_subcatalogs, ET.tostring(catalog).decode(RDFXmlParserConstants.ENCODING))
            self._subcatalogs_size += 1

    @log_debug
    def _append_referenced_elements_to_internal_subcatalog_template(self, element_list):
        _tree = ET.parse(self._filepath_rdf_internal_subcatalog_template)
        _root = _tree.getroot()
        catalog = _root.find(RDFXmlParserConstants.CATALOG_TAG_NAMESPACE,self._get_namespaces())
        if catalog:
            for element in element_list:
                catalog.append(element)
        ET.indent(_root)
        _tree.write(self._filepath_rdf_internal_subcatalog_template, encoding="utf-8", xml_declaration=True)
        self._close_file(self._file_rdf_internal_subcatalog_template)

    ###################################################
    ### append_datasets_and_dataservices_data_block ###
    ###################################################
    @log_debug
    def _append_datasets_and_dataservices_references_to_internal_catalog_template(self, rdf):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.debug(f'{method_log_prefix} Appending datasets and dataservices references to file {self._filepath_rdf_internal_subcatalog_template}')
        _root_element = ET.fromstring(rdf)
        # datasets
        datasets_references_to_add = set()
        for dataset_reference in _root_element.findall(f'.//{RDFXmlParserConstants.DATASET_REFERENCE_TAG_NAMESPACE}',self._get_namespaces()):
            datasets_references_to_add.add(dataset_reference)
        self._append_referenced_elements_to_internal_subcatalog_template(datasets_references_to_add)
        # dataservices
        dataservices_references_to_add = set()
        for dataservice_reference in _root_element.findall(f'.//{RDFXmlParserConstants.DATASERVICE_REFERENCE_TAG_NAMESPACE}',self._get_namespaces()):
            dataservices_references_to_add.add(dataservice_reference) # datasets
        self._append_referenced_elements_to_internal_subcatalog_template(dataservices_references_to_add)
        record_references_to_add = set()
        for record_reference in _root_element.findall(f'.//{RDFXmlParserConstants.CATALOG_RECORD_REFERENCE_TAG_NAMESPACE}',self._get_namespaces()):
            record_references_to_add.add(record_reference)
        self._append_referenced_elements_to_internal_subcatalog_template(record_references_to_add)

    @log_debug
    def _append_datasets_and_dataservices_data_block_file(self,  rdf):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.debug(f'{method_log_prefix} Appending datasets and dataservices to file {self._file_datasets_and_dataservices}')
        self._open_datasets_and_dataservices_file_append_mode()
        self._append_datasets_and_dataservices_to_file(rdf)
        self._close_files()

    @log_debug
    def _append_datasets_and_dataservices_to_file(self, rdf):
        _root_element = ET.fromstring(rdf)
        # append datasets
        for dataset in _root_element.findall(RDFXmlParserConstants.DATASET_TAG_NAMESPACE,self._get_namespaces()):
            self._write_line(self._file_datasets_and_dataservices, ET.tostring(dataset).decode(RDFXmlParserConstants.ENCODING))
            self._datasets_size += 1
        # append dataservices
        for dataservice in _root_element.findall(RDFXmlParserConstants.DATASERVICE_TAG_NAMESPACE,self._get_namespaces()):
            self._write_line(self._file_datasets_and_dataservices, ET.tostring(dataservice).decode(RDFXmlParserConstants.ENCODING))
            self._dataservices_size += 1

    ##################################
    ### append_metadata_data_block ###
    ##################################
    @log_debug
    def _append_metadata_data_block_file(self, rdf, return_metadata_elements_rdf_about_value=False):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.debug(f'{method_log_prefix} Appending metadata to file {self._file_metadata}')
        self._open_metadata_file_append_mode()
        metadata_elements = self._append_metadata_to_file(rdf, return_metadata_elements_rdf_about_value)
        self._close_files()
        return metadata_elements

    def _check_if_append_to_medatada_file(self, metatada_tag):
        return (RDFXmlParserConstants.CATALOG_TAG != metatada_tag and 
                RDFXmlParserConstants.DATASET_TAG != metatada_tag and 
                RDFXmlParserConstants.DATASERVICE_TAG != metatada_tag)

    def check_if_is_an_available_organization(self, metadata_attrib_rdf_about):
        '''
        Check if metadata_attrib_rdf_about is the uri of a datos.gob.es organization
        and add it to _used_organization dictionary
        '''
        is_an_available_organization = False
        if metadata_attrib_rdf_about.startswith(DCATAPESPrefixConstants.PUBLISHER_PREFIX):
            splitted_upper_organization_uri = metadata_attrib_rdf_about.upper().split('/')
            organization_minhap = splitted_upper_organization_uri[-1] if splitted_upper_organization_uri and len(splitted_upper_organization_uri) > 0 else None
            if organization_minhap not in self._used_organizations.keys():
                available_organization = self._available_organizations.get(organization_minhap, None)
                available_organization_name = available_organization[1] if available_organization and len(available_organization) > 1 else None
                if available_organization_name:
                    is_an_available_organization = True
                    self._used_organizations.setdefault(organization_minhap, available_organization_name)
            else:
                is_an_available_organization = True
        return is_an_available_organization

    @log_debug
    def _append_metadata_to_file(self, rdf, return_metadata_elements_rdf_about_value=False):
        _root_element = ET.fromstring(rdf)
        metadata_elements_rdf_about_value = [] if return_metadata_elements_rdf_about_value else None
        for metadata in _root_element:  
            if self._check_if_append_to_medatada_file(metadata.tag):
                metadata_attrib_rdf_about = metadata.attrib.get(RDFXmlParserConstants.RDF_ABOUT_ATTRIB_KEY, None) if metadata.attrib else None
                if (metadata_elements_rdf_about_value is not None and 
                    metadata_attrib_rdf_about is not None):
                    metadata_elements_rdf_about_value.append(metadata_attrib_rdf_about)
                if not self.check_if_is_an_available_organization(metadata_attrib_rdf_about):
                    self._write_line(self._file_metadata, ET.tostring(metadata).decode(RDFXmlParserConstants.ENCODING))
        return metadata_elements_rdf_about_value

    @log_debug
    def _append_organization_metadata(self):
        '''
        Adds the datos.gob information of the organisms used to the metadata file 
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.debug(f'{method_log_prefix} Appending metadata to file {self._file_metadata}')
        log.debug(f'{method_log_prefix} _used_organizations = {self._used_organizations}')
        if self._used_organizations:
            org_graph = Graph()
            for organization_minhap, organization_name in self._used_organizations.items() or []:
                organization_uri = URIRef(f'{DCATAPESPrefixConstants.PUBLISHER_PREFIX}{organization_minhap}')
                org_graph.add((organization_uri, RDF.type, FOAF.Agent))
                org_graph.add((organization_uri, FOAF.name, Literal(organization_name, lang=config.get(ConfigConstants.CKAN_PROP_LOCALE_DEFAULT, 'es'))))
                org_graph.add((organization_uri, DCT.identifier, Literal(organization_minhap)))
            rdf = org_graph.serialize(format='xml')
            self._open_metadata_file_append_mode()
            _root_element = ET.fromstring(self.replace_rdf_description_and_adjust_namespaces(rdf))
            for metadata in _root_element:  
                self._write_line(self._file_metadata, ET.tostring(metadata).decode(RDFXmlParserConstants.ENCODING))
        self._close_files()

    @log_debug
    def replace_rdf_description_and_adjust_namespaces(self, xml_content:str):
        '''
        Modify an RDF/XML by replacing rdf:Description and adjusting the namespaces.
        
        :param xml_content: content to update
        :type xml_content:str
        
        :return Tupla with xml_content without rdf:Description nodes and adjunted namespaces
        '''
        # parse XML from a string into an Element
        if not xml_content:
            return xml_content
        root = ET.fromstring(xml_content)
        namespaces = self._get_namespaces() or {}
        # Register prefix to use
        for prefix, namespace_uri in namespaces.items():
            ET.register_namespace(prefix, namespace_uri)
        replacements = []
        # Replace rdf:Description with RDF type
        self._replace_rdf_description(root, namespaces, replacements)
        # Replace the node in the ET
        for description_element, new_element in replacements or []:
            # Find parent root of description element
            parent = next(elem for elem in root.iter() if description_element in list(elem))
            parent.remove(description_element)
            parent.append(new_element)
        ET.indent(root)
        # Serialize the new RDF/XML 
        transformed_rdf = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
        return transformed_rdf
    
    def _replace_rdf_description(self, root, namespaces, replacements):
        PREFIX_RDF = "rdf"
        PATH_RDF_DESCRIPTION = f"{PREFIX_RDF}:Description"
        PATH_RDF_TYPE = f"{PREFIX_RDF}:type"
        for description in root.findall(PATH_RDF_DESCRIPTION, namespaces):
            resource_attr = f"{{{namespaces[PREFIX_RDF]}}}resource"
            # a node can have multiple types, not just one
            rdf_types = description.findall(PATH_RDF_TYPE, namespaces)
            if not rdf_types:
                continue
            num_types = len(rdf_types)
            main_rdf_type = self._get_main_rdf_type_in_node_description(rdf_types, resource_attr)

            if main_rdf_type is not None and resource_attr in main_rdf_type.attrib:
                new_type_uri = main_rdf_type.attrib[resource_attr]
                namespace_uri, element_name = self.parse_namespace_and_element(new_type_uri)
                prefix, namespace_uri = self.add_namespace(None, namespace_uri)
                ET.register_namespace(prefix, namespace_uri)
                # Create a new node
                new_element = ET.Element(f"{{{namespace_uri}}}{element_name}")
                new_element.attrib = description.attrib  # Copy attribs as rdf:about
                # Copy children nodes to new node
                self._copy_children_in_new_element(new_element, description, resource_attr, num_types, new_type_uri, f"{{{namespaces[PREFIX_RDF]}}}type")
                replacements.append((description, new_element))  

    def _get_main_rdf_type_in_node_description(self, rdf_types, resource_attr):
        main_rdf_type = None
        if not rdf_types:
            return
        main_rdf_type = rdf_types[0]
        num_types = len(rdf_types)
        if num_types > 1:
            for rdf_type in rdf_types:
                if rdf_type is not None and resource_attr in rdf_type.attrib:
                    new_type_uri = rdf_type.attrib[resource_attr]
                    # The following types are prioritized: DCAT.Dataset, DCAT.Distribution and DCAT.Dataservice
                    if (new_type_uri == str(DCAT.Dataset) or 
                        new_type_uri == str(DCAT.Distribution) or
                        new_type_uri == str(DCAT.DataService)):
                        main_rdf_type = rdf_type
                        break
        return main_rdf_type

    def _copy_children_in_new_element(self, new_element, description, resource_attr, num_types, new_type_uri, rdf_type_tag):
        for child in description:
            child_resource_attr_value = child.attrib[resource_attr] if child.attrib and resource_attr in child.attrib else None
            add_child = False
            if num_types == 1:
                # Skip rdf:type
                add_child = child.tag != rdf_type_tag 
            elif num_types > 1:
                # Skip rdf:type only if it is the same type of the new element type
                add_child = (child.tag != rdf_type_tag or 
                             (child.tag == rdf_type_tag and child_resource_attr_value and child_resource_attr_value != new_type_uri))
            if add_child:
                new_element.append(child)

    def get_resume(self):
        return f"""The number of elements writing in final export file has been:
            - Number of root catalogs = 1
            - Number of subcatalogs in root catalog = {len(self._subcatalogs_of_main_catalog)}
            - Number of subcatalogs in other subcatalogs = {self._subcatalogs_size - len(self._subcatalogs_of_main_catalog)}
            - Total number of datasets = {self._datasets_size}
            - Total number of dataservices = {self._dataservices_size}"""
