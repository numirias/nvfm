" node plugins


" python3 plugins
call remote#host#RegisterPlugin('python3', resolve(expand('<sfile>:p:h') . '/../../'), [
      \ {'sync': v:true, 'name': 'CursorMoved', 'type': 'autocmd', 'opts': {'pattern': '*', 'eval': 'win_getid()'}},
      \ {'sync': v:true, 'name': 'NvfmEnter', 'type': 'function', 'opts': {}},
      \ {'sync': v:true, 'name': 'NvfmFilter', 'type': 'function', 'opts': {}},
      \ {'sync': v:true, 'name': 'NvfmHistory', 'type': 'function', 'opts': {}},
      \ {'sync': v:true, 'name': 'NvfmRefresh', 'type': 'function', 'opts': {}},
      \ {'sync': v:true, 'name': 'NvfmSet', 'type': 'function', 'opts': {}},
      \ {'sync': v:true, 'name': 'NvfmStartup', 'type': 'function', 'opts': {}},
     \ ])


" ruby plugins


" python plugins


