#! /usr/bin/env python3

# scummvm_helper.py: Utility to maintain scummvm.ini entries.
# This script is to be used in a RetroPie setup.
#
# It is leveraged by the launcher scripts "+Start ScummVM.sh" (scummvm) and
# "romdir-launcher.sh" (lr-scrummvm) but can also be used standalone.
#
# See scummvm_helper.py --help for usage.


import argparse
import configparser
import logging
import re
import sys
from collections import OrderedDict
from functools import cmp_to_key
from pathlib import Path

SCUMMVM_INI = Path('/opt/retropie/configs/scummvm/scummvm.ini')
LR_SCUMMVM_INI = Path('/home/pi/RetroPie/BIOS/scummvm.ini')

ROM_HOME = Path('/home/pi/RetroPie/roms/scummvm')
ARGS_INI_ALLOWED = ["libretro", "native"]
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
                                     'sh" and "romdir-launcher.sh" (Retroarch '
                                     'ScummVM).')
    parser.add_argument('-d', '--debug', help=f'verbose lgg to terminal, '
                        f'disables file log to {LOG_FILE}',
                        action='store_true', default=False)
    subparsers = parser.add_subparsers(
        help=f'help for subcommands e.g., {__file__}  createsvm --help',
        required=True, dest='command')

    add_createsvm_parser(subparsers)
    msg_ini_files = (f"'native' resolves to {SCUMMVM_INI}, 'libretro' resolves "
                     f"to {LR_SCUMMVM_INI}")
    add_uniqsection_parser(subparsers, msg_ini_files)
    add_copysection_parser(subparsers, msg_ini_files)
    add_exists_parser(subparsers, msg_ini_files)
    add_findsectionbypath_parser(subparsers)
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


def add_uniqsection_parser(subparsers, msg_ini_files):
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
    uniq_parser.add_argument('-i', '--ini', dest='scummvm', nargs=1,
                             action=ParserIniAction, default='native',
                             help='scummvm.ini to trim'
                             f' ({"/".join(ARGS_INI_ALLOWED)}), default:'
                             f' native. {msg_ini_files}')
    uniq_parser.set_defaults(func=uniq_game_short_name)


def add_copysection_parser(subparsers, msg_ini_files):
    # copy game section
    copysection_parser = subparsers.add_parser('copyentry', help='copy one'
                                               ' scummvm game section to'
                                               ' another ini file')
    copysection_parser.add_argument('section',
                                    help='the [gamesection] to copy e.g.,'
                                    ' lba-en')
    copysection_parser.add_argument('-f', '--force', action='store_true',
                                    help='force update existing [gamesection]'
                                    ' entry')
    copysection_parser.add_argument('-t', '--to', dest='scummvm', nargs=1,
                                    action=ParserIniAction, default='libretro',
                                    help='target ini to copy game section to'
                                    f' ({"/".join(ARGS_INI_ALLOWED)}), default:'
                                    f' libretro. {msg_ini_files}')
    copysection_parser.set_defaults(func=copy_entry)


def add_exists_parser(subparsers, msg_ini_files):
    # exists game section
    exists_parser = subparsers.add_parser('checkentry', help='test if a'
                                          ' gamesection exists in a'
                                          ' scummvm.ini file.')
    exists_parser.add_argument('section', help='the [gamesection] to test for'
                               ' presence e.g., tentacle')
    exists_parser.add_argument('-i', '--ini', dest='scummvm', nargs=1,
                               action=ParserIniAction, default='native',
                               help='scummvm.ini to test'
                               f' ({"/".join(ARGS_INI_ALLOWED)}), default:'
                               f' native. {msg_ini_files}')
    exists_parser.set_defaults(func=check_entry)


def add_findsectionbypath_parser(subparsers):
    # get gamesection by path
    help_msg = ('searches for game section containing a specific folder in '
                'path= and returns every matching game section. Applies only to'
                ' scummvm.ini of native ScummVM')
    section_parser = subparsers.add_parser('findsection', help=help_msg)
    section_parser.add_argument('folder', help='the folder of the game to '
                                'be matched')
    section_parser.set_defaults(func=find_section)


