set encoding=utf8
set laststatus=2
set scrolloff=5
set mouse=nc
set noswapfile
set nowrap
set bufhidden=hide
" TODO Necessary?
set viminfo="NONE"
set shada="NONE"
" Don't highlight matching brackets
NoMatchParen

set showtabline=2
set statusline=%{get(g:,'statusline'.winnr())}
set fillchars=eob:\ ,fold:-
set foldenable
set foldminlines=0
set foldtext=Foldtext()


hi CursorLine ctermbg=236 cterm=none
hi Cursor          ctermfg=red  ctermbg=red
" hi Normal       ctermfg=231 ctermbg=233 guifg=#ffffff guibg=#121212
hi VertSplit       ctermfg=244 ctermbg=none cterm=none
hi EndOfBuffer       ctermfg=244 ctermbg=none
hi Folded ctermfg=239 ctermbg=none

hi TabLineFill ctermfg=white ctermbg=none cterm=none
hi TabLinePath ctermfg=white ctermbg=236 cterm=none
hi TabLineCurrent ctermfg=white ctermbg=236 cterm=bold
" hi TabLineSel ctermfg=blue ctermbg=236 cterm=none
" hi TabLine ctermfg=252 ctermbg=236 cterm=none
"
hi SelectedEntry ctermfg=none ctermbg=236


hi StatusLine      ctermfg=white ctermbg=236 cterm=none
hi StatusLineNC    ctermfg=white ctermbg=236 cterm=none

hi FileMeta ctermfg=243
hi NvfmMessage ctermfg=246


noremap <silent>a <nop>
noremap <silent>A <nop>
noremap <silent>d <nop>
noremap <silent>D <nop>
noremap <silent>i <nop>
noremap <silent>I <nop>
noremap <silent>o <nop>
noremap <silent>O <nop>
noremap <silent>p <nop>
noremap <silent>P <nop>
noremap <silent>r <nop>
noremap <silent>R <nop>
noremap <silent>s <nop>
noremap <silent>S <nop>
noremap <silent>u <nop>
noremap <silent>U <nop>

noremap <silent>q :qall!<CR>
noremap <silent>Q :qall!<CR>
noremap <silent> <S-j> 4j
noremap <silent> <S-k> 4k

noremap <silent>l :call NvfmEnter()<CR>
noremap <silent>L :call NvfmEnter(v:null, v:true)<CR>
noremap <silent><CR> :call NvfmEnter()<CR>
noremap <silent>h :call NvfmEnter('..')<CR>
noremap <silent>~ :call NvfmEnter($HOME)<CR>
noremap <silent>gh :call NvfmEnter($HOME)<CR>
noremap <silent>gr :call NvfmEnter('/')<CR>

nnoremap <silent>r :call NvfmRefresh()<CR>
nnoremap <silent>e :call ViewFile()<CR>

noremap <silent>b :call NvfmHistory(-1)<CR>
noremap <silent>B :call NvfmHistory(1)<CR>

noremap <silent>sa :call NvfmSet('sort', 'alpha') \| call NvfmRefresh()<CR>
noremap <silent>sA :call NvfmSet('sort', 'alpha_reverse') \| call NvfmRefresh()<CR>
noremap <silent>st :call NvfmSet('sort', 'last_modified') \| call NvfmRefresh()<CR>
noremap <silent>sT :call NvfmSet('sort', 'last_modified_reverse') \| call NvfmRefresh()<CR>
noremap <silent>ss :call NvfmSet('sort', 'size') \| call NvfmRefresh()<CR>
noremap <silent>sS :call NvfmSet('sort', 'size_reverse') \| call NvfmRefresh()<CR>

noremap <silent>Fa :call NvfmSet('time_format', 'ago') \| call NvfmRefresh()<CR>
noremap <silent>Ft :call NvfmSet('time_format', '%Y-%m-%d %H:%m') \| call NvfmRefresh()<CR>
noremap <silent>Fl :call NvfmSet('time_format', '%c') \| call NvfmRefresh()<CR>

noremap <silent>/ :call NvfmFilterInput()<CR>
noremap <silent>f :call NvfmFilterInput()<CR>
" Eliminate all folds
noremap <silent><ESC> :call NvfmFilter(v:null)<CR>


function Foldtext()
    return '(+' . (v:foldend - v:foldstart + 1) . ') '
endfunction


function NvfmFilterInput()
    let l:input = input('find> ', '')
    if len(l:input)
        echo "\rfind: " . l:input
    else
        call NvfmFilter(v:null)
    endif
endfunction


let g:statusline1 = 'a'
let g:statusline2 = 'b'
let g:statusline3 = 'c'


function Startup()
    vsplit
    vsplit
    exec 2 . "wincmd w"

    " TODO Rename
    call NvfmStartup()
    " [Set options here]
    call NvfmEnter($NVFM_START_PATH)
endfunction

au VimEnter * call Startup()

au VimResized * wincmd =

au CmdlineChanged @ call NvfmFilter(getcmdline())
