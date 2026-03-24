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
# -*- coding: 850 -*-
# -*- coding: utf-8 -*-

import smtplib
import logging
import inspect
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import ckan.lib.helpers as h
import ckan.lib.mailer as mailer

from ckan.common import asbool, _
from ckan.plugins import toolkit
from ckan.plugins.toolkit import config
from ckan.logic import NotFound
from ckanext.harvest.logic.auth import user_is_sysadmin

from .export import csv_export_utils
from .export.rdf_export_generator import RDFExportGenerator
from .constants import CommonPackageConstants
from .decorators import log_info
from jinja2 import Environment, FileSystemLoader

log = logging.getLogger(__name__)

@toolkit.side_effect_free
@log_info
def dge_harvest_catalog_show(context, data_dict):
    rdf_export_generator = RDFExportGenerator(_get_dcat_ap_es_harvester_config_file(), False)
    return rdf_export_generator.dge_harvest_catalog_show_rdf(context, data_dict)

@log_info
def dge_harvest_catalog_show_edp(context, data_dict):
    rdf_export_generator = RDFExportGenerator(_get_dcat_ap_es_harvester_config_file(), True)
    return rdf_export_generator.dge_harvest_catalog_show_rdf(context, data_dict)

def _get_dcat_ap_es_harvester_config_file():
    property_prefix =  'ckanext.dge_harvest.dcat_ap_es_1_0_0.'
    return config.get(f'{property_prefix}config.filepath', '')

@log_info
def dge_harvest_catalog_show_csv(context, data_dict):
    return csv_export_utils.dge_harvest_catalog_show_csv(context, data_dict, _get_dcat_ap_es_harvester_config_file())


@log_info
def dge_harvest_package_show(context, data_dict):
    output = None
    toolkit.check_access('dge_harvest_package_show', context, data_dict)

    package_dict = toolkit.get_action('package_show')(context, data_dict)
    _format = data_dict.get('format')
    _package_type = package_dict.get('type', None)
    if _package_type in [CommonPackageConstants.KEY_TYPE_DATASET_VALUE, CommonPackageConstants.KEY_TYPE_DATASERVICE_VALUE]:
        if _format and _format == 'csv':
            output = csv_export_utils._dge_csv_serialize_packages([package_dict], None, _get_dcat_ap_es_harvester_config_file())
        else:
            rdf_export_generator = RDFExportGenerator(_get_dcat_ap_es_harvester_config_file(), False)
            output = rdf_export_generator.dge_harvest_package_show_rdf(package_dict, _format)
    return output

