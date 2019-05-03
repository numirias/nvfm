#!/bin/bash
#
# Generates the remote plugin manifest

HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

tmp=$(mktemp -d --suffix _nvfm)
rplugin_path=$(realpath $HERE/../src/nvfm)

mkdir -p $tmp/nvfm/rplugin/python3
ln -s $rplugin_path $tmp/nvfm/rplugin/python3/nvfm

export NVIM_RPLUGIN_MANIFEST=$tmp/rplugin.vim
export NVFM_RUNTIME=$tmp/nvfm/
nvim --headless -u <(cat <<-END
    let &rtp .= "," . \$NVFM_RUNTIME
    au VimEnter * UpdateRemotePlugins | qall!
END
)

path="resolve(expand('<sfile>:p:h') . '/../../')"
cat $NVIM_RPLUGIN_MANIFEST | sed "s,'$rplugin_path',$path,g" > $HERE/../src/nvfm/runtime/plugin/manifest.vim

rm -rf $tmp
