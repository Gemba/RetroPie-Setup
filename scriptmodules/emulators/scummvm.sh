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
rp_module_licence="GPL2 https://raw.githubusercontent.com/scummvm/scummvm/master/COPYING"
###rp_module_repo="git https://github.com/scummvm/scummvm.git v2.2.0"
rp_module_repo="git https://github.com/scummvm/scummvm.git master"
rp_module_section="opt"
rp_module_flags="sdl2"

function depends_scummvm() {
    local depends=(
        libmpeg2-4-dev libogg-dev libvorbis-dev libflac-dev libmad0-dev libpng-dev
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
    local params=(
        --enable-release --enable-vkeybd
        --disable-debug --disable-eventrecorder
        --prefix="$md_inst" --opengl-mode=auto
    )
    isPlatform "gles" && params+=(--force-opengl-game-es2)
    ./configure "${params[@]}"
    make clean
    make
    strip "$md_build/scummvm"
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
    cat > "$romdir/scummvm/+Start $name.sh" << _EOF_
#! /bin/bash

folder="\$1"

emu_home="$md_inst"
scummvm_bin="\$emu_home/bin/scummvm"
rom_home="$romdir/scummvm"
scummvm_ini="\$HOME/.config/scummvm/scummvm.ini"

pushd "\$rom_home" >/dev/null

params=(
  --fullscreen
  --joystick=0
  --gfx-mode=hq3x
  --extrapath="\$emu_home/extra"
  --path="\$folder"
  --stretch-mode=stretch
)
# enable for verbose log
#params+=(--debuglevel=3)

# expect <game_dir>/<game_dir>.svm
game_id=\$(cat "\$rom_home/\$folder/\$folder.svm" | xargs)

# check if gameid (=short game name) is present (maybe absent on first start)
if [[ -z "\$game_id" ]] ; then
  # first column of --detect after GameID contains <engine>:<gameid>
  game_id=\$("\$scummvm_bin" --detect --path="\$folder" | grep -A 2 "GameID" | tail +3 | cut -f 1 -d ' ' | cut -f 2 -d ':')
  echo "\$game_id" > "\$rom_home/\$folder/\$folder.svm"
fi

if [[ \$(grep -c "gameid=\$game_id" "\$scummvm_ini") -eq 0 ]]; then
  # create an entry in ~/.config/scummvm/scummvm.ini for customisation
  "\$scummvm_bin" --add --path="\$folder" >/dev/null 2>&1
fi

"\$scummvm_bin" "\${params[@]}" "\$game_id"

popd >/dev/null
_EOF_

    chown $user:$user "$romdir/scummvm/+Start $name.sh"
    chmod u+x "$romdir/scummvm/+Start $name.sh"

    addEmulator 1 "$md_id" "scummvm" "bash $romdir/scummvm/+Start\ $name.sh %BASENAME%"
    addSystem "scummvm"
}
