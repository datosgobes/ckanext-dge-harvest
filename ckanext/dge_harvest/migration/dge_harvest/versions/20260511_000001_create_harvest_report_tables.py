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

"""Create the structured harvest report tables.

Revision ID: 20260511_000001
Revises: 20250415_135300
Create Date: 2026-05-11 00:00:01.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260511_000001"
down_revision = "20250415_135300"
branch_labels = None
depends_on = None


def upgrade():
    """Create the canonical message table and the materialized row table."""
    op.create_table(
        "dge_harvest_message",
        sa.Column("id", sa.UnicodeText(), primary_key=True),
        sa.Column(
            "harvest_job_id",
            sa.UnicodeText(),
            sa.ForeignKey("harvest_job.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "harvest_object_id",
            sa.UnicodeText(),
            sa.ForeignKey("harvest_object.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("level", sa.UnicodeText(), nullable=False),
        sa.Column("phase", sa.UnicodeText(), nullable=False),
        sa.Column("origin", sa.UnicodeText(), nullable=False),
        sa.Column("category", sa.UnicodeText(), nullable=False),
        sa.Column("message_code", sa.UnicodeText(), nullable=True),
        sa.Column("display_message", sa.UnicodeText(), nullable=False),
        sa.Column("raw_message", sa.UnicodeText(), nullable=True),
        sa.Column("details_json", sa.UnicodeText(), nullable=True),
        sa.Column("more_info_url", sa.UnicodeText(), nullable=True),
        sa.Column("fingerprint_full", sa.UnicodeText(), nullable=False),
        sa.Column("fingerprint_semantic", sa.UnicodeText(), nullable=True),
        sa.Column("legacy_projection", sa.UnicodeText(), nullable=True),
        sa.Column("created", sa.DateTime(), nullable=False),
    )

    op.create_index(
        "ix_dge_harvest_message_job_created",
        "dge_harvest_message",
        ["harvest_job_id", "created"],
    )
    op.create_index(
        "ix_dge_harvest_message_job_fingerprint_full",
        "dge_harvest_message",
        ["harvest_job_id", "fingerprint_full"],
    )
    op.create_index(
        "ix_dge_harvest_message_job_level",
        "dge_harvest_message",
        ["harvest_job_id", "level"],
    )
    op.create_index(
        "ix_dge_harvest_message_job_phase",
        "dge_harvest_message",
        ["harvest_job_id", "phase"],
    )
    op.create_index(
        "ix_dge_harvest_message_object",
        "dge_harvest_message",
        ["harvest_object_id"],
    )
    op.create_index(
        "ix_dge_harvest_message_code",
        "dge_harvest_message",
        ["message_code"],
    )

    op.create_table(
        "dge_harvest_report_row",
        sa.Column("id", sa.UnicodeText(), primary_key=True),
        sa.Column(
            "harvest_job_id",
            sa.UnicodeText(),
            sa.ForeignKey("harvest_job.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fingerprint_full", sa.UnicodeText(), nullable=False),
        sa.Column("fingerprint_semantic", sa.UnicodeText(), nullable=True),
        sa.Column("level", sa.UnicodeText(), nullable=False),
        sa.Column("phase", sa.UnicodeText(), nullable=False),
        sa.Column("origin", sa.UnicodeText(), nullable=False),
        sa.Column("category", sa.UnicodeText(), nullable=False),
        sa.Column("message_code", sa.UnicodeText(), nullable=True),
        sa.Column("display_message", sa.UnicodeText(), nullable=False),
        sa.Column("more_info_url", sa.UnicodeText(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column(
            "first_message_id",
            sa.UnicodeText(),
            sa.ForeignKey("dge_harvest_message.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "last_message_id",
            sa.UnicodeText(),
            sa.ForeignKey("dge_harvest_message.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("modified", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "message_count > 0",
            name="ck_dge_harvest_report_row_message_count_positive",
        ),
        sa.UniqueConstraint(
            "harvest_job_id",
            "fingerprint_full",
            name="uq_dge_harvest_report_row_job_fingerprint",
        ),
    )

    op.create_index(
        "ix_dge_harvest_report_row_job_level",
        "dge_harvest_report_row",
        ["harvest_job_id", "level"],
    )
    op.create_index(
        "ix_dge_harvest_report_row_job_message",
        "dge_harvest_report_row",
        ["harvest_job_id", "display_message"],
    )
    op.create_index(
        "ix_dge_harvest_report_row_job_count",
        "dge_harvest_report_row",
        ["harvest_job_id", "message_count"],
    )
    op.create_index(
        "ix_dge_harvest_report_row_job_modified",
        "dge_harvest_report_row",
        ["harvest_job_id", "modified"],
    )
    op.create_index(
        "ix_dge_harvest_report_row_code",
        "dge_harvest_report_row",
        ["message_code"],
    )
    op.create_index(
        "ix_dge_harvest_report_row_semantic",
        "dge_harvest_report_row",
        ["fingerprint_semantic"],
    )


def downgrade():
    """Drop the structured harvest report tables and their indexes."""
    op.drop_index(
        "ix_dge_harvest_report_row_semantic",
        table_name="dge_harvest_report_row",
    )
    op.drop_index(
        "ix_dge_harvest_report_row_code",
        table_name="dge_harvest_report_row",
    )
    op.drop_index(
        "ix_dge_harvest_report_row_job_modified",
        table_name="dge_harvest_report_row",
    )
    op.drop_index(
        "ix_dge_harvest_report_row_job_count",
        table_name="dge_harvest_report_row",
    )
    op.drop_index(
        "ix_dge_harvest_report_row_job_message",
        table_name="dge_harvest_report_row",
    )
    op.drop_index(
        "ix_dge_harvest_report_row_job_level",
        table_name="dge_harvest_report_row",
    )
    op.drop_table("dge_harvest_report_row")

    op.drop_index(
        "ix_dge_harvest_message_code",
        table_name="dge_harvest_message",
    )
    op.drop_index(
        "ix_dge_harvest_message_object",
        table_name="dge_harvest_message",
    )
    op.drop_index(
        "ix_dge_harvest_message_job_phase",
        table_name="dge_harvest_message",
    )
    op.drop_index(
        "ix_dge_harvest_message_job_level",
        table_name="dge_harvest_message",
    )
    op.drop_index(
        "ix_dge_harvest_message_job_fingerprint_full",
        table_name="dge_harvest_message",
    )
    op.drop_index(
        "ix_dge_harvest_message_job_created",
        table_name="dge_harvest_message",
    )
    op.drop_table("dge_harvest_message")
