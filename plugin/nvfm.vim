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


function Startup()
    setlocal bufhidden=wipe
    vsplit
    vsplit
    exec 2 . "wincmd w"

    call NvfmStartup()
    " setlocal nomodifiable
endfunction

au VimEnter * call Startup()

au VimResized * wincmd =


nnoremap <silent>e :call ViewFile()<CR>
