" node plugins


" python3 plugins
call remote#host#RegisterPlugin('python3', resolve(expand('<sfile>:p:h') . '/../../'), [
      \ {'sync': v:true, 'name': 'CursorMoved', 'type': 'autocmd', 'opts': {'pattern': '*'}},
      \ {'sync': v:true, 'name': 'NvfmEnter', 'type': 'function', 'opts': {}},
      \ {'sync': v:true, 'name': 'NvfmStartup', 'type': 'function', 'opts': {}},
     \ ])


" ruby plugins


" python plugins

