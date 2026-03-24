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

import logging
import inspect
from typing import List, Tuple
import os
import configparser
from .decorators import log_debug, log_info

log = logging.getLogger(__name__)

class HarvesterConfigReaderException(Exception):
    def __init__(self, msg=None) -> None:
        Exception.__init__(self, msg)
        self.msg = msg

class HarvesterConfigReader():
    '''
    A class to read configurations for harvester from a separate configuration file.
    This class allows you to load and retrieve configuration properties from a custom file 
    that is not part of ckan.ini.
    '''

    def _get_log_prefix(self, method_name):
        return f'[{self.__class__.__name__}][{method_name}]'

    def __init__(self, config_file:str) -> None:
        """
        Initializes the FederationConfigManager with the specified configuration file.

        :param config_file: The path to the configuration file (e.g., 'config.ini')
        :type config_file: str
        """
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()

    @log_debug
    def load_config(self) -> None:
        """
        Loads the configuration file. Raises an error if the file is not found.
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"{method_log_prefix} Configuration file '{self.config_file}' not found.")
        self.config.read(self.config_file)

    @log_debug
    def get_property(self, section:str, key:str, default:str=None) -> str:
        """
        Retrieves the value of a specific property from the configuration.

        :param section: The section name in the configuration file (e.g., 'catalog').
        :type section: str
        
        :param key: The property key within the section (e.g., 'url').
        :type key: str
        
        :param default: An optional default value to return if the key is not found.
        :type default: str
        
        :return: The value of the property, or the default value if not found.
        :rtype: str
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if default is not None:
                return default
            raise KeyError(f"{method_log_prefix} Property '{key}' not found in section '{section}'.")

    @log_debug
    def get_section_properties(self, section:str) -> dict[str,str]:
        """
        Retrieves all properties in a specified section as a dictionary.

        :param section: The section name (e.g., 'catalog').
        :type section: str
        
        :return: A dictionary of all key-value pairs in the section.
        :rtype: dict[str,str]
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        if section not in self.config:
            raise KeyError(f"{method_log_prefix} Section '{section}' not found in the configuration file.")
        result = dict(self.config.items(section)) 
        return result

    @log_debug
    def get_properties_with_prefix(self, section:str, prefix:str) -> dict[str,str]:
        """
        Retrieves all properties in a section that start with a given prefix.

        :param section: The section name in the configuration file (e.g., 'catalog').
        :type section: str
        
        :param prefix: The prefix to filter the properties (e.g., 'api').
        :type prefix: str
        
        :return: A dictionary of all key-value pairs that start with the prefix.
        :rtype: dict[str,str]
        """
        method_log_prefix = self._get_log_prefix(inspect.currentframe().f_code.co_name)
        if section not in self.config:
            raise KeyError(f"{method_log_prefix} Section '{section}' not found in the configuration file.")
        result = {k: v for k, v in self.config.items(section) if k.startswith(prefix)}
        return result

    def reload_config(self) -> None:
        """
        Reloads the configuration file in case it has been modified.
        """
        self.load_config()

    @log_debug
    def get_section_property_as_a_list(self, section:str, key:str, default_value:str=None, split_character:str=None) -> list[str]:
        """
        Retrieves a list with the value of a specific property from the configuration.
        
        :param section: The section name in the configuration file (e.g., 'catalog').
        :type section: str
        
        :param key: The property key within the section (e.g., 'url').
        :type key: str
        
        :param default_value: An optional default value to return if the key is not found.
        :type default_value: str
        
        :param split_character: A separator character to separate values of a list. None by default
        :type split_character: str
        
        
        :return: A list with the value of the property, or the default value if not found.
        :rtype: list[str]
        """
        result = self.get_property(section, key, default_value)
        if not split_character:
            result = result.split()
        else:
            result = result.split(split_character)
        return result

    @log_debug
    def get_section_property_as_a_list_dict(self, section:str, key:str, default_value:str=None, separator_character:str='|', split_character:str=None) -> dict[str, list[str]]:
        """
        Retrieves a dictionary with the value of a specific property from the configuration whose value has this format:
        <key><separator_character><value>.
        The dictionary value will be a list to allow that key is repeated.

        :param section: The section name in the configuration file (e.g., 'catalog').
        :type section: str
        
        :param key: The property key within the section (e.g., 'url').
        :type key: str
        
        :param default_value: An optional default value to return if the key is not found.
        :type default_value: str
        
        :param separator_character: A separator character to separate key from value of dict
        :type separator_character: str
        
        :param split_character: A separator character to separate values of a list. None by default
        :type split_character: str
        
        :return: A dictionary with the keys and value of the property, or the default value if not found.
        :rtype: dict[str, list[str]]
        """
        result = {}
        DEFAULT_SEPARATOR_CHARACTER = '|'
        if not separator_character:
            separator_character = DEFAULT_SEPARATOR_CHARACTER
        property_values = self.get_section_property_as_a_list(section, key, default_value, split_character)
        
        for value in property_values:
            if value:
                data = value.split(separator_character)
                if data:
                    key = data[0] if len(data) >= 1 else None
                    value = data[1] if len(data) >=2 else None
                    if key and value:
                        result.setdefault(key,[]).append(value)
        return result

    @log_debug
    def get_section_property_as_a_str_dict(self, section:str, key:str, default_value:str=None, separator_character:str='|', split_character:str=None) -> dict[str, str]:
        """
        Retrieves a dictionary with the value of a specific property from the configuration whose value has this format:
        <key><separator_character><value>.

        :param section: The section name in the configuration file (e.g., 'catalog').
        :type section: str
        
        :param key: The property key within the section (e.g., 'url').
        :type key: str
        
        :param default_value: An optional default value to return if the key is not found.
        :type default_value: str
        
        :param separator_character: A separator character to separate key from value of dict
        :type separator_character: str
        
        :param split_character: A separator character to separate values of a list. None by default
        :type split_character: str
        
        :return: A dictionary with the keys and value of the property, or the default value if not found.
        :rtype: dict[str, str]
        """
        result = {}
        DEFAULT_SEPARATOR_CHARACTER = '|'
        if not separator_character:
            separator_character = DEFAULT_SEPARATOR_CHARACTER
        property_values = self.get_section_property_as_a_list(section, key, default_value, split_character)
        for value in property_values:
            if value:
                data = value.split(separator_character)
                if data:
                    key = data[0] if len(data) >= 1 else None
                    value = data[1] if len(data) >=2 else None
                    if key and value:
                        result[key] = value
        return result