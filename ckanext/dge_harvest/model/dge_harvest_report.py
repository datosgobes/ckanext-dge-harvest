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

"""ORM models for the structured harvest report.

This module exposes the canonical message table and the materialized row used
by the new report together with ORM-level normalization for the internal
payload fields.
"""

import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UnicodeText,
    UniqueConstraint,
)
from sqlalchemy.orm import backref, relationship, validates

from ckanext.harvest.model import (
    HarvestDomainObject,
    HarvestJob,
    HarvestObject,
    make_uuid,
)
from ckanext.dge_harvest.services.report.harvest_report_payload import (
    normalize_details_json,
    normalize_raw_message,
)
from ckanext.dge_harvest.services.report.harvest_report_text import (
    normalize_preserved_text,
)

try:
    from ckan.plugins.toolkit import BaseModel
except ImportError:
    # CKAN <= 2.9
    from ckan.model.meta import metadata
    from sqlalchemy.ext.declarative import declarative_base

    BaseModel = declarative_base(metadata=metadata)


class DgeHarvestMessage(BaseModel, HarvestDomainObject):
    """Canonical federation report message observed during a harvest job."""

    __tablename__ = "dge_harvest_message"

    id = Column(UnicodeText, primary_key=True, default=make_uuid)
    harvest_job_id = Column(
        UnicodeText,
        ForeignKey("harvest_job.id", ondelete="CASCADE"),
        nullable=False,
    )
    harvest_object_id = Column(
        UnicodeText,
        ForeignKey("harvest_object.id", ondelete="SET NULL"),
        nullable=True,
    )
    level = Column(UnicodeText, nullable=False)
    phase = Column(UnicodeText, nullable=False)
    origin = Column(UnicodeText, nullable=False)
    category = Column(UnicodeText, nullable=False)
    message_code = Column(UnicodeText, nullable=True)
    display_message = Column(UnicodeText, nullable=False)
    display_message_ui = Column(UnicodeText, nullable=False)
    raw_message = Column(UnicodeText, nullable=True)
    details_json = Column(UnicodeText, nullable=True)
    more_info_url = Column(UnicodeText, nullable=True)
    fingerprint_full = Column(UnicodeText, nullable=False)
    fingerprint_semantic = Column(UnicodeText, nullable=True)
    legacy_projection = Column(UnicodeText, nullable=True)
    created = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    job = relationship(
        HarvestJob,
        backref=backref("dge_harvest_messages", cascade="all, delete-orphan"),
    )
    harvest_object = relationship(
        HarvestObject,
        backref=backref("dge_harvest_messages"),
    )

    __table_args__ = (
        Index(
            "ix_dge_harvest_message_job_created",
            "harvest_job_id",
            "created",
        ),
        Index(
            "ix_dge_harvest_message_job_fingerprint_full",
            "harvest_job_id",
            "fingerprint_full",
        ),
        Index(
            "ix_dge_harvest_message_job_level",
            "harvest_job_id",
            "level",
        ),
        Index(
            "ix_dge_harvest_message_job_phase",
            "harvest_job_id",
            "phase",
        ),
        Index("ix_dge_harvest_message_object", "harvest_object_id"),
        Index("ix_dge_harvest_message_code", "message_code"),
    )

    def __repr__(self):
        """Return a compact debug representation of the canonical message."""
        return (
            "<DgeHarvestMessage(id={}, job_id={}, level={}, code={})>"
        ).format(
            self.id,
            self.harvest_job_id,
            self.level,
            self.message_code,
        )

    @validates("raw_message")
    def validate_raw_message(self, key, value):
        """Normalize the internal raw payload before persistence."""
        return normalize_raw_message(value)

    @validates("display_message_ui")
    def validate_display_message_ui(self, key, value):
        """Normalize the visible formatted payload before persistence."""
        return normalize_preserved_text(value)

    @validates("details_json")
    def validate_details_json(self, key, value):
        """Normalize the structured internal details before persistence."""
        return normalize_details_json(value)


class DgeHarvestReportRow(BaseModel, HarvestDomainObject):
    """Materialized federation report row grouped by visible fingerprint."""

    __tablename__ = "dge_harvest_report_row"

    id = Column(UnicodeText, primary_key=True, default=make_uuid)
    harvest_job_id = Column(
        UnicodeText,
        ForeignKey("harvest_job.id", ondelete="CASCADE"),
        nullable=False,
    )
    fingerprint_full = Column(UnicodeText, nullable=False)
    fingerprint_semantic = Column(UnicodeText, nullable=True)
    level = Column(UnicodeText, nullable=False)
    phase = Column(UnicodeText, nullable=False)
    origin = Column(UnicodeText, nullable=False)
    category = Column(UnicodeText, nullable=False)
    message_code = Column(UnicodeText, nullable=True)
    display_message = Column(UnicodeText, nullable=False)
    display_message_ui = Column(UnicodeText, nullable=False)
    more_info_url = Column(UnicodeText, nullable=True)
    message_count = Column(Integer, nullable=False)
    first_message_id = Column(
        UnicodeText,
        ForeignKey("dge_harvest_message.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_message_id = Column(
        UnicodeText,
        ForeignKey("dge_harvest_message.id", ondelete="SET NULL"),
        nullable=True,
    )
    first_seen = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )
    last_seen = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )
    created = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        nullable=False,
    )
    modified = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    job = relationship(
        HarvestJob,
        backref=backref("dge_harvest_report_rows", cascade="all, delete-orphan"),
    )
    first_message = relationship(
        DgeHarvestMessage,
        foreign_keys=[first_message_id],
    )
    last_message = relationship(
        DgeHarvestMessage,
        foreign_keys=[last_message_id],
    )

    __table_args__ = (
        CheckConstraint(
            "message_count > 0",
            name="ck_dge_harvest_report_row_message_count_positive",
        ),
        UniqueConstraint(
            "harvest_job_id",
            "fingerprint_full",
            name="uq_dge_harvest_report_row_job_fingerprint",
        ),
        Index(
            "ix_dge_harvest_report_row_job_level",
            "harvest_job_id",
            "level",
        ),
        Index(
            "ix_dge_harvest_report_row_job_message",
            "harvest_job_id",
            "display_message",
        ),
        Index(
            "ix_dge_harvest_report_row_job_count",
            "harvest_job_id",
            "message_count",
        ),
        Index(
            "ix_dge_harvest_report_row_job_modified",
            "harvest_job_id",
            "modified",
        ),
        Index("ix_dge_harvest_report_row_code", "message_code"),
        Index(
            "ix_dge_harvest_report_row_semantic",
            "fingerprint_semantic",
        ),
    )

    def __repr__(self):
        """Return a compact debug representation of one materialized row."""
        return (
            "<DgeHarvestReportRow(id={}, job_id={}, level={}, count={})>"
        ).format(
            self.id,
            self.harvest_job_id,
            self.level,
            self.message_count,
        )


dge_harvest_message_table = DgeHarvestMessage.__table__
dge_harvest_report_row_table = DgeHarvestReportRow.__table__
