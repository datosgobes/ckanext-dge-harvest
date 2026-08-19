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

import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    UnicodeText,
    UniqueConstraint,
)

from sqlalchemy.orm import backref, relationship

from ckan.model import meta
from ckanext.harvest.model import HarvestDomainObject, HarvestJob, make_uuid

from ckan.model import Session

try:
    from ckan.plugins.toolkit import BaseModel
except ImportError:
    # CKAN <= 2.9
    from ckan.model.meta import metadata
    from sqlalchemy.ext.declarative import declarative_base

    BaseModel = declarative_base(metadata=metadata)



class DgeHarvestJobExtra(BaseModel, HarvestDomainObject):
    """
    Modelo ORM para extras de harvest jobs en ckanext-dge-harvest.
    Sigue el patrón de HarvestObjectExtra de ckanext-harvest.
    """

    __tablename__ = "dge_harvest_job_extra"

    id = Column(UnicodeText, primary_key=True, default=make_uuid)
    harvest_job_id = Column(
        UnicodeText,
        ForeignKey("harvest_job.id", ondelete="CASCADE"),
        nullable=False,
    )
    key = Column(UnicodeText, nullable=False)
    value = Column(UnicodeText, nullable=True)
    created = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    job = relationship(
        HarvestJob,
        backref=backref("extras", cascade="all, delete-orphan"),
    )

    __table_args__ = (
        UniqueConstraint(
            "harvest_job_id",
            "key",
            name="uq_dge_harvest_job_extra_job_key",
        ),
        Index("ix_dge_harvest_job_extra_job", "harvest_job_id"),
    )

    def __repr__(self):
        return "<DgeHarvestJobExtra(id={}, job_id={}, key={})>".format(
            self.id, self.harvest_job_id, self.key
        )


dge_harvest_job_extra_table = DgeHarvestJobExtra.__table__


def upsert_job_extra(job_id, key, value):
    """
    Crea o actualiza un extra para un harvest_job.
    Añade el objeto a la sesión pero NO hace commit.
    """
    extra = Session.query(DgeHarvestJobExtra).filter_by(
        harvest_job_id=job_id,
        key=key,
    ).first()

    if extra:
        extra.value = value
    else:
        extra = DgeHarvestJobExtra(
            harvest_job_id=job_id,
            key=key,
            value=value,
        )
        Session.add(extra)
    
    return extra


def get_job_extra(job_id, key, default=None):
    """
    Recupera el valor de un extra específico por job_id y key.
    """
    extra = Session.query(DgeHarvestJobExtra).filter_by(
        harvest_job_id=job_id,
        key=key,
    ).first()

    return extra.value if extra else default
