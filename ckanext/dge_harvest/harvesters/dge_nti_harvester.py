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

import json
import logging
import hashlib
import uuid
import inspect

import ckan.logic as logic
import ckan.model as model
import ckan.plugins as p

from ckanext.dcat.processors import RDFParserException
from ckanext.harvest.model import HarvestObject

from .dge_harvester import DGERDFHarvester
from ..processors import DGENTIRDFParser
from ..constants.nti_constants import NTICatalogConstants, NTIHarvesterConstants, NTIDatasetConstants
from ..decorators import log_debug, log_info

log = logging.getLogger(__name__)

class DGENTIRDFHarvester(DGERDFHarvester):

    def info(self):
        return {
            'name': 'dge_rdf',
            'title': 'dge_rdf',
            'description': 'Harvester for DGE datasets from an RDF graph'
        }

    @log_info
    def gather_stage(self, harvest_job):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        
        if harvest_job.gather_finished is not None:
            log.info('%s End method 0. The gathering stage took more than 2 hours, and the harvest job was renewed before it was finished. Returns: []' % (method_log_prefix))
            return []

        # Refreshing source info
        model.Session.refresh(harvest_job.source)

        # Get rdf_format and default_catalog_language in source_config
        rdf_format, default_catalog_language = self._get_rdf_format_config(harvest_job.source.config)

        # Get file contents of first page
        next_page_url = harvest_job.source.url
        log.info(f'{method_log_prefix} Init harvest for harvest_source with url {next_page_url}')

        guids_in_source = []
        object_ids = []
        last_content_hash = None
        self._names_taken = []
        visited_urls = set()
        while next_page_url is not None and next_page_url not in visited_urls:
            next_page_url = self._run_before_downloads(harvest_job, next_page_url)
            if not next_page_url:
                log.debug(f'{method_log_prefix} End method 1. Returns: []')
                return []
                
            content, rdf_format = self._get_content_and_type(next_page_url, harvest_job, 1, content_type=rdf_format)

            content_hash = hashlib.md5()
            if content:
                content_hash.update(content.encode('utf8'))

            if last_content_hash:
                if content_hash.digest() == last_content_hash.digest():
                    log.warning('Remote content was the same even when using a paginated URL, skipping')
                    break
            else:
                last_content_hash = content_hash

            content = self._run_after_downloads(harvest_job, content, next_page_url)
            if not content:
                log.debug(f'{method_log_prefix} End method 2. Returns: []')
                return []

            parser = DGENTIRDFParser(profiles=['dge_nti_profile'])
            try:
                parser.parse(content, _format=rdf_format)
            except RDFParserException as e:
                gather_error = self._set_error_message(NTIHarvesterConstants.CATALOG_PARSER_ERROR, NTIHarvesterConstants.CATALOG_PARSER_ERROR_URL, e, next_page_url)
                self._save_gather_error(gather_error, harvest_job)
                log.debug(f'{method_log_prefix}'.format(content))
                log.debug(f'{method_log_prefix} End method 3. Returns: []')
                return []
            except Exception as e:
                gather_error = self._set_error_message(NTIHarvesterConstants.CATALOG_PARSER_ERROR, NTIHarvesterConstants.CATALOG_PARSER_ERROR_URL, e, next_page_url)
                self._save_gather_error(gather_error, harvest_job)
                log.debug(f'{method_log_prefix} End method 4. Returns: []')
                return []

            parser = self._run_after_parsings(harvest_job, parser, next_page_url)
            if parser is None:
                log.debug(f'{method_log_prefix} End method 5. Returns: []')
                return []

            catalog_errors = 0
            catalog_warnings = 0
            catalog_uri = None

            try:
                for catalog in parser.catalogs():
                    catalog_errors = catalog[NTICatalogConstants.KEY_CATALOG_ERRORS]
                    catalog_warnings = catalog[NTICatalogConstants.KEY_CATALOG_WARNINGS]
                    catalog_uri = catalog.get(NTICatalogConstants.KEY_CATALOG_URI, None)

                    owner_org_catalog = None
                    source_catalog = model.Package.get(harvest_job.source.id)
                    if source_catalog.owner_org:
                        owner_org_catalog = source_catalog.owner_org

                    # check if catalog_publisher is harvest_source_org
                    if catalog.get(NTICatalogConstants.KEY_CATALOG_PUBLISHER) and \
                            catalog.get(NTICatalogConstants.KEY_CATALOG_PUBLISHER) != owner_org_catalog:
                        if not catalog_errors:
                            catalog_errors = []
                        errormsg = NTIHarvesterConstants.UNEXPECTED_PUBLISHER_CATALOG_OWNER_SOURCE
                        log.info(f"{method_log_prefix} Adding catalog error {errormsg}")
                        catalog_errors.append(errormsg)

                    total_catalog_errors = len(catalog_errors) if catalog_errors else 0
                    total_catalog_warnings = len(catalog_warnings) if catalog_warnings else 0

                    if catalog_warnings and len(catalog_warnings) > 0:
                        num = 0
                        for catalog_warning in catalog_warnings:
                            num += 1
                            if (num <= DGERDFHarvester.MAX_NUM):
                                warnmsg = NTIHarvesterConstants.CATALOG_VALIDATION_WARNING.format(catalog_warning)
                                if next_page_url:
                                    warnmsg = NTIHarvesterConstants.CATALOG_VALIDATION_WARNING_URL.format(next_page_url, catalog_warning)
                                log.info(f"{method_log_prefix} Saving gather_error - {warnmsg} {harvest_job}")
                                self._save_gather_error(warnmsg, harvest_job)

                    if catalog_errors and len(catalog_errors) > 0:
                        num = 0
                        for catalog_error in catalog_errors:
                            num += 1
                            if (num <= DGERDFHarvester.MAX_NUM):
                                errormsg = NTIHarvesterConstants.CATALOG_VALIDATION_ERRORS.format(catalog_error)
                                if next_page_url:
                                    errormsg = NTIHarvesterConstants.CATALOG_VALIDATION_ERRORS_URL.format(next_page_url, catalog_error)
                                log.info(f"{method_log_prefix} Saving gather_error - {errormsg} {harvest_job}")
                                self._save_gather_error(errormsg, harvest_job)
                        # Summary
                        summarymsg = NTIHarvesterConstants.LOG_CATALOG_ERROR_SUMMARY.format(catalog_uri or 'Not URIRef', total_catalog_warnings, total_catalog_errors)
                        log.info(f"{method_log_prefix} {summarymsg}")
                        log.debug(f'{method_log_prefix} End method 6. Returns: False')
                        return False
                    else:
                        error_dataset_identifier = ""
                        total_datasets = 0
                        total_error_datasets = 0
                        total_errors = 0
                        total_warnings = 0
                        try:
                            dict = {}
                            dict[NTICatalogConstants.KEY_CATALOG_LANGUAGE] = catalog[NTICatalogConstants.KEY_CATALOG_LANGUAGE]
                            dict[NTIDatasetConstants.KEY_DATASET_DEFAULT_CATALOG_LANGUAGE] = default_catalog_language
                            dict[NTICatalogConstants.KEY_CATALOG_THEME_TAXONOMY] = catalog[NTICatalogConstants.KEY_CATALOG_THEME_TAXONOMY]
                            dict[NTICatalogConstants.KEY_CATALOG_URI] = catalog[NTICatalogConstants.KEY_CATALOG_URI]
                            dict[NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA] = catalog[NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA]
																						
                            for dataset in parser.datasets(dict):
																		   
                                total_datasets += 1

                                # Unless already set by the parser, get the owner organization (if any)
                                # from the harvest source dataset
                                if not dataset.get(NTIDatasetConstants.KEY_OWNER_ORG):
                                    if owner_org_catalog:
                                        dataset[NTIDatasetConstants.KEY_OWNER_ORG] = owner_org_catalog

                                if not dataset.get(NTIDatasetConstants.KEY_NAME) \
                                        and dataset.get(NTIDatasetConstants.KEY_TITLE) \
                                        and dataset.get(NTIDatasetConstants.KEY_PUBLISHER_ID_MINHAP):
                                    dataset[NTIDatasetConstants.KEY_NAME] = self._gen_new_name(
                                        dataset.get(NTIDatasetConstants.KEY_PUBLISHER_ID_MINHAP, '') + '-' + dataset.get(NTIDatasetConstants.KEY_TITLE, ''))

                                # Try to get a unique identifier for the harvested dataset
                                guid = self._get_guid(dataset)
                                if not guid:
                                    log.error(f'{method_log_prefix} Could not get a unique identifier for dataset: {dataset}')
                                    continue

                                dataset[NTIDatasetConstants.KEY_EXTRAS].append({'key': 'guid', 'value': guid})
                                guids_in_source.append(guid)

                                # delete unnecesary info
                                errors = dataset.pop(NTIDatasetConstants.KEY_ERRORS, [])
                                warnings= dataset.pop(NTIDatasetConstants.KEY_WARNINGS, [])
                                dataset.pop(NTICatalogConstants.KEY_CATALOG_AVAILABLE_DATA, None)

                                if guid or dataset.get(NTIDatasetConstants.KEY_NAME):
                                    error_dataset_identifier = guid if guid else dataset.get(NTIDatasetConstants.KEY_NAME)

                                if errors and len(errors) > 0:
                                    total_errors = total_errors + len(errors)
                                    log.debug(f"{method_log_prefix} errors number={len(errors)}")
                                if warnings and len(warnings) > 0:
                                    total_warnings = total_warnings + len(warnings)
                                    log.debug(f"{method_log_prefix} warnings number={len(warnings)}")

                                if errors and len(errors) > 0:
                                    obj = HarvestObject(guid=guid, job=harvest_job, state='ERROR',
                                                        content=json.dumps(dataset))
                                    obj.save()
                                    total_error_datasets += 1
                                    num = 0
                                    for error in errors:
                                        num += 1
                                        if (num <= DGERDFHarvester.MAX_NUM):
                                            log.info(f"{method_log_prefix} Saving objectError {error} for guid {guid}")
                                            errormessage = NTIHarvesterConstants.DATASET_VALIDATION_ERROR.format(error)
                                            self._save_object_error(errormessage, obj, 'Gather')
                                else:
                                    obj = HarvestObject(guid=guid, job=harvest_job,
                                                        content=json.dumps(dataset), )

                                    obj.save()
                                    object_ids.append(obj.id)

                                if warnings and len(warnings) > 0:
                                    num = 0
                                    for warn in warnings:
                                        num += 1
                                        if (num <= DGERDFHarvester.MAX_NUM):
                                            log.info(f"{method_log_prefix} Saving warning in objectError {warn} for guid {guid}")
                                            warnmessage = NTIHarvesterConstants.DATASET_VALIDATION_WARNING.format(warn)
                                            self._save_object_error(warnmessage, obj, 'Gather')
										
                            # Summary
                            summarymsg = NTIHarvesterConstants.LOG_SUMMARY.format(
                                total_catalog_warnings, total_datasets, total_error_datasets, total_errors,
                                total_warnings)
                            log.info(f"{method_log_prefix} {summarymsg}")
                        except RDFParserException as e:
                            errormsg = NTIHarvesterConstants.DATASET_VALIDATION_ERROR.format(type(e).__name__, e)
                            log.info(f"{method_log_prefix} Saving gather_error - {errormsg}")
                            self._save_gather_error(errormsg, harvest_job)
                            # Summary
                            summarymsg = NTIHarvesterConstants.LOG_SUMMARY.format(
                                total_catalog_warnings, total_datasets, (total_error_datasets + 1), total_errors,
                                total_warnings)
                            log.info(f"{method_log_prefix} {summarymsg}")
                            log.debug(f'{method_log_prefix} End method 7. Returns: False')
                            return []
            except RDFParserException as e:
                errormsg = NTIHarvesterConstants.CATALOG_VALIDATION_ERROR.format(type(e).__name__, e)
                if next_page_url:
                    errormsg = NTIHarvesterConstants.CATALOG_VALIDATION_ERROR_URL.format(next_page_url, type(e).__name__, e)
                log.info(f"{method_log_prefix} Saving gather_error - {errormsg}")
                self._save_gather_error(errormsg, harvest_job)
                # Summary
                summarymsg = NTIHarvesterConstants.LOG_CATALOG_ERROR_SUMMARY.format(catalog_uri or 'Not URIRef', total_catalog_warnings, (total_catalog_errors + 1))
                log.info(f"{method_log_prefix} {summarymsg}")
                log.debug(f'{method_log_prefix} End method 8. Returns: False')
                return False
            
            # Add the current URL to the visited set
            visited_urls.add(next_page_url)
            # Get the next URL
            next_page_url = parser.next_page()
            log.debug(f'{method_log_prefix} Getting next page URL: {next_page_url}')

        # Check if some datasets need to be deleted
        object_ids_to_delete = self._mark_datasets_for_deletion(guids_in_source, harvest_job)
        log.debug(f'object_ids_to_delete={object_ids_to_delete}')
        log.debug(f'object_ids={object_ids}')
        object_ids.extend(object_ids_to_delete)
        log.debug(f'{method_log_prefix} content={content}')
        log.debug(f'{method_log_prefix} End method 9. Returns: {object_ids}')
        return object_ids

    def fetch_stage(self, harvest_object):
        # Nothing to do here
        return True

    @log_info
    def import_stage(self, harvest_object):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        harvest_object_id = ''
        harvest_object_guid = ''
        try:
            harvest_object_id = harvest_object.id
            harvest_object_guid = harvest_object.guid
            status = self._get_object_extra(harvest_object, 'status')
            if status == 'delete':
                # Delete package
                return self._delete_package(harvest_object)

            if harvest_object.content is None:
                error = 'Empty content for object {0}'.format(harvest_object.id)
                log.info(f"{method_log_prefix} Saving objectError {error} for harvest_object_guid {harvest_object_guid}")
                self._save_object_error(NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(error), harvest_object, 'Import')
                return False
            try:
                dataset = json.loads(harvest_object.content)
            except ValueError:
                error = 'Could not parse content for object {0}'.format(harvest_object.id)
                log.info(f"{method_log_prefix} Saving objectError {error} for harvest_object_guid {harvest_object_guid}")
                self._save_object_error(NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(error), harvest_object, 'Import')
                return False
            # Get the last harvested object (if any)
            previous_object = model.Session.query(HarvestObject) \
                .filter(HarvestObject.guid == harvest_object.guid) \
                .filter(HarvestObject.current == True) \
                .first()

            # Flag previous object as not current anymore
            if previous_object:
                previous_object.current = False
                previous_object.add()

            # Flag this object as the current one
            harvest_object.current = True
            harvest_object.add()

            context = {
                'user': self._get_user_name(),
                'return_id_only': True,
                'ignore_auth': True,
            }

            # Check if a dataset with the same guid exists
            existing_dataset =self._get_existing_package_by_guid(context, harvest_object.guid)

            if existing_dataset:
                # Don't change the dataset name even if the title has
                dataset[NTIDatasetConstants.KEY_NAME] = existing_dataset[NTIDatasetConstants.KEY_NAME]
                dataset[NTIDatasetConstants.KEY_ID] = existing_dataset[NTIDatasetConstants.KEY_ID]
                if (existing_dataset[NTIDatasetConstants.KEY_STATE] == 'deleted'):
                    log.info(f'{method_log_prefix} Reactivating deleted package with id {existing_dataset[NTIDatasetConstants.KEY_ID]}')
                    dataset[NTIDatasetConstants.KEY_STATE] = 'active'

                # Save reference to the package on the object
                harvest_object.package_id = dataset[NTIDatasetConstants.KEY_ID]
                harvest_object.add()

                try:
                    p.toolkit.get_action('package_update')(context, dataset)
                except p.toolkit.ValidationError as e:
                    error = NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(str(e.error_summary))
                    log.debug(f"{method_log_prefix} Saving objectError {error} for harvest_object_guid {harvest_object_guid}")
                    self._save_object_error(error, harvest_object, 'Import')
                    return False

                log.info(f'{method_log_prefix} Updated dataset {dataset.get(NTIDatasetConstants.KEY_NAME)}')

            else:
                package_schema = logic.schema.default_create_package_schema()
                context['schema'] = package_schema

                # We need to explicitly provide a package ID
                dataset[NTIDatasetConstants.KEY_ID] = str(uuid.uuid4())
                package_schema['id'] = [str]

                # Save reference to the package on the object
                harvest_object.package_id = dataset[NTIDatasetConstants.KEY_ID]
                harvest_object.add()

                # Defer constraints and flush so the dataset can be indexed with
                # the harvest object id (on the after_show hook from the harvester
                # plugin)
                model.Session.execute('SET CONSTRAINTS harvest_object_package_id_fkey DEFERRED')
                model.Session.flush()

                try:
                    p.toolkit.get_action('package_create')(context, dataset)
                except p.toolkit.ValidationError as e:
                    error = NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(str(e.error_summary))
                    log.info(f"{method_log_prefix} Saving objectError {error} for harvest_object_guid {harvest_object_guid}")
                    self._save_object_error(error, harvest_object, 'Import')
                    return False

                log.info(f'{method_log_prefix} Created dataset {dataset.get(NTIDatasetConstants.KEY_NAME)}')
            model.Session.commit()
        except Exception as e:
            errormsg = f'{str(e)}'
            try:
                errormsg = f"Exception in harvest_object {harvest_object_guid} ({harvest_object_id}) {type(e).__name__}: {str(e)}"
                log.error(f"{method_log_prefix} {errormsg}")
                if 'IntegrityError' == type(e).__name__:
                    errormsg = NTIHarvesterConstants.DATASET_INTEGRITY_ERROR
                self._save_object_error(NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(errormsg), harvest_object, 'Import')
            except Exception as ex:
                log.error(f"{method_log_prefix} Exception {type(ex)}. {str(ex)}")
                harvest_object.package_id = None
                self._save_object_error(NTIHarvesterConstants.DATASET_IMPORT_ERROR.format(errormsg), harvest_object, 'Import')
            return False
        return True

