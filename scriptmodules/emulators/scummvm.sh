#!/usr/bin/env bash

# This file is part of The RetroPie Project
#
# The RetroPie Project is the legal property of its developers, whose names are
# too numerous to list here. Please refer to the COPYRIGHT.md file distributed with this source.
#
# See the LICENSE.md file at the top-level directory of this distribution and
# at https://raw.githubusercontent.com/RetroPie/RetroPie-Setup/master/LICENSE.md
#

rp_module_id="scummvm"
rp_module_desc="ScummVM"
rp_module_help="Copy your ScummVM games to $romdir/scummvm.\nSee https://retropie.org.uk/docs/ScummVM/#example\nfor expected folders and files."
rp_module_licence="GPL3 https://raw.githubusercontent.com/scummvm/scummvm/master/COPYING"
rp_module_repo="git https://github.com/scummvm/scummvm.git v2.7.0"
rp_module_section="opt"
rp_module_flags="sdl2"

function depends_scummvm() {
    local depends=(
        liba52-0.7.4-dev libmpeg2-4-dev libogg-dev libvorbis-dev libflac-dev libgif-dev libmad0-dev libpng-dev
        libtheora-dev libfaad-dev libfluidsynth-dev libfreetype6-dev zlib1g-dev
        libjpeg-dev libasound2-dev libcurl4-openssl-dev
    )
    if isPlatform "vero4k"; then
        depends+=(vero3-userland-dev-osmc)
    fi
    if [[ "$md_id" == "scummvm-sdl1" ]]; then
        depends+=(libsdl1.2-dev)
    else
        depends+=(libsdl2-dev)
    fi
    getDepends "${depends[@]}"
}

function sources_scummvm() {
    gitPullOrClone
}

function build_scummvm() {
    rpSwap on 750
    local params=(
        --enable-release --enable-vkeybd
        --disable-debug --disable-eventrecorder --prefix="$md_inst"
    )
    isPlatform "rpi" && isPlatform "32bit" && params+=(--host=raspberrypi)
    isPlatform "rpi" && [[ "$md_id" == "scummvm-sdl1" ]] && params+=(--opengl-mode=none)
    # stop scummvm using arm-linux-gnueabihf-g++ which is v4.6 on
    # wheezy and doesn't like rpi2 cpu flags
    if isPlatform "rpi"; then
        if [[ "$md_id" == "scummvm-sdl1" ]]; then
            SDL_CONFIG=sdl-config CC="gcc" CXX="g++" ./configure "${params[@]}"
        else
            CC="gcc" CXX="g++" ./configure "${params[@]}"
        fi
    else
        ./configure "${params[@]}"
    fi
    make clean
    make
    strip "$md_build/scummvm"
    rpSwap off
    md_ret_require="$md_build/scummvm"
}

function install_scummvm() {
    make install
    mkdir -p "$md_inst/extra"
    cp -v backends/vkeybd/packs/vkeybd_*.zip "$md_inst/extra"
}