class ParserIniAction(argparse.Action):
    """Validates parameter values for CLI --ini and --to."""

    def __call__(self, parser, namespace, values, option_string=None):
        v = values[0]
        allowed = ', '.join(ARGS_INI_ALLOWED)
        msg = f"Got value: {v}. Was expecting one of: {allowed}"

        if v not in ARGS_INI_ALLOWED:
            raise ValueError(msg)

        setattr(namespace, self.dest, v)

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
    ini_native = args.scummvm == "native"
    short_name = args.shortname
    cfg_file = SCUMMVM_INI if ini_native else LR_SCUMMVM_INI
    ini = read_ini(cfg_file)

    # only sections which point to a game
    game_sects = [s for s in ini if 'path' in ini[s]]

    # output ini object
    ini_new = configparser.ConfigParser({}, OrderedDict)

    if short_name == "_all_":
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
            log.debug(f"Source section [{source_sect}] changed to "
                      f"[{short_name}].")

        # copy other sections
        [copy_gamesection(ini, ini_new, sect)
         for sect in [s for s in game_sects if '-' not in s]]
    else:
        if '-' in short_name:
            log.error(f"Game short name '{short_name}' may not contain dashes."
                      " Exiting.")
            sys.exit(-2)

        re_sect = rf"^{short_name}([-].*)?$"
        game_sections = [s for s in game_sects if re.search(re_sect, s)]

        if len(game_sections) == 0:
            log.warning(f"Section [{short_name}] not present in {cfg_file}."
                        " Exiting.")
            sys.exit(-1)

        if len(game_sections) == 1 and short_name in ini:
            log.info(f"Section [{short_name}] already unique in {cfg_file}."
                     " Exiting.")
            sys.exit(0)

        source_sect = default_variant(game_sections)
        copy_gamesection(ini, ini_new, short_name, source_sect)
        log.debug(f"Source section [{source_sect}] changed to "
                  f"[{short_name}].")
        # retain non dashed game sections
        [copy_gamesection(ini, ini_new, sect) for sect in ini.sections() if not
         sect.startswith(short_name)]

    copy_gamesection(ini, ini_new, 'scummvm')
    sorted_sections = sorted(ini_new._sections.items(),
                             key=cmp_to_key(cmp_scummvm_ini_sections))
    ini_new._sections = OrderedDict(sorted_sections)

    with open(cfg_file, 'w') as fh:
        ini_new.write(fh, space_around_delimiters=False)


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
    """Unifies variants of game sections to one game short name."""
    if not ini_new.has_section(short_name):
        ini_new.add_section(short_name)
        if not source_section:
            source_section = short_name
        for k, v in ini.items(source_section):
            if k == 'gameid':
                v = short_name  # e.g. for gameid=bladerunner-final
            ini_new.set(short_name, k, v)


def copy_entry(args):
    """Copies one section of a scummvm.ini file to another."""
    to_native = args.scummvm == "native"
    section_name = args.section
    if not to_native:
        # to libretro-scummvm
        from_file = SCUMMVM_INI
        to_file = LR_SCUMMVM_INI
    else:
        # to ScummVM native
        from_file = LR_SCUMMVM_INI
        to_file = SCUMMVM_INI

    from_ini = read_ini(from_file)
    to_ini = read_ini(to_file)

    # keep only game sections
    game_sections = [s for s in from_ini if 'path' in from_ini[s]]

    if not section_name in game_sections:
        log.warning(f"Source [{section_name}] not present in {from_file}."
                    " Exiting.")
        sys.exit(-1)

    if section_name in to_ini.sections() and not args.force:
        log.warning(f"Target [{section_name}] already present in {to_file}."
                    " Use --force to update. Exiting.")
        sys.exit(-1)

    section = from_ini[section_name]
    to_ini[section_name] = section

    tgt_path = to_ini[section_name]['path']
    if not to_native and not Path(tgt_path).is_absolute():
        # lr-scummvm requires absolute paths in scummvm.ini
        to_ini[section_name]['path'] = f"{Path(ROM_HOME).joinpath(tgt_path)}"

    with open(to_file, 'w') as fh:
        to_ini.write(fh)

    log.debug(f"Section [{section_name}] written to {to_file}.")


def check_entry(args):
    """Tests for existence of a given game id as ini section.

    Check is successful iff game id is exactly matched.
    Note that a [section] for a game may contain variants separated by dash
    e.g., for language or platform, like: tlj-win, which may hinder a match
    if given game id has no dash(es)."""
    ini_native = args.scummvm == "native"
    game_short_name = args.section
    cfg_file = SCUMMVM_INI if ini_native else LR_SCUMMVM_INI
    ini = read_ini(cfg_file)
    if game_short_name in ini.sections():
        print("present")
    else:
        print("absent")


def find_section(args):
    """Looks up scummvm.ini section by matching path= with provided folder."""
    ini = read_ini(SCUMMVM_INI)
    # keep only game sections
    game_sections = [s for s in ini if 'path' in ini[s]]
    match = []
    for sect in game_sections:
        path = ini[sect]['path']
        if path.endswith(args.folder):
            match.append(sect)
    print(f"{';'.join(match)}")


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