@log_info
def dge_harvest_clear_old_harvest_jobs(context, data_dict):
    '''
    Clears all finished jobs that have been created over one month ago of a harvest source
    except the last job by source if it has been created makes more than one month will be cleared.
    The datasets imported from the harvest source will NOT be deleted!!!
    :param id: the id of the harvest source to clear
    :type id: string
    '''
    method_log_prefix = f'[{__name__}][dge_harvest_clear_old_harvest_jobs]'
    log.debug(f'{method_log_prefix} Init method. Inputs context={context}, data_dict={data_dict}')
    toolkit.check_access('dge_harvest_clear_old_harvest_jobs', context, data_dict)

    harvest_source_id = data_dict.get('id', None)
    interval_value = config.get('ckanext.dge_harvest.clear_jobs.interval', '1 month')
    model = context['model']
    source_list = []
    sql = None
    if harvest_source_id:
        sql = '''select distinct hj.source_id, p.name from harvest_job hj,
                 package p where hj.source_id = p.id and p.type like 'harvest'
                 and source_id like '{source_id}';'''.format(source_id = harvest_source_id)
    else:
        sql = '''select distinct hj.source_id, p.name from harvest_job hj,
                 package p where hj.source_id = p.id and p.type like 'harvest';'''
    if sql:
        result = model.Session.execute(sql)
        if result:
            for row in result:
                source_id = row[0] if row else None
                if source_id:
                    source_list.append({'id': row[0], 'name': row[1] if row[1] else ''})

    if source_list:
        sql = '''begin;'''
        for item in source_list:
            hs_id = item.get('id', None)
            if hs_id:
                sql += '''
                    delete from harvest_object_error where harvest_object_id in (select id from harvest_object where current=false and harvest_job_id in (select id from harvest_job where status like 'Finished' and created <= (now() - interval '{interval_value}') and  source_id like '{harvest_source_id}' and id not in (select h.id from (select ROW_NUMBER() OVER (PARTITION BY hj.source_id order by hj.created desc) as rn, * from Harvest_job hj where source_id like '{harvest_source_id}') h where h.rn = 1 and h.created <= (now() - interval '{interval_value}') order by created desc) order by source_id desc, created desc));
                    delete from harvest_object_extra where harvest_object_id in (select id from harvest_object where current=false and harvest_job_id in (select id from harvest_job where status like 'Finished' and created <= (now() - interval '{interval_value}') and  source_id like '{harvest_source_id}' and id not in (select h.id from (select ROW_NUMBER() OVER (PARTITION BY hj.source_id order by hj.created desc) as rn, * from Harvest_job hj where source_id like '{harvest_source_id}') h where h.rn = 1 and h.created <= (now() - interval '{interval_value}') order by created desc) order by source_id desc, created desc));
                    delete from harvest_gather_error where harvest_job_id in (select id from harvest_job where status like 'Finished' and created <= (now() - interval '{interval_value}') and  source_id like '{harvest_source_id}' and id not in (select h.id from (select ROW_NUMBER() OVER (PARTITION BY hj.source_id order by hj.created desc) as rn, * from Harvest_job hj where source_id like '{harvest_source_id}') h where h.rn = 1 and h.created <= (now() - interval '{interval_value}') order by created desc) order by source_id desc, created desc);
                    delete from harvest_object where current=false and harvest_job_id in (select id from harvest_job where status like 'Finished' and created <= (now() - interval '{interval_value}') and  source_id like '{harvest_source_id}' and id not in (select h.id from (select ROW_NUMBER() OVER (PARTITION BY hj.source_id order by hj.created desc) as rn, * from Harvest_job hj where source_id like '{harvest_source_id}') h where h.rn = 1 and h.created <= (now() - interval '{interval_value}') order by created desc) order by source_id desc, created desc);
                    delete from harvest_job h_job where status like 'Finished' and created <= (now() - interval '{interval_value}') and source_id like '{harvest_source_id}' and id not in (select h.id from (select ROW_NUMBER() OVER (PARTITION BY hj.source_id order by hj.created desc) as rn, * from Harvest_job hj where source_id like '{harvest_source_id}') h where h.rn = 1 and h.created <= (now() - interval '{interval_value}') order by created desc) and not exists (select ho.id from harvest_object ho where ho.harvest_job_id = h_job.id and ho.current = true);
                    '''.format(harvest_source_id=hs_id, interval_value=interval_value)
        sql += '''commit;'''
        model.Session.execute(sql)
        for item in source_list:
            hs_id = item.get('id', None)
            if hs_id:
                toolkit.get_action('harvest_source_reindex')(context, {'id': hs_id})
        log.debug(f'{method_log_prefix} End method. Returns {source_list}')
        return source_list

def _dge_harvest_send_email(from_addr, to_addrs, msg):
    log.info(f"Sending email from {from_addr} to {to_addrs}")
    smtp_connection = smtplib.SMTP()
    if 'smtp.test_server' in config:
        smtp_server = config['smtp.test_server']
        smtp_starttls = False
        smtp_user = None
        smtp_password = None
    else:
        smtp_server = config.get('smtp.server', '')
        smtp_starttls = asbool(
                        config.get('smtp.starttls'))
        smtp_user = config.get('smtp.user')
        smtp_password = config.get('smtp.password')
    smtp_connection.connect(smtp_server)
    try:
        smtp_connection.ehlo()
        if smtp_starttls:
            if smtp_connection.has_extn('STARTTLS'):
                smtp_connection.starttls()
                smtp_connection.ehlo()
            else:
                raise mailer.MailerException("SMTP server does not support STARTTLS")

        if smtp_user:
            assert smtp_password, ("If smtp.user is configured then "
                    "smtp.password must be configured as well.")
            smtp_connection.login(smtp_user, smtp_password)

        smtp_connection.sendmail(from_addr, to_addrs, msg.as_string())
        log.info(f"Sent email from {from_addr} to {to_addrs}")

    except smtplib.SMTPException as e:
        msg = f'{e}'
        log.exception(msg)
        raise mailer.MailerException(msg)
    finally:
        smtp_connection.quit()

