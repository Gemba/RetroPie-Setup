#! /usr/bin/env python3

# scummvm_helper.py: Utility to maintain scummvm.ini entries.
# This script is to be used in a RetroPie setup.
#
# It is leveraged by the launcher script "+Start ScummVM.sh" (scummvm)
# but can also be used standalone.
#
# See scummvm_helper.py --help for usage.
#
# Copyright (C) 2022 Gemba
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import argparse
import configparser
import logging
import re
import sys
from collections import OrderedDict
from functools import cmp_to_key
from pathlib import Path

SCUMMVM_INI = Path('/opt/retropie/configs/scummvm/scummvm.ini')

ROM_HOME = Path('/home/pi/RetroPie/roms/scummvm')
LOG_FILE = "/dev/shm/runcommand.log"


def setup_logging(is_debug):
    """Creates log instance."""
    global log
    log = logging.getLogger(f"{Path(__file__).name}")
    log.setLevel(logging.DEBUG)

    if not is_debug:
        filelog = logging.FileHandler(LOG_FILE, mode='w')
        filelog.setLevel(logging.INFO)
        filelog.setFormatter(logging.Formatter(
            '%(levelname)-5s %(name)s: %(message)s'))
        log.addHandler(filelog)
    else:
        con = logging.StreamHandler()
        con.setLevel(logging.DEBUG)
        con.setFormatter(logging.Formatter('%(levelname)-5s: %(message)s'))
        log.addHandler(con)


def cli_parser():
    """Sets up command line parser."""
    parser = argparse.ArgumentParser(description='Utility to modify scummvm.ini'
                                     ' files. Used as part of "+Start ScummVM.'
                                     'sh"')
    parser.add_argument('-d', '--debug', help=f'verbose lgg to terminal, '
                        f'disables file log to {LOG_FILE}',
                        action='store_true', default=False)
    subparsers = parser.add_subparsers(
        help=f'help for subcommands e.g., {__file__}  createsvm --help',
        required=True, dest='command')

    add_createsvm_parser(subparsers)
    add_uniqsection_parser(subparsers)
    add_exists_parser(subparsers)
    return parser


def add_createsvm_parser(subparsers):
    # create svm
    createsvm_parser = subparsers.add_parser('createsvm', help=f'creates set'
                                             f' of *.svm files in in {ROM_HOME}'
                                             ' for each [gamesection]'
                                             ' from scummvm.ini. Uses'
                                             f' {SCUMMVM_INI} as source')
    createsvm_parser.add_argument('-o', '--overwrite', help='overwrites'
                                  ' existing *.svm files',
                                  action='store_true')
    createsvm_parser.set_defaults(func=create_svm_files)


def add_uniqsection_parser(subparsers):
    # unifies different game short name flavors
    # e.g. <game_short_name>-dos, <game_short_name>-win, <game_short_name>-gog
    # to <game_short_name> in ini file
    uniq_parser = subparsers.add_parser('uniq', help='keep only the first game'
                                        ' short name when multiple entries are '
                                        'generated e.g., [lba-gb], [lba-fr], '
                                        '[lba-de] will only keep [lba]')
    uniq_parser.add_argument('shortname', help='the game short name to  unify '
                             'e.g., tentacle. Use _all_ to unify every game '
                             'section in scummvm.ini, this is useful after a '
                             '"Mass Add..." in ScummVM UI')
    uniq_parser.set_defaults(func=uniq_game_short_name)


def add_exists_parser(subparsers):
    # exists game section
    exists_parser = subparsers.add_parser('checkentry', help='test if a'
                                          ' gamesection exists in a'
                                          ' scummvm.ini file.')
    exists_parser.add_argument('section', help='the [gamesection] to test for'
                               ' presence e.g., tentacle')
    exists_parser.set_defaults(func=check_entry)


# end of parser / setup section


def create_svm_files(args):
    """Creates a set of *.svm files by iterating over an scummvm.ini file."""
    ini = read_ini(SCUMMVM_INI)
    gamepaths = []
    created = 0
    log.info("Checking if new *.svm files need to be created.")
    for sect in [s for s in ini if 'path' in ini[s]]:
        gpath = ini[sect]['path']
        gdir = Path(gpath).name
        log.debug(f"Checking '{sect}' for folder {gdir}/ ...")
        svm_file = f"{gpath}.svm"
        svm_path = ROM_HOME.joinpath(svm_file)
        if gpath not in gamepaths:
            gamepaths.append(gpath)
            if not svm_path.exists() or args.overwrite:
                with open(svm_path, 'w') as fh:
                    fh.write(f"{sect}\n")
                log.debug(f"... created: {svm_path.name}, with: '{sect}'.")
                created = created + 1
            else:
                with open(svm_path, 'r') as fh:
                    svm_content = fh.readline().strip()
                log.debug(f"... exists: {svm_path.name}, with: '{svm_content}'."
                          " Skipping.")
        else:
            with open(svm_path, 'r') as fh:
                game_id = fh.readline().strip()
            log.debug(f"... game variant detected. Already have "
                      f"'{svm_path.name}' containing: '{game_id}', current"
                      f" value '{sect}' not set.")
    s = '' if created == 1 else 's'
    log.info(f"Created {created} *.svm file{s}.")


