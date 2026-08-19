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

"""Create dge_harvest_job_extra table

Revision ID: 20250415_135300
Revises:
Create Date: 2025-04-15 13:53:00.000000

"""

from alembic import op
import sqlalchemy as sa

# Identificadores de revisión
revision = "20250415_135300"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Crea la tabla dge_harvest_job_extra con UUID como PK."""
    op.create_table(
        "dge_harvest_job_extra",
        sa.Column(
            "id",
            sa.UnicodeText(),
            primary_key=True,
            # Nota: make_uuid se aplica a nivel de modelo, no en DDL.
            # Para inserts directos en BD, generar UUID en la aplicación.
        ),
        sa.Column(
            "harvest_job_id",
            sa.UnicodeText(),
            sa.ForeignKey("harvest_job.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.UnicodeText(), nullable=False),
        sa.Column("value", sa.UnicodeText(), nullable=True),
        sa.Column(
            "created",
            sa.DateTime(),
            default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "harvest_job_id",
            "key",
            name="uq_dge_harvest_job_extra_job_key",
        ),
    )

    op.create_index(
        "ix_dge_harvest_job_extra_job",
        "dge_harvest_job_extra",
        ["harvest_job_id"],
    )


def downgrade():
    """Elimina la tabla dge_harvest_job_extra."""
    op.drop_index(
        "ix_dge_harvest_job_extra_job",
        table_name="dge_harvest_job_extra",
    )
    op.drop_table("dge_harvest_job_extra")