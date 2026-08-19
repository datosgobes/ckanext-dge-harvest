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

import os
import inspect
import rdflib
import ckan.model as model
import ckan.plugins as p
import ckan.plugins.toolkit as toolkit
import json
import logging
import requests

from ckan.plugins.toolkit import config as pc
from ckantoolkit import config

from ckanext.dcat.harvesters.rdf import DCATRDFHarvester
from ckanext.dcat.interfaces import IDCATRDFHarvester
from ckanext.harvest.helpers import get_harvest_source
from ckanext.harvest.model import HarvestJob
from .dge_harvester_exceptions import (
    GatherConnectionError,
    GatherFileNotFoundError,
    GatherFileTooLargeError,
    GatherHTTPError,
    GatherHookError,
    GatherRdfFormatConfigError,
    GatherSoftLimitInfo,
    GatherStageResult,
    GatherTimeoutError,
    PrepareGatherContextError,
)
from ..constants.constants import ConfigConstants, CommonPackageConstants, DatasetConstants, HarvesterConstants
from ..decorators import log_debug, log_info
from ckanext.dge_harvest.model.dge_harvest_job_extra import upsert_job_extra

log = logging.getLogger(__name__)

class DGERDFHarvester(DCATRDFHarvester):
    DEFAULT_SOFT_LIMIT_FILE_SIZE_MB = 50 # 50 Mb
    CHUNK_SIZE = 1024 * 512

    MAX_NUM = 20
    force_import = False

    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    def _has_job_been_aborted(self, harvest_job):
        """Return whether the current harvest job has already been finished.

        Renewed or externally aborted jobs can reach gather workers after the
        owning queue entry is no longer valid. In that situation gather should
        stop early and, when appropriate, persist an informational message.
        """
        job_status = (
            model.Session.query(HarvestJob.status)
            .filter(HarvestJob.id == harvest_job.id)
            .scalar()
        )
        return job_status == 'Finished'

    def _get_local_content_and_type(self, url, harvest_job, content_type=None):
        # Check local file
        if os.path.exists(url):
            with open(url, 'r') as f:
                content = f.read()
            content_type = content_type or rdflib.util.guess_format(url)
            return content, content_type, GatherStageResult()
        else:
            message = f'No se ha podido acceder al fichero de federación. Comprueba que la URL configurada en la fuente de federación es correcta y accesible. URL configurada: {url}'
            raise GatherFileNotFoundError(
                display_message = message,
                raw_message = message,
            )


    @log_info
    def _prepare_gather_context(self, harvest_job):
        """Freeze the minimum gather context and return it as a dictionary.

        The helper persists the effective source URL, source type, source
        config and, when available, the owner organization linked to the
        source. It commits those values immediately because later report
        retrieval must not depend on mutable harvest source state.

        Args:
            harvest_job: Running harvest job whose context is being frozen.

        Returns:
            dict[str, object]: Frozen context with at least these keys:
                ``effective_url``, ``source_type``, ``source_config`` and
                ``source_owner_org``.

        Raises:
            PrepareGatherContextError: If the critical source context cannot be
                read or persisted.
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)

        try:
            model.Session.refresh(harvest_job.source)
            effective_url = harvest_job.source.url
            source_type = harvest_job.source.type
            source_config = harvest_job.source.config
        except Exception as exc:
            raise PrepareGatherContextError(
                'Could not read source context for harvest job {}: {}'.format(
                    harvest_job.id,
                    exc,
                )
            ) from exc

        source_owner_org = None
        try:
            harvest_source = get_harvest_source(harvest_job.source.id)
            if harvest_source:
                source_owner_org = harvest_source.get('owner_org', None)
        except Exception as exc:
            log.warning(
                '%s Could not resolve source owner organization for harvest job %s: %s',
                method_log_prefix,
                harvest_job.id,
                exc,
                exc_info=True
            )

        try:
            upsert_job_extra(
                harvest_job.id,
                HarvesterConstants.SOURCE_URL_AT_RUN,
                effective_url
            )
            upsert_job_extra(
                harvest_job.id,
                HarvesterConstants.SOURCE_TYPE_AT_RUN,
                source_type,
            )
            upsert_job_extra(
                harvest_job.id,
                HarvesterConstants.SOURCE_CONFIG_AT_RUN,
                source_config,
            )
            if source_owner_org:
                upsert_job_extra(
                    harvest_job.id,
                    HarvesterConstants.SOURCE_OWNER_ORG_AT_RUN,
                    source_owner_org,
                )
            model.Session.commit()
            log.info(
                f'{method_log_prefix} Gather context frozen. '
                f'{HarvesterConstants.SOURCE_URL_AT_RUN}={effective_url}; '
                f'{HarvesterConstants.SOURCE_TYPE_AT_RUN}={source_type}; '
                f'{HarvesterConstants.SOURCE_CONFIG_AT_RUN}={source_config}; '
                f'{HarvesterConstants.SOURCE_OWNER_ORG_AT_RUN}={source_owner_org}'
            )
        except Exception as exc:
            model.Session.rollback()
            raise PrepareGatherContextError(
                '{} Could not persist gather context for harvest job {}: {}'.format(
                    method_log_prefix,
                    harvest_job.id,
                    exc,
                )
            ) from exc

        return {
            HarvesterConstants.SOURCE_URL_AT_RUN: effective_url,
            HarvesterConstants.SOURCE_TYPE_AT_RUN: source_type,
            HarvesterConstants.SOURCE_CONFIG_AT_RUN: source_config,
            HarvesterConstants.SOURCE_OWNER_ORG_AT_RUN: source_owner_org,
        }

    def _get_proxies(self):
        method_log_prefix = f'[{type(self).__name__}][_get_proxies]'
        http_proxy = pc.get(ConfigConstants.CKAN_PROP_HTTP_PROXY, None)
        https_proxy = pc.get(ConfigConstants.CKAN_PROP_HTTPS_PROXY, None)
        proxies = None
        if http_proxy or https_proxy:
            proxies = {}
            if http_proxy:
                proxies['http'] = http_proxy
            if https_proxy:
                proxies['https'] = https_proxy
            log.debug(f"{method_log_prefix} Using proxies {proxies}")
        else:
            log.debug(f"{method_log_prefix} No proxies")
        return proxies

    @log_debug
    def _get_content_and_type(self, url, harvest_job, page=1, content_type=None):
        '''
        Gets the content and type of the given url.

        :param url: a web url (starting with http) or a local path
        :param harvest_job: the job, used for error reporting
        :param page: adds paging to the url
        :param content_type: will be returned as type
        :return: a tuple containing the content and content-type
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        if not url.lower().startswith('http'):
            return self._get_local_content_and_type(url, harvest_job, content_type)

        warn_messages = []

        try:
            if page > 1:
                url = url + '&' if '?' in url else url + '?'
                url = url + 'page={0}'.format(page)

            proxies = self._get_proxies()

            log.debug(f'{method_log_prefix} Getting file {url}')

            # get the `requests` session object
            session = requests.Session()
            for harvester in p.PluginImplementations(IDCATRDFHarvester):
                session = harvester.update_session(session)

            did_get = False
            r = session.head(url, proxies=proxies, verify=False)
            log.debug('Response {}'.format(r))
            if r.status_code in HarvesterConstants.FAILED_REQUESTS_HEAD_STATUS_CODES_FOR_REQUESTS_GET:
                log.debug("HEAD request failed with status code 400, 403, 404 or 405. Attempting GET request")
                log.debug(f"{method_log_prefix} Status code response = {r.status_code}")
                r = session.get(url, proxies=proxies, stream=True, verify=False)
                did_get = True
            r.raise_for_status()

            max_file_size_mb = toolkit.asint(config.get('ckanext.dcat.max_file_size', self.DEFAULT_MAX_FILE_SIZE_MB))
            max_file_size = 1024 * 1024 * max_file_size_mb
            cl = r.headers.get('content-length')
            log.debug(f'{cl}')
            if cl and int(cl) > max_file_size:
                cl_mb = int(cl) / 1024 / 1024
                message = f'El fichero de federación {url} supera el tamaño máximo permitido. tamaño máximo permitido: {max_file_size_mb} MB. tamaño del fichero recibido: {cl_mb} MB.'
                raise GatherFileTooLargeError(
                    display_message = message,
                    raw_message= message,
                    context={
                        "url": url,
                        "content_length": cl,
                        "max_file_size": max_file_size,
                    },
                )

            # Check whether the soft limit has been exceeded
            soft_limit_file_size_mb = toolkit.asint(config.get('ckanext.dge_harvest.soft_limit_file_size', self.DEFAULT_SOFT_LIMIT_FILE_SIZE_MB))
            soft_limit_file_size = 1024 * 1024 * soft_limit_file_size_mb
            if cl and int(cl) > soft_limit_file_size:
                message = f'El fichero de federación {url} supera el umbral de tamaño recomendado ({soft_limit_file_size_mb} MB). Se recomienda paginar o dividir el contenido para garantizar el correcto procesamiento de futuras federaciones.'
                warn_messages.append(
                    GatherSoftLimitInfo(
                        display_message = message,
                        raw_message=message,
                        context={
                            "url": url,
                            "content_length": cl,
                            "soft_limit_file_size": soft_limit_file_size,
                        },
                    )
                )

            if not did_get:
                r = session.get(url, proxies=proxies, stream=True, verify=False)

            length = 0
            content = b''
            for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                content = content + chunk
                length += len(chunk)

                if length >= max_file_size:
                    length_mb = length / 1024 / 1024
                    message = f'El fichero de federación {url} supera el tamaño máximo permitido. Tamaño máximo permitido: {max_file_size_mb} MB. tamaño del fichero recibido: {length_mb} MB.'
                    raise GatherFileTooLargeError(
                        display_message = message,
                        raw_message=message,
                        context={"url": url, "content_length": length, "max_file_size": max_file_size},
                    )
            content = content.decode('utf-8')

            if content_type is None and r.headers.get('content-type'):
                content_type = r.headers.get('content-type').split(";", 1)[0]

            return content, content_type, GatherStageResult(warnings=warn_messages)

        except requests.exceptions.HTTPError as error:
            if page > 1 and error.response.status_code == 404:
                # We want to catch these ones later on
                raise

            message = f'No se ha podido descargar el fichero de federación. El servidor remoto ha respondido con el error {error.response.status_code} {error.response.reason}.'
            raise GatherHTTPError(
                display_message = message,
                raw_message=message,
                context={
                    "url": url,
                    "status_code": error.response.status_code,
                    "reason": error.response.reason,
                },
            ) from error
        except requests.exceptions.ConnectionError as error:

            message = "No se ha podido acceder al fichero de federación debido a un problema de conexión con el servidor remoto."
            raise GatherConnectionError(
                display_message = message,
                raw_message=f'{message} Detalle: {error}.',
                context={"url": url, "exception_message": str(error)},
            ) from error
        except requests.exceptions.Timeout as error:
            message='No se ha podido acceder al fichero de federación porque el servidor remoto ha superado el tiempo de espera permitido.',
            raise GatherTimeoutError(
                display_message = message,
                raw_message=f'{message} Detalle: {error}.',
                context={"url": url, "exception_message": str(error)},
            ) from error

    @log_debug
    def _get_rdf_format_config(self, config_str):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        rdf_format = None
        default_catalog_language = None
        if config_str:
            try:
                config = json.loads(config_str)
            except (TypeError, ValueError) as exc:
                raise GatherRdfFormatConfigError(
                    display_message = "No se ha podido transformar el fichero al formato indicado. Comprueba que en la fuente de federación el formato configurado es es esperado.",
                    raw_message= f'Could not parse source config for RDF format: {str(exc)}',
                    kind = "rdf_format_config_error",
                    context= {"config_str": config_str, "exception_message": str(exc)}
                ) from exc
            rdf_format = config.get(ConfigConstants.HS_PROP_RDF_FORMAT, None)
            default_catalog_language = config.get(ConfigConstants.HS_PROP_DEFULT_CATALOG_LANGUAGE, None)
        return rdf_format, default_catalog_language

    def _normalize_url(self, url):
        from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
        from collections import OrderedDict
        
        if not url:
            return url
        
        try:
            parsed = urlparse(url.strip())
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            

            if scheme == 'http' and netloc.endswith(':80'):
                netloc = netloc[:-3]
            elif scheme == 'https' and netloc.endswith(':443'):
                netloc = netloc[:-4]
            

            path = parsed.path
            if path and path != '/' and path.endswith('/'):
                path = path[:-1]
            

            query = ''
            if parsed.query:
                params = parse_qsl(parsed.query, keep_blank_values=True)
                unique_params = OrderedDict()
                for key, value in params:
                    if key not in unique_params:
                        unique_params[key] = value
                sorted_params = sorted(unique_params.items(), key=lambda x: x[0])
                query = urlencode(sorted_params, doseq=False)
            

            return urlunparse((scheme, netloc, path, parsed.params, query, ''))
            
        except Exception as e:
            log.info(f'Error while normalize url {url}. Exception {type(e).__name__}: {e.message}. Return url without normalize')
            return url

    def validate_config(self, source_config):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        if not source_config:
            return source_config
        try:
            source_config_obj = json.loads(source_config)
            
          
            if 'url' in source_config_obj and 'full_rdf_url' not in source_config_obj:
                source_config_obj['full_rdf_url'] = source_config_obj.pop('url')
            

            if source_config_obj.get('full_rdf_url'):
                source_config_obj['full_rdf_url'] = self._normalize_url(source_config_obj['full_rdf_url'])
            

            if ConfigConstants.HS_PROP_DEFULT_CATALOG_LANGUAGE in source_config_obj:
                default_catalog_language = source_config_obj.get(ConfigConstants.HS_PROP_DEFULT_CATALOG_LANGUAGE)
                locals_offered = pc.get(ConfigConstants.CKAN_PROP_LOCALES_OFFERED, '').split()
                if default_catalog_language not in locals_offered:
                    raise ValueError(f'{ConfigConstants.HS_PROP_DEFULT_CATALOG_LANGUAGE} must be a value of {locals_offered}')
            super(DGERDFHarvester, self).validate_config(json.dumps(source_config_obj))
            

            source_config = json.dumps(source_config_obj, sort_keys=True, separators=(',', ':'))
            
        except ValueError as e:
            log.exception(f'{method_log_prefix} Exception {type(e).__name__}: {e.message}')
            raise e
        return source_config

    def _replace_https_with_http(self, value):
        return value.replace('https://', 'http://') if value else value

    @log_debug
    def _get_guid(self, data_dict, source_url=None):
        '''
        Try to get a unique identifier for a harvested dataset or dataservice

        It will be the first found of:
         * publisher_id_minhap + URI (rdf:about)
         * Dataset name
         * URI (rdf:about)
         * dct:identifier

        if it is not a dataset, type of element will be added to guid

        The last two are obviously not optimal, as depend on title, which
        might change.

        Returns None if no guid could be decided.
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        guid = None
        type_value = data_dict.get(CommonPackageConstants.KEY_TYPE, None)
        _type = f'{type_value}-' if type_value and type_value != CommonPackageConstants.KEY_TYPE_DATASET_VALUE else ''

        publisher_id_minhap = data_dict.get(CommonPackageConstants.KEY_PUBLISHER_ID_MINHAP) + '-' if data_dict.get(CommonPackageConstants.KEY_PUBLISHER_ID_MINHAP) else ''
        guid = (
            self._get_dict_value(data_dict, CommonPackageConstants.KEY_URI) or
            self._get_dict_value(data_dict, DatasetConstants.KEY_DATASET_IDENTIFIER)
        )
        if guid:
            guid = _type + publisher_id_minhap + self._replace_https_with_http(guid)

        if not guid and data_dict.get(CommonPackageConstants.KEY_NAME):
            guid = _type + data_dict[CommonPackageConstants.KEY_NAME]
            if source_url:
                guid = self._replace_https_with_http(source_url).rstrip('/') + '/' + guid
        return guid

    def _set_error_message(self, error_message, error_message_url, error_message_value, next_page_url):
        error_msg = error_message.format(error_message_value)
        if next_page_url and error_message_url:
            error_msg = error_message_url.format(next_page_url, error_message_value)
        return error_msg

    @log_debug
    def _run_before_downloads(self, harvest_job, next_page_url):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        for harvester in p.PluginImplementations(IDCATRDFHarvester):
            log.debug(f'{method_log_prefix} harvester: {harvester}')
            next_page_url, before_download_errors = harvester.before_download(next_page_url, harvest_job)

            if before_download_errors:
                raise GatherHookError(
                    display_message = f"No se ha podido descargar el catálogo de federación desde {next_page_url}.",
                    raw_message=(
                        "No se ha podido descargar el catálogo de federación desde {next_page_url}."
                        + " | ".join(before_download_errors)
                    ),
                    kind="run_before_downloads",
                    context={
                        "url": next_page_url,
                        "errors": before_download_errors,
                    },
                )

            if not next_page_url:
                break
        return next_page_url

    @log_debug
    def _run_after_downloads(self, harvest_job,content, next_page_url):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        for harvester in p.PluginImplementations(IDCATRDFHarvester):
            log.debug(f'{method_log_prefix} harvester: {harvester}')
            content, after_download_errors = harvester.after_download(content, harvest_job)

            if after_download_errors:
                raise GatherHookError(
                    display_message = f"No se ha podido descargar el catálogo de federación desde {next_page_url}.",
                    raw_message=(
                        "No se ha podido descargar el catálogo de federación."
                        + " | ".join(after_download_errors)
                    ),
                    kind="run_after_downloads",
                    context={
                        "url": next_page_url,
                        "errors": after_download_errors,
                    },
                )

            if not content:
                break
        return content

    @log_debug
    def _run_after_parsings(self, harvest_job, parser, next_page_url):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)

        for harvester in p.PluginImplementations(IDCATRDFHarvester):
            log.debug(f'{method_log_prefix} harvester: {harvester}')
            parser, after_parsing_errors = harvester.after_parsing(parser, harvest_job)

            if after_parsing_errors:
                raise GatherHookError(
                    display_message = f"No se ha podido parsear el catálogo de federación desde {next_page_url}.",
                    raw_message=(
                        "No se ha podido parsear el catálogo de federación."
                        + " | ".join(after_parsing_errors)
                    ),
                    kind="run_after_parsings",
                    context={
                        "url": next_page_url,
                        "errors": after_parsing_errors,
                    },
                )
            if not parser:
                return None
        log.debug(f'{method_log_prefix} End method. Returns: {parser}')
        return parser

    @log_debug
    def _delete_package(self, harvest_object):
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        log.debug(f'{method_log_prefix}. Harvest_object with id = {harvest_object.id}; guid= {harvest_object.guid}; package_id={harvest_object.package_id}')
        context = {'model': model, 'session': model.Session,
                   'user': self._get_user_name(), 'ignore_auth': True}

        p.toolkit.get_action('package_delete')(context, {'id': harvest_object.package_id})
        log.info(f'{method_log_prefix} Deleted package {harvest_object.package_id} with guid {harvest_object.guid}')
        return True

    @log_debug
    def _read_packages_in_any_state_from_db(self, guid):
        '''
        Returns a database result of datasets matching the given guid.
        '''
        datasets = model.Session.query(model.Package.id) \
                                .join(model.PackageExtra) \
                                .filter(model.PackageExtra.key == 'guid') \
                                .filter(model.PackageExtra.value == guid) \
                                .order_by(model.Package.metadata_modified.desc()) \
                                .all()
        return datasets

    @log_debug
    def _get_existing_package_by_guid(self, context, guid):
        '''
        Checks if a dataset with a certain guid extra already exists in an active or deleted package.

        Returns a dict as the ones returned by package_show. Active dataset if founded dataset was deleted.
        '''
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        datasets = self._read_packages_in_any_state_from_db(guid)

        if not datasets:
            return None
        elif len(datasets) > 1:
            log.error(f'{method_log_prefix} Found more than one dataset with the same guid: {guid}')

        return p.toolkit.get_action('package_show')(context or {}, {'id': datasets[0][0]})
