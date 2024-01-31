#!/usr/bin/env bash

# This file is part of The RetroPie Project
#
# The RetroPie Project is the legal property of its developers, whose names are
# too numerous to list here. Please refer to the COPYRIGHT.md file distributed with this source.
#
# See the LICENSE.md file at the top-level directory of this distribution and
# at https://raw.githubusercontent.com/RetroPie/RetroPie-Setup/master/LICENSE.md
#

rp_module_id="edna"
rp_module_desc="Module for the point and click adventure 'Edna and Harvey: The breakout'"
rp_module_licence="PROP"
rp_module_section="exp"
rp_module_flags="all"

function depends_edna() {
    getDepends xorg openjdk-8-jre liblwjgl-java rtkit libopenal1 pulseaudio
}

function sources_edna() {
    echo
    #gitPullOrClone "$md_build" https://github.com/kcat/openal-soft.git
}

function build_edna() {
    echo
    #cd build
    #cmake ..
    #make -j4
    #md_ret_require="$md_build/build/openal-info"
}

function install_edna() {
    echo
    #mkdir -p "$romdir/ports/edna/lib/"
    #rm -f "$romdir/ports/edna/lib"/*.so

    #cp -a "$md_build/build"/libopenal.so* "$romdir/ports/edna/lib/"
    #chown -h pi:pi "$romdir/ports/edna/lib"/libopenal.so*
}

function remove_edna() {
    echo ;
}

function configure_edna() {
    addPort "$md_id" "edna" "Edna & Harvey: The Breakout" "XINIT:$md_inst/EdnaBreakout.sh"
    mkdir -p "$md_inst"

# TODO
#/etc/security/limits.conf
#pi hard rtprio 99
#pi soft rtprio 99

# TODO check with latest installed EdnaBreakout.sh

    cat >"$md_inst/EdnaBreakout.sh" << _EOF_
#!/bin/bash
systemctl --user start pulseaudio
xset -dpms s off s noblank
pushd "$romdir/ports/edna"
java -jar -Xms256M -Xmx512M\
 -Djava.library.path=lib/:/usr/lib/jni/:/usr/lib/arm-linux-gnueabihf/\
 Edna.jar
systemctl --user stop pulseaudio.service pulseaudio.socket
_EOF_
    chmod +x "$md_inst/EdnaBreakout.sh"
}
