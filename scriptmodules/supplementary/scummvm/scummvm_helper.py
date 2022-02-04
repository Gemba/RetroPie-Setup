#! /usr/bin/env python3

# scummvm_helper.py: Utility to maintain scummvm.ini entries.
# This script is to be used in a RetroPie setup.
#
# It is leveraged by the launcher scripts "+Start ScummVM.sh" (scummvm) and
# "romdir-launcher.sh" (lr-scrummvm) but can also be used standalone.
#
# See scummvm_helper.py --help for usage.
#
# Copyright (C) 2022 Gemba @ github
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

# Note on terminology:
# 'game id' denotes the game identifier, synonym is target. The game id does
# usually not contain the engine. However the full game id does contain the
# engine followed by the target, separated by a colon. For example
# scumm:tentacle. This format id is also referenced as ScummVM ID

import argparse
import configparser
import logging
import re
import sys
from collections import OrderedDict
from functools import cmp_to_key
from pathlib import Path

SCUMMVM_INI = Path("/opt/retropie/configs/scummvm/scummvm.ini")
LR_SCUMMVM_INI = Path("/home/pi/RetroPie/BIOS/scummvm.ini")

ROM_HOME = Path("/home/pi/RetroPie/roms/scummvm")
ARGS_INI_ALLOWED = ["libretro", "native"]
LOG_FILE = "/dev/shm/runcommand.log"


def setup_logging(is_debug):
    """Creates log instance."""
    global log
    log = logging.getLogger(f"{Path(__file__).name}")
    log.setLevel(logging.DEBUG)

    if is_debug:
        con = logging.StreamHandler()
        con.setLevel(logging.DEBUG)
        con.setFormatter(logging.Formatter("%(levelname)-5s: %(message)s"))
        log.addHandler(con)
    else:
        filelog = logging.FileHandler(LOG_FILE, mode="w")
        filelog.setLevel(logging.INFO)
        log_fmt = logging.Formatter("%(levelname)-5s %(name)s: %(message)s")
        filelog.setFormatter(log_fmt)
        log.addHandler(filelog)


def cli_parser():
    """Sets up command line parser."""
    parser = argparse.ArgumentParser(
        description="Utility to modify scummvm.ini files. Used as part of "
        "'+Start ScummVM.sh' and 'romdir-launcher.sh' (libretro core of "
        "ScummVM)."
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        help=f"verbose log to terminal, disables log to file {LOG_FILE}"
    )
    subparsers = parser.add_subparsers(
        required=True,
        dest="command",
        help=f"help for subcommands e.g., {__file__}  createsvm --help"
    )

    add_createsvm_parser(subparsers)
    msg_ini_files = (
        f"'native' resolves to {SCUMMVM_INI}, 'libretro' resolves "
        f"to {LR_SCUMMVM_INI}"
    )
    add_uniqsection_parser(subparsers, msg_ini_files)
    add_copysection_parser(subparsers, msg_ini_files)
    add_exists_parser(subparsers, msg_ini_files)
    return parser


def add_createsvm_parser(subparsers):
    """Subparser for createsvm command."""
    createsvm_parser = subparsers.add_parser(
        "createsvm",
        help=f"creates set of *.svm files in in {ROM_HOME} for each"
        f" [gamesection] from scummvm.ini. Uses {SCUMMVM_INI} as source"
    )
    createsvm_parser.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        help="overwrites existing *.svm files"
    )
    createsvm_parser.set_defaults(func=create_svm_files_cmd)


def add_uniqsection_parser(subparsers, msg_ini_files):
    """Subparser for unifying targets (game ids) in scummvm.ini."""
    # unifies different target variants
    # e.g. <target>-dos, <target>-win, <target>-gog
    # to one <target> in ini file
    uniq_parser = subparsers.add_parser(
        "uniq",
        help="keep only the first target entry when multiple entries are"
        " generated e.g., [lba-gb], [lba-fr], [lba-de] will only keep [lba]"
    )
    uniq_parser.add_argument(
        "game_id",
        help="the game id to unify without variant/dashes e.g., tentacle."
        " Use _all_ as game id to unify every game section in scummvm.ini,"
        " this is useful after a 'Mass Add...' in ScummVM UI"
    )
    uniq_parser.add_argument(
        "-i",
        "--ini",
        dest="scummvm",
        metavar="selector",
        nargs=1,
        action=ParserIniAction,
        default="native",
        help=f'scummvm.ini file to unify ({"/".join(ARGS_INI_ALLOWED)}), '
        f"default: native. {msg_ini_files}",
    )
    uniq_parser.set_defaults(func=unique_target_cmd)