def dge_harvest_source_email_job_finished(context, data_dict):
    method_log_prefix = f'[{__name__}][dge_harvest_source_email_job_finished]'
    log.debug(f'{method_log_prefix} Init method. Inputs context={context}, data_dict={data_dict}')
    toolkit.check_access('dge_harvest_source_email_job_finished', context, data_dict)
    model = context['model']
    source_id = data_dict.get('source_id')
    job_id = data_dict.get('job_id')
    pkg = model.Package.get(source_id)
    if pkg is None:
        raise NotFound
    org = model.Group.get(pkg.owner_org)
    if org is None:
        raise NotFound
    source_status_dict = toolkit.get_action('harvest_source_show_status')(context, {'id': source_id})
    last_job = source_status_dict.get('last_job', None)
    members = toolkit.get_action('member_list')(
                        context, {'id': pkg.owner_org, 'object_type': 'user', 'capacity': 'editor'})
    if members is None:
        raise NotFound

    #To
    mail_to = []
    for member in members:
        user = model.User.get(member[0])
        if user and user.state == 'active' and user.email and len(user.email) > 0:
            mail_to.append(user.email)

    #From
    mail_from = config.get('smtp.mail_from', None)

    #CC
    mail_ccs = config.get('smtp.mail_cc', '').split(' ')

    #Reply-To
    mail_reply_to = config.get('smtp.mail_reply_to', None)

    #Subject
    subject = f"Finalizada federaci\u00F3n con {config.get('ckan.site_title', 'datos.gob.es')}"
    
    #Template
    path = config.get('ckanext.dge_harvest.template.path_emails')
    url = config.get('ckanext.comments.url.images.drupal')
    url_logos = config.get('ckanext.comments.url.image.logos')
    url_image_subscribe = config.get('ckanext.comments.url.image.subscribe')
    url_subscribe = config.get('ckanext.comments.url.subscribe')

    #Body
    url_job = config.get('ckan.site_url') + "/harvest/" + pkg.name + "/job/" + job_id
    url_job = url_job.replace("http://", "https://")
    env = Environment(loader=FileSystemLoader(path))
    job_finished_template = env.get_template('harvest_job_finished.html')
    body = job_finished_template.render(
        url=url,
        url_logos=url_logos,
        url_image_subscribe=url_image_subscribe,
        url_subscribe=url_subscribe,
        org_title=org.title,
        last_job=last_job,
        url_job=url_job,
        job_id=job_id,
        h=h
    )
    msg = MIMEText(body, 'html')
    
    if mail_from:
        msg['From'] = mail_from
    if mail_reply_to:
        msg['Reply-To'] = mail_reply_to
    if mail_to and len(mail_to) > 0:
        msg['To'] = ", ".join(mail_to)
    if mail_ccs and len(mail_ccs) > 0:
        msg['Cc'] = ", ".join(mail_ccs)
    msg['Subject'] = subject
    try:
        _dge_harvest_send_email(msg['From'], (mail_to + mail_ccs), msg)
    except mailer.MailerException as e:
        msg = f'{e}'
        log.exception(f'{method_log_prefix} Exception sending email.')
    finally:
        log.debug(f'{method_log_prefix} End method.')

