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


"""Add UI-preserving display message columns to harvest report tables.

Revision ID: 20260619_000001
Revises: 20260511_000001
Create Date: 2026-06-19 00:00:01.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260619_000001"
down_revision = "20260511_000001"
branch_labels = None
depends_on = None


def upgrade():
    """Add the UI display column and backfill existing rows."""
    op.add_column(
        "dge_harvest_message",
        sa.Column("display_message_ui", sa.UnicodeText(), nullable=True),
    )
    op.add_column(
        "dge_harvest_report_row",
        sa.Column("display_message_ui", sa.UnicodeText(), nullable=True),
    )

    op.execute(
        "UPDATE dge_harvest_message "
        "SET display_message_ui = display_message "
        "WHERE display_message_ui IS NULL"
    )
    op.execute(
        "UPDATE dge_harvest_report_row "
        "SET display_message_ui = display_message "
        "WHERE display_message_ui IS NULL"
    )

    op.alter_column(
        "dge_harvest_message",
        "display_message_ui",
        nullable=False,
    )
    op.alter_column(
        "dge_harvest_report_row",
        "display_message_ui",
        nullable=False,
    )


def downgrade():
    """Remove the UI display columns from harvest report tables."""
    op.drop_column("dge_harvest_report_row", "display_message_ui")
    op.drop_column("dge_harvest_message", "display_message_ui")
