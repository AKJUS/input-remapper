#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2021 sezanzeb <proxima@sezanzeb.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


"""Make the systems/environments mapping of keys and codes accessible."""


import re
import json
import subprocess
import evdev

from keymapper.logger import logger
from keymapper.mapping import Mapping, DISABLE_NAME, DISABLE_CODE
from keymapper.paths import get_config_path, touch, USER


# xkb uses keycodes that are 8 higher than those from evdev
XKB_KEYCODE_OFFSET = 8

XMODMAP_FILENAME = "xmodmap.json"


class SystemMapping:
    """Stores information about all available keycodes."""

    def __init__(self):
        """Construct the system_mapping."""
        self._mapping = {}
        self._xmodmap = {}
        self._case_insensitive_mapping = {}
        self.populate()

    def list_names(self):
        """Return an array of all possible names in the mapping."""
        return self._mapping.keys()

    def correct_case(self, symbol):
        """Return the correct casing for a symbol."""
        if symbol in self._mapping:
            return symbol
        # only if not e.g. both "a" and "A" are in the mapping
        return self._case_insensitive_mapping.get(symbol.lower(), symbol)

    def populate(self):
        """Get a mapping of all available names to their keycodes."""
        logger.debug("Gathering available keycodes")
        self.clear()
        xmodmap_dict = {}
        try:
            xmodmap = subprocess.check_output(
                ["xmodmap", "-pke"], stderr=subprocess.STDOUT
            ).decode()
            xmodmap = xmodmap
            self._xmodmap = re.findall(r"(\d+) = (.+)\n", xmodmap + "\n")
            xmodmap_dict = self._find_legit_mappings()
            if len(xmodmap_dict) == 0:
                logger.info("`xmodmap -pke` did not yield any symbol")
        except (subprocess.CalledProcessError, FileNotFoundError):
            # might be within a tty
            logger.info("`xmodmap` command not found")

        if USER != "root":
            # write this stuff into the key-mapper config directory, because
            # the systemd service won't know the user sessions xmodmap
            path = get_config_path(XMODMAP_FILENAME)
            touch(path)
            with open(path, "w") as file:
                logger.debug('Writing "%s"', path)
                json.dump(xmodmap_dict, file, indent=4)

        for name, code in xmodmap_dict.items():
            self._set(name, code)

        for name, ecode in evdev.ecodes.ecodes.items():
            if name.startswith("KEY") or name.startswith("BTN"):
                self._set(name, ecode)

        self._set(DISABLE_NAME, DISABLE_CODE)

    def update(self, mapping):
        """Update this with new keys.

        Parameters
        ----------
        mapping : dict
            maps from name to code. Make sure your keys are lowercase.
        """
        for name, code in mapping.items():
            self._set(name, code)

    def _set(self, name, code):
        """Map name to code."""
        self._mapping[str(name)] = code
        self._case_insensitive_mapping[str(name).lower()] = name

    def get(self, name):
        """Return the code mapped to the key."""
        # the correct casing should be shown when asking the system_mapping
        # for stuff. indexing case insensitive to support old presets.
        if name not in self._mapping:
            # only if not e.g. both "a" and "A" are in the mapping
            name = self._case_insensitive_mapping.get(str(name).lower())

        return self._mapping.get(name)

    def clear(self):
        """Remove all mapped keys. Only needed for tests."""
        keys = list(self._mapping.keys())
        for key in keys:
            del self._mapping[key]

    def get_name(self, code):
        """Get the first matching name for the code."""
        for entry in self._xmodmap:
            if int(entry[0]) - XKB_KEYCODE_OFFSET == code:
                return entry[1].split()[0]

        return None

    def _find_legit_mappings(self):
        """From the parsed xmodmap list find usable symbols and their codes."""
        xmodmap_dict = {}
        for keycode, names in self._xmodmap:
            # there might be multiple, like:
            # keycode  64 = Alt_L Meta_L Alt_L Meta_L
            # keycode 204 = NoSymbol Alt_L NoSymbol Alt_L
            # Alt_L should map to code 64. Writing code 204 only works
            # if a modifier is applied at the same time. So take the first
            # one.
            name = names.split()[0]
            xmodmap_dict[name] = int(keycode) - XKB_KEYCODE_OFFSET

        return xmodmap_dict


# this mapping represents the xmodmap output, which stays constant
system_mapping = SystemMapping()
