set nocompatible
set encoding=utf8
set laststatus=2
set scrolloff=5
set mouse=a
set noswapfile
set nowrap
set nofoldenable
" TODO Necessary?
set viminfo=
" Don't highlight matching brackets
NoMatchParen

set showtabline=2
set statusline=%{get(g:,'statusline'.winnr())}


hi CursorLine ctermbg=236 cterm=none
hi Cursor          ctermfg=red  ctermbg=red
" hi Normal       ctermfg=231 ctermbg=233 guifg=#ffffff guibg=#121212
hi VertSplit       ctermfg=244 ctermbg=none cterm=none
hi EndOfBuffer       ctermfg=244 ctermbg=none

hi TabLineFill ctermfg=white ctermbg=none cterm=none
hi TabLinePath ctermfg=white ctermbg=236 cterm=none
hi TabLineCurrent ctermfg=white ctermbg=236 cterm=bold
" hi TabLineSel ctermfg=blue ctermbg=236 cterm=none
" hi TabLine ctermfg=252 ctermbg=236 cterm=none
"
hi SelectedEntry ctermfg=none ctermbg=236


hi StatusLine      ctermfg=white ctermbg=236 cterm=none
hi StatusLineNC    ctermfg=white ctermbg=236 cterm=none

hi FileMeta ctermfg=246

noremap <silent>q :qall!<CR>
noremap <silent>l :call NvfmEnter(line('.'))<CR>
noremap <silent><CR> :call NvfmEnter(line('.'))<CR>
noremap <silent>h :call NvfmEnter('..')<CR>
noremap <silent>~ :call NvfmEnter($HOME)<CR>


let g:statusline1 = 'a'
let g:statusline2 = 'b'
let g:statusline3 = 'c'


function FileMetaHl()
    call matchadd('FileMeta', '.\%<19c')

endfunction

function Startup()
    "Name first buffer
    file nvfm_left
    setlocal buftype=nofile "right pane
    let num = bufnr('nvfm_main', 1)
    exe 'vertical sbuffer' .  num
    let num = bufnr('nvfm_right', 1)
    exe 'vertical sbuffer' .  num
    setlocal cursorline buftype=nofile "left pane
    call FileMetaHl()
    wincmd =
    exec 2 . "wincmd w"
    setlocal cursorline buftype=nofile "mid pane
    call FileMetaHl()

    call NvfmStartup()
    " setlocal nomodifiable
endfunction

au VimEnter * call Startup()

au VimResized * wincmd =


function ViewFile(filename)
    exec 3 "wincmd w"
    exec "view! " . a:filename
    wincmd p
endfunction

function ViewHexdump()
    exec 3 "wincmd w"
    "Otherwise, vim wants to to save the file before closing the buffer
    setlocal buftype=nofile
    "Display unprintable characters as <00> instead of ^C
    setlocal display=uhex
    setlocal syntax=xxd
    wincmd p
endfunction


nnoremap <silent>e :call ViewFile()<CR>
