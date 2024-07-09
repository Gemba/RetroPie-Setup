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
rp_module_repo="git https://github.com/scummvm/scummvm.git v2.8.1"
rp_module_section="opt"
rp_module_flags="sdl2"

function depends_scummvm() {
    local depends=(
        liba52-0.7.4-dev libmpeg2-4-dev libogg-dev libvorbis-dev libflac-dev libgif-dev libmad0-dev libpng-dev
        libtheora-dev libfaad-dev libfluidsynth-dev libfreetype6-dev zlib1g-dev
        libjpeg-dev libasound2-dev libcurl4-openssl-dev libmikmod-dev libvpx-dev
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
        --prefix="$md_inst"
        --enable-release --enable-vkeybd
        --disable-debug --disable-eventrecorder --disable-sonivox
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

    # copy python helper
    cp "$scriptdir/scriptmodules/supplementary/scummvm/scummvm_helper.py" "$romdir/scummvm/"
    chmod a+x "$romdir/scummvm/scummvm_helper.py"

    # Create startup script
    rm -f "$romdir/scummvm/+Launch GUI.sh"
    local name="ScummVM"
    [[ "$md_id" == "scummvm-sdl1" ]] && name="ScummVM-SDL1"
    cat > "$romdir/scummvm/+Start $name.sh" << _EOF_
#! /usr/bin/env bash

# input from runcommand %BASENAME%
base_name="\$1"
# <base_name>.svm and <base_name>/ folder expected to be siblings on filesystem

emu_home="$md_inst"
scummvm_bin="\$emu_home/bin/scummvm"
rom_home="$romdir/scummvm"
scummvm_ini="\$HOME/.config/scummvm/scummvm.ini"
# avoid fail when romfolder is mount -o noexec
scummvm_helper="python3 \"\$rom_home/scummvm_helper.py\""

pushd "\$rom_home" >/dev/null

params=(
  --fullscreen
  --joystick=0
)

if ! grep -qs extrapath "\$scummvm_ini"; then
    params+=(--extrapath="\$emu_home/extra")
fi

# enable for verbose log
#params+=(--debuglevel=3)

if [[ -n "\$base_name" ]] ; then
    # launch was via *.svm file, append extension and read file content
    game_id=\$(xargs < "\$rom_home/\${base_name}.svm")

    # expect game id in *.svm file
    # check if game id is present in *.svm file (maybe absent on first start)
    if [[ -z "\$game_id" ]] ; then
        # absent, try detection
        # scrape --detect output: it returns game id without engine
        game_id=\$("\$scummvm_bin" --detect --path="\$base_name" | grep -A 2 "GameID" | tail +3 | cut -f 1 -d ' ' | cut -f 2 -d ':')
        if [[ -z "\$game_id" ]] ; then
            # if game_id is empty at this point, then detection was not successful
            cat << EOF
FATAL: Detecting game in directory "\$base_name" failed. Game will not start.
Maybe a required game file is missing? Check https://wiki.scummvm.org for this
game. Else try running this command to identify any other possible cause:
    \$scummvm_bin --detect --path="\$rom_home/\$base_name" --debuglevel=3
EOF
            exit 1
        else
            # add game id to ~/.config/scummvm/scummvm.ini for customisation
            "\$scummvm_bin" --add --path="\$base_name" >/dev/null 2>&1
            # make sure any added game id variant (i.e. with dashed suffix) is
            # mapped to [<game_id>]
            "\$scummvm_helper" uniq "\$game_id"
            echo "\$game_id" > "\$rom_home/\${base_name}.svm"
        fi
    else
        # some sanity checks if user has manually added a wrong value to *.svm file
        found_in_scummvm_ini=\$("\$scummvm_helper" checkentry "\$game_id")
        if [[ "absent" == "\$found_in_scummvm_ini" ]] ; then
            # add to ~/.config/scummvm/scummvm.ini for customisation
            "\$scummvm_bin" --add --path="\$base_name" >/dev/null 2>&1
            # make sure any added game id variant (i.e. with dashed suffix) is
            # mapped to [<game_id>] and any dash in the *.svm value is cut off.
            tgt=\$(echo "\$game_id" | cut -f 1 -d '-')
            if ! "\$scummvm_helper" uniq "\$tgt" ; then
                # most likely an invalid gameid given in *.svm
                params+=(--path="\$base_name")
                cat << EOF
WARNING: Game id [\$game_id] has no corresponding section in
    \$scummvm_ini
Please empty contents of \${base_name}.svm and restart game to fix.
If the game can be started now, the game config is not saved.
EOF
            else
                # write corrected game id if the previous had a dash
                echo "\$tgt" > "\$rom_home/\$base_name.svm"
                game_id="\$tgt"
            fi
        fi
    fi
else
    # force directly detour into UI (to add game / mass add in UI), most likely at initial start of ScummVM.
    game_id=""
fi

ini_pre=\$(grep "\[" "\$scummvm_ini" | sort | sha256sum)

"\$scummvm_bin" "\${params[@]}" "\$game_id"

# detecting if game sections added/removed via ScummVM UI
ini_post=\$(grep "\[" "\$scummvm_ini" | sort | sha256sum)

if [[ "\${ini_pre}" != "\${ini_post}" ]] ; then
    # run when returning from ScummVM UI Game add... or Mass add...
    "\$scummvm_helper" uniq _all_
    "\$scummvm_helper" createsvm
fi

popd >/dev/null
_EOF_
    chown "$user":"$user" "$romdir/scummvm/+Start $name.sh"
    chmod u+x "$romdir/scummvm/+Start $name.sh"

    addEmulator 1 "$md_id" "scummvm" "bash $romdir/scummvm/+Start\ $name.sh %BASENAME%"
    addSystem "scummvm"
}
