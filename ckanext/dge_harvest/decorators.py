# Copyright (C) 2025 Entidad Pública Empresarial Red.es
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

import logging
from functools import wraps
import inspect
import time

def log_execution(level=logging.DEBUG):
    """Generate a decorator to register input and output of methods."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            max_len = 200
            def safe_str(value):
                try:
                    if value is None:
                        return "None"
                    if isinstance(value, (tuple, list)):
                        return type(value).__name__ + "(" + ", ".join(
                            (str(item)[:max_len] + "...[TRUNCATE]" if len(str(item)) > max_len else str(item))
                            for item in value
                        ) + ")"
                    value_str = str(value)
                    return (value_str[:max_len] + "...[TRUNCATE]") if len(value_str) > max_len else value_str
                except Exception as e:
                    logger.warning(f"Error processing log value: {type(e).__name__} - {e}")
                    return "[ERROR to process value]"

            # Get context info
            cls_name = None
            if hasattr(args[0], '__class__'):
                cls_name = args[0].__class__.__name__

            # Inspect params' names
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())
            
            # Delete 'self' param and its value if is a class method
            aux_args = args
            if param_names and param_names[0] == 'self':
                param_names.pop(0) 
                aux_args = args[1:]
            else:
                cls_name = None

            # Process input params
            named_args = {name: safe_str(value) for name, value in zip(param_names, aux_args)}
            if "args" in param_names:
                named_args["args"] = f"*args={safe_str(aux_args)}"
            named_kwargs = {k: safe_str(v) for k, v in kwargs.items()}
            logger.log(
                level,
                f"{'[' + cls_name + ']' if cls_name else ''}[{func.__name__}] "
                f"Starting the method: args={named_args}, kwargs={named_kwargs}"
            )

            # Run method
            ini = time.time()
            result = func(*args, **kwargs)
            end = time.time()

            # Process output params
            truncated_result = safe_str(result)
            logger.log(
                level,
                f"{'[' + cls_name + ']' if cls_name else ''}[{func.__name__}] "
                f"Ending the method in {end-ini} seconds with result={truncated_result}"
            )
            return result
        return wrapper
    return decorator

# Debug decorator
log_debug = log_execution(level = logging.DEBUG)

# Info decorator
log_info = log_execution(level = logging.INFO)
