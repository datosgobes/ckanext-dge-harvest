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
"""Harvest job finish orchestration for the federation report extension.

This module separates the responsibilities executed when a harvest job is
closed: first consolidate or inspect the report state, then trigger
notifications. The current report model is materialized incrementally while
messages are persisted, so consolidation is intentionally lightweight, but the
hook is kept explicit for future close-time tasks.
"""

from ckan.plugins import toolkit

from ckanext.dge_harvest.services.report.harvest_report_query import (
    resolve_report_mode,
)


def finalize_harvest_report_for_job(job_id, session=None):
    """Resolve the final report mode for one finished job.

    The current report implementation updates structured rows incrementally
    during harvesting, so this step does not rebuild materialized data. It
    still exists as an explicit close-time boundary so future tasks can attach
    end-of-job consolidation without coupling it to notification flow.

    Args:
        job_id (str): Harvest job identifier.
        session: Optional SQLAlchemy session override.

    Returns:
        dict: Minimal consolidation result with the resolved report mode.
    """
    return {
        "job_id": job_id,
        "mode": resolve_report_mode(job_id, session=session),
    }


def notify_harvest_job_finished(
    context, source_id, job_id, action_getter=None
):
    """Trigger the existing organization notification for one finished job.

    Args:
        context (dict): CKAN action context.
        source_id (str): Harvest source identifier.
        job_id (str): Harvest job identifier.
        action_getter: Optional injected action resolver for tests.

    Returns:
        Any: Result returned by the notification action.
    """
    action_resolver = action_getter or toolkit.get_action
    return action_resolver("dge_harvest_source_email_job_finished")(
        context,
        {"source_id": source_id, "job_id": job_id},
    )


def run_harvest_job_finished_hook(
    context, source_id, job_id, session=None, action_getter=None
):
    """Run the harvest job finish hook in deterministic order.

    Args:
        context (dict): CKAN action context.
        source_id (str): Harvest source identifier.
        job_id (str): Harvest job identifier.
        session: Optional SQLAlchemy session override.
        action_getter: Optional injected action resolver for tests.

    Returns:
        dict: Hook result including consolidation metadata.
    """
    consolidation = finalize_harvest_report_for_job(job_id, session=session)
    notify_harvest_job_finished(
        context=context,
        source_id=source_id,
        job_id=job_id,
        action_getter=action_getter,
    )
    return consolidation
