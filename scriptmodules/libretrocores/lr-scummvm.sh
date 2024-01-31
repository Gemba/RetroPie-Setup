#!/usr/bin/env bash

# This file is part of The RetroPie Project
#
# The RetroPie Project is the legal property of its developers, whose names are
# too numerous to list here. Please refer to the COPYRIGHT.md file distributed with this source.
#
# See the LICENSE.md file at the top-level directory of this distribution and
# at https://raw.githubusercontent.com/RetroPie/RetroPie-Setup/master/LICENSE.md
#

rp_module_id="lr-scummvm"
rp_module_desc="ScummVM port for libretro"
rp_module_help="Copy your ScummVM games to $romdir/scummvm\n\nSee https://retropie.org.uk/docs/ScummVM/#example\nfor expected folders and files."
rp_module_licence="GPL3 https://raw.githubusercontent.com/libretro/scummvm/master/COPYING"
rp_module_repo="git https://github.com/libretro/scummvm.git master"
rp_module_section="exp"

function depends_lr-scummvm() {
    getDepends zip
}

function sources_lr-scummvm() {
    gitPullOrClone
}

function build_lr-scummvm() {
    cd backends/platform/libretro
    make clean
    make USE_MT32EMU=1
    make datafiles
    md_ret_require="$md_build/backends/platform/libretro/scummvm_libretro.so"
}

function install_lr-scummvm() {
    md_ret_files=(
        "backends/platform/libretro/scummvm_libretro.so"
        "backends/platform/libretro/scummvm.zip"
        "COPYING"
    )
}

function configure_lr-scummvm() {
    addEmulator 0 "$md_id" "scummvm" "$md_inst/romdir-launcher.sh %ROM%"
    addSystem "scummvm"
    [[ "$md_mode" == "remove" ]] && return

    # ensure rom dir and system retroconfig
    mkRomDir "scummvm"
    defaultRAConfig "scummvm"

    # unpack the data files to system dir
    runCmd unzip -q -o "$md_inst/scummvm.zip" -d "$biosdir"
    chown -R $user:$user "$biosdir/scummvm"

    local scummvm_ini="$biosdir/scummvm.ini"
    # basic initial configuration (if config file not found)
    if [[ ! -f "$scummvm_ini" ]]; then
        echo "[scummvm]" > "$scummvm_ini"
        iniConfig "=" "" "$scummvm_ini"
        iniSet "extrapath" "$biosdir/scummvm/extra"
        iniSet "themepath" "$biosdir/scummvm/theme"
        iniSet "soundfont" "$biosdir/scummvm/extra/Roland_SC-55.sf2"
        iniSet "gui_theme" "scummremastered"
        iniSet "subtitles" "true"
        iniSet "multi_midi" "true"
        iniSet "gm_device" "fluidsynth"
        chown $user:$user "$scummvm_ini"
    fi

    # enable speed hack core option if running in arm platform
    isPlatform "arm" && setRetroArchCoreOption "scummvm_speed_hack" "enabled"

    # copy python helper only if not present or if there is a more recent dated version
    rsync -a "$scriptdir/scriptmodules/supplementary/scummvm/scummvm_helper.py" "$romdir/scummvm/"
    chmod a+x "$romdir/scummvm/scummvm_helper.py"

    # create retroarch launcher for lr-scummvm with support for rom directories
    # containing svm files inside (for direct game directory launching in ES)
    cat > "$md_inst/romdir-launcher.sh" << _EOF_
#!/usr/bin/env bash

# contains absolute path to file
ROM="\$1" ; shift
scummvm_ini="$scummvm_ini"

# \$ROM is a *.svm file in ~/RetroPie/roms/scummvm
game_id=\$(xargs < "\$ROM")
fn=\$(basename "\$ROM")
folder="\${fn%.*}"
path=\$(dirname "\$ROM")
scummvm_helper="python3 \"\$path/scummvm_helper.py\""

if [[ -n "\$game_id" ]] ; then
    # remap to *.scummvm in game subfolder for libretro
    # libretro ScummVM expects *.scummvm file within game dir
    ROM="\$path/\$folder/\${folder}.scummvm"
    if [[ ! -e "\$ROM" ]] ; then
        # create symbolic link *.scummvm -> ../*.svm
        pushd "\$path/\$folder" > /dev/null
        if ! ln -s "../\$fn" "\${folder}.scummvm" ; then
            # filesystem does not allow symlinks (e.g. mounted vFAT volume)
            cp -f "../\$fn" "\${folder}.scummvm"
        fi
        popd > /dev/null
    fi
    # check if [game_id] exists in libretro's scummvm.ini
    # LR scummvm.ini is usually at "$scummvm_ini"
    ini_config_lr=\$("\$scummvm_helper" checkentry "\$game_id" --ini libretro)
    if [[ "\$ini_config_lr" == "absent" ]] ; then
        # not present in libretro's scummvm.ini
        # 'copyentry' exits if there is no game_id in the source scummvm.ini
        "\$scummvm_helper" copyentry "\$game_id"
    fi
else
    # force failsafe to autodetect in libretro as there is no ScummVM config to use
    # NB: Only files with suffix .scummvm will be evaluated by libretro.cpp other
    # files will trigger autodetect mode. Any game specific changes will not be saved
    # in libretro's $scummvm_ini
    ROM="\$path/\$folder/\${folder}.autodetect"
fi

echo "ROM parameter for libretro: \$ROM" >> /dev/shm/runcommand.log

# keep hash to detect any UI added games
ini_pre=\$(grep "\[" "\$scummvm_ini" | sort | sha256sum)

$emudir/retroarch/bin/retroarch \\
    -L "$md_inst/scummvm_libretro.so" \\
    --config "$md_conf_root/scummvm/retroarch.cfg" \\
    "\$ROM" "\$@"

# detecting if game sections added/removed via ScummVM UI
ini_post=\$(grep "\[" "\$scummvm_ini" | sort | sha256sum)

if [[ "\${ini_pre}" != "\${ini_post}" ]] ; then
    # run when returning from ScummVM UI Game 'Add...' or 'Mass add...'
    "\$scummvm_helper" uniq _all_ --ini libretro
    "\$scummvm_helper" createsvm
fi
_EOF_
    chmod +x "$md_inst/romdir-launcher.sh"
}