def add_copysection_parser(subparsers, msg_ini_files):
    """Subparser for copying a [<game id>] section between scummvm.ini files."""
    copysection_parser = subparsers.add_parser(
        "copyentry", help="copy one scummvm target (game id) to another ini file"
    )
    copysection_parser.add_argument(
        "section", help="the [<game-id>] to copy without brackets e.g., lba"
    )
    copysection_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="force update existing [<game-id>] entry",
    )
    copysection_parser.add_argument(
        "-t",
        "--to",
        dest="scummvm",
        metavar="selector",
        nargs=1,
        action=ParserIniAction,
        default="libretro",
        help=f'destination ini to copy game id to ({"/".join(ARGS_INI_ALLOWED)}),'
        f" default: libretro. {msg_ini_files}",
    )
    copysection_parser.set_defaults(func=copy_section_cmd)


def add_exists_parser(subparsers, msg_ini_files):
    """Subparser for testing existence of game id entry."""
    exists_parser = subparsers.add_parser(
        "checkentry",
        help="test if a target section configuration exists in a scummvm.ini"
        " file."
    )
    exists_parser.add_argument(
        "section", help="the [target] to test for presence e.g., tentacle"
    )
    exists_parser.add_argument(
        "-i",
        "--ini",
        dest="scummvm",
        metavar="selector",
        nargs=1,
        action=ParserIniAction,
        default="native",
        help=f'scummvm.ini to test ({"/".join(ARGS_INI_ALLOWED)}), default:'
        f" native. {msg_ini_files}",
    )
    exists_parser.set_defaults(func=check_entry_cmd)


class ParserIniAction(argparse.Action):
    """Validates parameter values for CLI --ini and --to."""

    def __call__(self, parser, namespace, values, option_string=None):
        v = values[0]
        allowed = ", ".join(ARGS_INI_ALLOWED)
        msg = f"Got value: {v}. Was expecting one of: {allowed}"

        if v not in ARGS_INI_ALLOWED:
            raise ValueError(msg)

        setattr(namespace, self.dest, v)


# end of parser / setup section


def create_svm_files_cmd(args):
    """Creates a set of *.svm files by iterating over an scummvm.ini file."""
    ini = read_ini(SCUMMVM_INI)
    gamepaths = []
    ctr = 0
    log.info("Checking if new *.svm files need to be created.")
    for game_id in [s for s in ini if "path" in ini[s]]:
        gpath = ini[game_id]["path"]
        gdir = Path(gpath).name
        log.debug(f"Checking '{game_id}' for folder {gdir}/ ...")
        svm_file = f"{gpath}.svm"
        svm_path = ROM_HOME.joinpath(svm_file)
        if gpath not in gamepaths:
            gamepaths.append(gpath)
            if not svm_path.exists() or args.overwrite:
                with open(svm_path, "w") as fh:
                    fh.write(f"{game_id}\n")
                log.debug(f"... created: {svm_path.name}, with: '{game_id}'.")
                ctr = ctr + 1
            else:
                with open(svm_path, "r") as fh:
                    # usually game id/target as content
                    target = fh.readline().strip()
                log.debug(
                    f"... exists: {svm_path.name}, with: '{target}'."
                    " Skipping."
                )
        else:
            with open(svm_path, "r") as fh:
                target = fh.readline().strip()
            log.debug(
                f"... game variant detected. Already have "
                f"'{svm_path.name}' containing: '{target}', current"
                f" value '{game_id}' not set."
            )
    s = "" if ctr == 1 else "s"
    log.info(f"Created {ctr} *.svm file{s}.")


def unique_target_cmd(args):
    """Keeps only the first entry of multiple game targets with the same stem.

    For example if the sections [lba-gb], [lba-fr], [lba-de] exists, they
    will be reduced to the entries of [lba-gb] at the section/target [lba],
    when the game short name lba was given as input."""
    ini_native = args.scummvm == "native"
    game_id = args.game_id
    cfg_file = SCUMMVM_INI if ini_native else LR_SCUMMVM_INI
    ini = read_ini(cfg_file)

    # pick only sections which represent game configs
    targets = [s for s in ini if "path" in ini[s]]
    # output ini
    ini_new = configparser.ConfigParser({}, OrderedDict)

    if game_id == "_all_":
        uniq_all_targets(ini, ini_new, game_id, targets)
    else:
        uniq_target(ini, ini_new, game_id, targets, cfg_file)

    # copy [scummvm] config
    _cp_section(ini, ini_new, "scummvm")
    sorted_sections = sorted(ini_new._sections.items(),
                             key=cmp_to_key(_cmp_scummvm_ini_sections)
                             )
    ini_new._sections = OrderedDict(sorted_sections)

    with open(cfg_file, "w") as fh:
        ini_new.write(fh, space_around_delimiters=False)