function configure_scummvm() {
    mkRomDir "scummvm"

    local dir
    for dir in .config .local/share; do
        moveConfigDir "$home/$dir/scummvm" "$md_conf_root/scummvm"
    done

    # Create startup script
    rm -f "$romdir/scummvm/+Launch GUI.sh"
    local name="ScummVM"
    [[ "$md_id" == "scummvm-sdl1" ]] && name="ScummVM-SDL1"

    local scummvm_ini="$home/.config/scummvm/scummvm.ini"
    if [[ ! -f "$scummvm_ini" ]]; then
        echo "[scummvm]" > "$scummvm_ini"
        iniConfig "=" "" "$scummvm_ini"
        iniSet "extrapath" "$md_inst/extra"
        iniSet "fullscreen" "true"
        iniSet "gui_theme" "scummremastered"
        iniSet "subtitles" "true"
        iniSet "multi_midi" "true"
        chown $user:$user "$scummvm_ini"
    fi

    cat > "$romdir/scummvm/+Start $name.sh" << _EOF_
#! /usr/bin/env bash

# input from runcommand is %BASENAME%
base_name="\$1"
# <base_name>.svm and <base_name>/ folder expected to be siblings on filesystem

scummvm_bin="$md_inst/bin/scummvm"
rom_home="$romdir/scummvm"
scummvm_ini="\$HOME/.config/scummvm/scummvm.ini"

params=(
  --joystick=0
)
# enable --debuglevel for verbose log
#params+=(--debuglevel=3)

function ini_get_game_sections() {
    # gets all game sections from scummvm.ini
    echo \$(sed -n 's/^[ \t]*\[\(.*\)\].*/\1/p' "\$scummvm_ini" | grep -v scummvm)
}

function ini_get_section_value() {
    # gets the value from a game sections key from scummvm.ini
    echo \$(sed -n "/^[ \t]*\[\$1\]/,/\[/s/^[ \t]*\$2[ \t]*=[ \t]*//p" "\$scummvm_ini")
}

function ini_del_section() {
    # removes a section and its key=values from scummvm.ini
    sed -i "/^\[\$1\]/,/^$/d" "\$scummvm_ini"
}

function validate_game_id() {
    # some sanity checks if *.svm is empty or user has accidentally added a wrong value to *.svm file
    if [[ -z "\$game_id" || \$(grep -c "\[\$game_id\]" "\$scummvm_ini") -eq 0 ]] ; then
        # no game_id or no excact match with sections in scummvm.ini
        # add to ~/.config/scummvm/scummvm.ini for customisation
        tgt=\$("\$scummvm_bin" --add --path="\$base_name" | grep --max-count=1 "Target:" | cut -f 2 -d ':' | xargs)
        if [[ -z "\$tgt" ]] ; then
            cat << EOF
ERROR: Game in "\${base_name}/" could not be added. Review your
    \$scummvm_ini
file. If it is already added, remove the section(s).
EOF
            exit 1
        fi
        # provide proper target to ensure launch
        game_id="\$tgt"
    fi
}

cd "\$rom_home"
grep "\[" "\$scummvm_ini" | sort > /dev/shm/_scummvm.ini.pre

if [[ -n "\$base_name" ]] ; then
    # launch was via <base_name>.svm file, append extension .svm and read file content
    # sunny day: expected to be a valid game_id
    game_id=\$(xargs < "\$rom_home/\${base_name}.svm")

    if [[ -z "\$game_id" ]] ; then
        # no game_id, try detect
        game_id=\$("\$scummvm_bin" --detect --path="\$base_name" | sed /GameID/,/---/d | head -1 | awk -F '[ :]' '{print \$2}')
        if [[ -z "\$game_id" ]] ; then
            cat << EOF
FATAL: Detecting game in directory "\$base_name" failed. Game will not start.
Maybe a required game file is missing? Check https://wiki.scummvm.org for this
game. Else try running this command to identify any other possible cause:
    \$scummvm_bin --detect --path="\$rom_home/\$base_name" --debuglevel=3
EOF
            exit 1
        else
            echo "\$game_id" > "\$rom_home/\${base_name}.svm"
        fi
    fi
    # at this point it is safe that
    # - game folder contains a detectable game when game id was empty or
    # - game id in svm file is not empty
    validate_game_id
else
    # force directly detour into UI (to add game / mass add in UI), most likely
    # at initial start of ScummVM via "+Start ScummVM" (and no ROM file) entry from ES.
    game_id=""
fi

# Launch the game
echo "\$scummvm_bin" "\${params[@]}" "\$game_id" >> /dev/shm/runcommand.log
"\$scummvm_bin" "\${params[@]}" "\$game_id"

grep "\[" "\$scummvm_ini" | sort > /dev/shm/_scummvm.ini.post
diff /dev/shm/_scummvm.ini.pre /dev/shm/_scummvm.ini.post > /dev/null

if [[ \$? -eq 1 ]] ; then
    # detected game sections added/removed via ScummVM UI
    # run when returning from ScummVM UI Game add... or Mass add...

    echo "Start: Sync scummvm.ini changes. \$(date)" >> /dev/shm/runcommand.log
    # 1. delete surplus entries of mass add (demos, false positives in subfolders, ...)
    declare -A paths=()
    echo "Stage 1: Surplus ini sections removal" >> /dev/shm/runcommand.log
    for tgt in \$(ini_get_game_sections) ; do
        p=\$(ini_get_section_value \$tgt path)
        if [[ "\$p" = /* && "\${p%/*}" != "\$rom_home" ]]  ; then
            echo "S1: Deleting #0 \$tgt" >> /dev/shm/runcommand.log
            rm -f "\$p.svm"
            ini_del_section \$tgt
        else
            p_key=\$(echo \$p | tr -cd '[:alnum:]')
            if [[ ! -v paths["\$p_key"] ]] ; then
                paths["\$p_key"]="\$tgt"
            else
                echo "S1: Deleting #1 \$tgt" >> /dev/shm/runcommand.log
                ini_del_section \$tgt
            fi
        fi
    done

    # 2. remove orphaned *.svm files (=no peer in scummvm.ini)
    echo "Stage 2: Orphan removal" >> /dev/shm/runcommand.log
    if [[ "\$(find \$rom_home -maxdepth 1 -name '*.svm' | wc -l)" -gt 0 ]] ; then
        orphaned=\$(comm -2 -3 <(cat *.svm | sort) <(ini_get_game_sections | tr " " "\n" | sort))
        for tgt in \$orphaned ; do
            echo "S2: Orphaned found \$tgt" >> /dev/shm/runcommand.log
            grep -l \$(echo \$tgt | awk -F '-' '{print \$1}') *.svm | xargs -I{} rm -f {}
        done
    fi

    # 3. rename [targets] to plain gameids
    echo "Stage 3: Rename [targets] to plain gameids" >> /dev/shm/runcommand.log
    for tgt in \$(ini_get_game_sections) ; do
        gid=\$(ini_get_section_value \$tgt gameid)
        if [[ "\$tgt" != "\$gid" ]] ; then
            sect="[\$gid]"
            # get all key=values from [\$tgt]
            props=\$(sed -n "/^[ \t]*\[\$tgt\]/,/\[/s/^[ \t]*\([^#; \t][^ \t=]*\).*=[ \t]*\(.*\)/\1=\2/p" "\$scummvm_ini")
            ini_del_section \$tgt
            printf "\$sect\n\$props\n\n" >> "\$scummvm_ini"
            echo "S3: Moved #2 [\$tgt] -> [\$gid]" >> /dev/shm/runcommand.log
        fi
    done

    # 4. create *.svm file for each game without one and write game id as content
    echo "Stage 4: Create *.svm files" >> /dev/shm/runcommand.log
    for gid in \$(ini_get_game_sections) ; do
        p=\$(ini_get_section_value \$gid path)
        svm_file="\$p.svm"
        if [[ ! -f "\$svm_file" || -z \$(xargs < "\$svm_file") ]] ; then
            echo "\$gid" > "\$svm_file"
        fi
    done
    # sanity checks
    only_in_svm=\$(comm -2 -3 <(cat *.svm | sort) <(ini_get_game_sections | tr " " "\n" | sort))
    only_in_ini=\$(comm -1 -3 <(cat *.svm | sort) <(ini_get_game_sections | tr " " "\n" | sort))
    if [[ "\$only_in_svm" != "\$only_in_ini" ]] ; then
        cat << EOF
WARNING: Inconsitencies detected. Review/adjust svm files and ini manually.
  Game IDs only in *.svm files:
\$only_in_svm
  Only in \$scummvm_ini:
\$only_in_ini
EOF
    fi
fi
echo "Done. \$(date)" >> /dev/shm/runcommand.log
_EOF_
    chown "$user":"$user" "$romdir/scummvm/+Start $name.sh"
    chmod u+x "$romdir/scummvm/+Start $name.sh"

    addEmulator 1 "$md_id" "scummvm" "bash $romdir/scummvm/+Start\ $name.sh %BASENAME%"
    addSystem "scummvm"
}