def uniq_game_short_name(args):
    """Keeps only the first entry of multiple game sections with the same stem.

    For example if the sections [lba-gb], [lba-fr], [lba-de] exists, they
    will be reduced to the entries of [lba-gb] at the section [lba], when the
    game short name lba was given as input."""
    short_name = args.shortname
    ini = read_ini(SCUMMVM_INI)
    # only sections which point to a game
    game_sects = [s for s in ini if 'path' in ini[s]]
    # output ini object
    ini_new = configparser.ConfigParser({}, OrderedDict)

    if short_name == "_all_":
        uniq_all_sections(ini, ini_new, short_name, game_sects)
    else:
        uniq_section(ini, ini_new, short_name, game_sects)

    copy_gamesection(ini, ini_new, 'scummvm')
    sorted_sections = sorted(ini_new._sections.items(),
                             key=cmp_to_key(cmp_scummvm_ini_sections))
    ini_new._sections = OrderedDict(sorted_sections)

    with open(SCUMMVM_INI, 'w') as fh:
        ini_new.write(fh, space_around_delimiters=False)


def uniq_all_sections(ini, ini_new, short_name, game_sects):
    # find all gamesections with dashes, keep only game short name
    game_short_names = set([s.split('-')[0]
                            for s in ini.sections() if '-' in s])
    for short_name in game_short_names:
        # keep only relevant game sections:
        # matches section with exact same name as short_name or
        # sections with short_name followed by at least one dash
        re_sect = rf"^{short_name}([-].*)?$"
        game_sections = [s for s in game_sects if re.search(re_sect, s)]
        source_sect = default_variant(game_sections)
        copy_gamesection(ini, ini_new, short_name, source_sect)
        log.debug(f"Source section [{source_sect}] changed to [{short_name}].")

    # copy other sections w/o dashes
    [copy_gamesection(ini, ini_new, sect)
     for sect in [s for s in game_sects if '-' not in s]]


def uniq_section(ini, ini_new, short_name, game_sects):
    if '-' in short_name:
        log.error(f"Game short name '{short_name}' may not contain dashes. "
                  "Exiting.")
        sys.exit(-2)

    re_sect = rf"^{short_name}([-].*)?$"
    game_sections = [s for s in game_sects if re.search(re_sect, s)]

    if len(game_sections) == 0:
        log.warning(f"Section [{short_name}] not present in {SCUMMVM_INI}. "
                    "Exiting.")
        sys.exit(-1)

    if len(game_sections) == 1 and short_name in ini:
        log.info(f"Section [{short_name}] already unique in {SCUMMVM_INI}. "
                 "Exiting.")
        sys.exit(0)

    source_sect = default_variant(game_sections)
    copy_gamesection(ini, ini_new, short_name, source_sect)
    log.debug(f"Source section [{source_sect}] changed to [{short_name}].")
    # retain other
    [copy_gamesection(ini, ini_new, sect)
     for sect in game_sects if not re.search(re_sect, sect)]


def default_variant(game_sections):
    """Selects the default language variant (EN) if several game variants
    with language information are found."""
    source_sect = game_sections[0]
    # make english default selection (suffix -gb / -en)
    # needed for "Little Big Adventure"
    for s in game_sections:
        if s.endswith('-gb') or s.endswith('-en'):
            source_sect = s
            break
    return source_sect


def cmp_scummvm_ini_sections(this, that):
    """Compare function for scummvm.ini section names."""
    if 'scummvm' == this[0]:
        return -1
    if 'scummvm' == that[0]:
        return 1
    return -1 if this[0] <= that[0] else 1


def copy_gamesection(ini, ini_new, short_name, source_section=None):
    """Copies one game section to target ini if the section does not yet
    exist."""
    if not ini_new.has_section(short_name):
        ini_new.add_section(short_name)
        if not source_section:
            source_section = short_name
        for k, v in ini.items(source_section):
            if k == 'gameid':
                v = short_name  # e.g. for gameid=bladerunner-final
            ini_new.set(short_name, k, v)


def check_entry(args):
    """Tests for existence of a given game id as ini section.

    Check is successful iff game id is exactly matched.
    Note that a [section] for a game may contain variants separated by dash
    e.g., for language or platform, like: tlj-win, which may hinder a match
    if given game id has no dash(es)."""
    game_short_name = args.section
    ini = read_ini(SCUMMVM_INI)
    if game_short_name in ini.sections():
        print("present")
    else:
        print("absent")


def read_ini(fn):
    """Checks existence of ini file and returns configparser object."""
    if fn.exists():
        config = configparser.ConfigParser()
        config.read(fn)
        return config
    log.fatal(f"File {fn} does not exist. Exiting.")
    sys.exit(-2)


# On with the show
if __name__ == "__main__":
    args = cli_parser().parse_args()
    setup_logging(args.debug)
    args.func(args)