def dge_harvest_get_running_harvest_jobs(context, data_dict):
    '''
    Gets running jobs that more than {minutes} minutes ago and send and email
    :param minutes: the number of minutes. 1440 minutes (24 hours) by default.
    :type minutes: int
    '''
    try:
        method_log_prefix = f'[{__name__}][dge_harvest_get_running_harvest_jobs]'
        log.debug(f'{method_log_prefix} Init method. Inputs context={context}, data_dict={data_dict}')
        toolkit.check_access('dge_harvest_get_running_harvest_jobs', context, data_dict)

        try:
            minutes = int(data_dict.get('minutes', 1440))
        except Exception:
            minutes = 1440

        if minutes == 1:
            interval_value = '1 minute'
        else:
            interval_value = f'{minutes} minutes'

        model = context['model']
        harvest_job_list = []
        sql = '''select p.name, p.title, hj.id, hj.created, hj.gather_started,
                 hj.gather_finished, hj.finished
                 from harvest_job hj, package p
                 where hj.status like 'Running'
                 and hj.created <= (now() at time zone 'utc' - interval '{interval_value}')
                 and hj.source_id = p.id order by created desc;
                 '''.format(interval_value=interval_value)
        result = model.Session.execute(sql)
        if result:
            for row in result:
                job_id = row[2] if row else None
                if job_id:
                    harvest_job_list.append({'source_name': row[0] if row[0] else '',
                                             'source_title': row[1] if row[1] else '',
                                             'job_id': row[2] if row[2] else '',
                                             'created': row[3] if row[3] else '',
                                             'gather_started': row[4] if row[4] else '',
                                             'gather_finished': row[5] if row[5] else '',
                                             'finished': row[6] if row[6] else ''
                                            })

        if harvest_job_list and len(harvest_job_list) > 0:

            #From
            mail_from = config.get('smtp.mail_from', None)

            #To
            mail_to = config.get('smtp.mail_cc', '').split(' ')

            #Reply-To
            mail_reply_to = config.get('smtp.mail_reply_to', None)

            #Subject
            subject = "Federaciones en estado 'Running'"
            
            #Template
            path = config.get('ckanext.dge_harvest.template.path_emails')
            url = config.get('ckanext.comments.url.images.drupal')
            url_logos = config.get('ckanext.comments.url.image.logos')
            url_image_subscribe = config.get('ckanext.comments.url.image.subscribe')
            url_subscribe = config.get('ckanext.comments.url.subscribe')

            #Body
            env = Environment(loader=FileSystemLoader(path))
            jobs_720_template = env.get_template('harvest_jobs_720.html')
            body = jobs_720_template.render(
                url=url,
                url_logos=url_logos,
                url_image_subscribe=url_image_subscribe,
                url_subscribe=url_subscribe,
                harvest_job_list=harvest_job_list,
                h=h
            )
            msg = MIMEText(body, 'html')
            
            if mail_from:
                msg['From'] = mail_from
            if mail_reply_to:
                msg['Reply-To'] = mail_reply_to
            if mail_to and len(mail_to) > 0:
                msg['To'] = ", ".join(mail_to)
            msg['Subject'] = subject
            try:
                _dge_harvest_send_email(msg['From'], mail_to, msg)
            except mailer.MailerException as e:
                log.exception(f'{method_log_prefix} Exception sending email. {e}')
            finally:
                log.debug(f'{method_log_prefix} End method.')
    except Exception as e:
        log.exception(f'{method_log_prefix} Exception: {e}.')
        print(f'{method_log_prefix} Exception: {e}.')
    finally:
        log.debug(f'{method_log_prefix} End method.')
    return harvest_job_list

############### AUTHORIZATION ###################

@toolkit.auth_allow_anonymous_access
def dge_harvest_auth(context, data_dict):
    '''
    All users can access DCAT endpoints by default
    '''
    return {'success': True}

def dge_harvest_is_sysadmin(context, data_dict):
    '''
        Only sysadmins can do it
    '''
    if not user_is_sysadmin(context):
        return {'success': False, 'msg': 'Only sysadmins can do this operation'}
    else:
        return {'success': True}
