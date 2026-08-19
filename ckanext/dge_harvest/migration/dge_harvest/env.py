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

from __future__ import annotations
"""Alembic environment for the DGE harvest extension migrations.

The environment includes the structured harvest report tables so Alembic
can autoload the shared metadata during upgrades.
"""

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from ckanext.dge_harvest.model import (
    dge_harvest_job_extra_table,
    dge_harvest_message_table,
    dge_harvest_report_row_table,
)

config = context.config
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

DGE_HARVEST_TABLES = (
    dge_harvest_job_extra_table,
    dge_harvest_message_table,
    dge_harvest_report_row_table,
)

target_metadata = DGE_HARVEST_TABLES[0].metadata


def run_migrations_offline():
    """Ejecuta migraciones en modo 'offline' (genera SQL sin conectar)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Ejecuta migraciones conectándose a la base de datos."""
    # CKAN inyecta la URL de la BD en runtime
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="dge_harvest_alembic_version",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