def uniq_all_targets(ini, ini_new, game_id, targets):
    # find all targets with dashes, keep only game id without dash
    plain_game_ids = set([s.split("-")[0]
                          for s in ini.sections() if "-" in s])
    for game_id in plain_game_ids:
        # keep only relevant game sections:
        # matches section with exact same name as game_id or
        # sections with game_id followed by at least one dash
        re_sect = rf"^{game_id}([-].*)?$"
        game_sections = [s for s in targets if re.search(re_sect, s)]
        source_sect = default_variant(game_sections)
        _cp_section(ini, ini_new, game_id, source_sect)
        log.debug(
            f"Source ini section [{source_sect}] changed to [{game_id}].")

    # copy other sections without dashes
    [_cp_section(ini, ini_new, sect)
     for sect in [s for s in targets if "-" not in s]]


def uniq_target(ini, ini_new, game_id, targets, cfg_file):
    if "-" in game_id:
        log.error(
            f"Game short name '{game_id}' may not contain dashes. Exiting.")
        sys.exit(-2)

    re_sect = rf"^{game_id}([-].*)?$"
    game_sections = [s for s in targets if re.search(re_sect, s)]

    if len(game_sections) == 0:
        log.warning(f"Section [{game_id}] not present in {cfg_file}. Exiting.")
        sys.exit(-1)

    if len(game_sections) == 1 and game_id in ini:
        log.info(f"Section [{game_id}] already unique in {cfg_file}. Exiting.")
        sys.exit(0)

    source_sect = default_variant(game_sections)
    _cp_section(ini, ini_new, game_id, source_sect)
    log.debug(f"Source ini section [{source_sect}] changed to [{game_id}].")
    # retain other
    [_cp_section(ini, ini_new, sect)
     for sect in targets if not re.search(re_sect, sect)]


def default_variant(game_sections):
    """Selects the default language variant (en) if several game variants
    with language information are found."""
    source_sect = game_sections[0]
    # make english default selection (suffix -gb / -en)
    # needed for "Little Big Adventure"
    for s in game_sections:
        if s.endswith("-gb") or s.endswith("-en"):
            source_sect = s
            break
    return source_sect


def _cmp_scummvm_ini_sections(this, that):
    """Compare function for scummvm.ini section names."""
    if this[0] == "scummvm":
        return -1
    if that[0] == "scummvm":
        return 1
    return -1 if this[0] <= that[0] else 1


def _cp_section(ini, ini_new, game_id, source_section=None):
    """Copies one [game id] section to destination ini if the destination
    section does not yet exist.

    If the source section does not exist nothing is copied."""
    if ini_new.has_section(game_id):
        return

    ini_new.add_section(game_id)
    if not source_section:
        source_section = game_id
    for k, v in ini.items(source_section):
        if k == "gameid":
            # preserve provided game id e.g., for gameid=bladerunner-final
            v = game_id
        ini_new.set(game_id, k, v)


def copy_section_cmd(args):
    """Copies one section of a scummvm.ini file to another.

    If source section does not exists this function bails out.
    A relative path to the game folder is replaced with an absolute path for
    libretro core."""
    to_native = args.scummvm == "native"
    section_name = args.section
    if to_native:
        # to ScummVM native
        from_file = LR_SCUMMVM_INI
        to_file = SCUMMVM_INI
    else:
        # to libretro-scummvm
        from_file = SCUMMVM_INI
        to_file = LR_SCUMMVM_INI

    from_ini = read_ini(from_file)
    to_ini = read_ini(to_file)

    # keep only game sections
    game_sections = [s for s in from_ini if "path" in from_ini[s]]

    if not section_name in game_sections:
        log.warning(
            f"Source [{section_name}] not present in {from_file}. Exiting.")
        sys.exit(-1)

    if section_name in to_ini.sections() and not args.force:
        log.warning(
            f"Game ID [{section_name}] already present in {to_file}."
            " Use --force to update. Exiting.")
        sys.exit(-1)

    section = from_ini[section_name]
    to_ini[section_name] = section

    tgt_path = to_ini[section_name]["path"]
    if not to_native and not Path(tgt_path).is_absolute():
        # lr-scummvm requires absolute paths in scummvm.ini
        to_ini[section_name]["path"] = f"{Path(ROM_HOME).joinpath(tgt_path)}"

    with open(to_file, "w") as fh:
        to_ini.write(fh)

    log.debug(f"Section [{section_name}] written to {to_file}.")


def check_entry_cmd(args):
    """Tests for existence of a given game id as ini section.

    Check is successful iff game id is exactly matched.
    Note that a [section] for a game may contain variants separated by dash
    e.g., for language or platform, like: tlj-win, which may hinder a match
    if given game id has no dash(es)."""
    ini_native = args.scummvm == "native"
    game_id = args.section
    cfg_file = SCUMMVM_INI if ini_native else LR_SCUMMVM_INI
    ini = read_ini(cfg_file)
    if game_id in ini.sections():
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


if __name__ == "__main__":
    args = cli_parser().parse_args()
    setup_logging(args.debug)
    args.func(args)
