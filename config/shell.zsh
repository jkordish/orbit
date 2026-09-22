# Managed by orbit. Existing shell configuration is preserved.
# This file is sourced from ~/.zshrc and intentionally keeps all interactive
# behavior in one owner: no framework, plugin manager, or hidden network work.

if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

typeset -U path PATH
path=("$HOME/.local/bin" "$HOME/.cargo/bin" "${HOMEBREW_PREFIX:-/opt/homebrew}/opt/rustup/bin" "${HOMEBREW_PREFIX:-/opt/homebrew}/opt/libpq/bin" $path)
path=("${KREW_ROOT:-$HOME/.krew}/bin" $path)

# Keep command history useful across terminals without putting it in the repo.
export HISTFILE="${HISTFILE:-${XDG_STATE_HOME:-$HOME/.local/state}/zsh/history}"
if [[ ! -d "${HISTFILE:h}" ]]; then
  mkdir -p -m 700 "${HISTFILE:h}"
fi
export HISTSIZE=100000
export SAVEHIST=50000
setopt APPEND_HISTORY
setopt EXTENDED_HISTORY
setopt HIST_EXPIRE_DUPS_FIRST
setopt HIST_FIND_NO_DUPS
setopt HIST_IGNORE_ALL_DUPS
setopt HIST_IGNORE_DUPS
setopt HIST_IGNORE_SPACE
setopt HIST_REDUCE_BLANKS
setopt INC_APPEND_HISTORY
setopt SHARE_HISTORY

# Make directory movement forgiving while keeping every change explicit.
setopt AUTO_CD
setopt AUTO_PUSHD
setopt PUSHD_IGNORE_DUPS
setopt PUSHD_SILENT
setopt INTERACTIVE_COMMENTS
setopt NO_BEEP
setopt NO_FLOW_CONTROL
setopt PROMPT_SUBST
setopt COMPLETE_IN_WORD
setopt ALWAYS_TO_END

if [[ -z ${EDITOR:-} ]]; then
  if (( $+commands[code] )); then
    export EDITOR='code --wait'
  else
    export EDITOR=vi
  fi
fi
export VISUAL="${VISUAL:-$EDITOR}"
export PAGER="${PAGER:-less}"
export LESS="${LESS:--FRX}"
export BAT_THEME="${BAT_THEME:-Catppuccin Mocha}"

# Small, composable helpers. They do not install packages or mutate projects.
if (( ! $+functions[take] && ! $+aliases[take] )); then
  take() {
    if [[ $# -ne 1 ]]; then
      print -u2 'usage: take DIRECTORY'
      return 2
    fi
    mkdir -p -- "$1" && builtin cd -- "$1"
  }
fi

if (( ! $+functions[mkcd] && ! $+aliases[mkcd] )); then
  mkcd() { take "$@"; }
fi

if (( ! $+functions[groot] && ! $+aliases[groot] )); then
  groot() {
    local root
    root=$(git rev-parse --show-toplevel 2>/dev/null) || {
      print -u2 'Not inside a Git repository.'
      return 1
    }
    builtin cd -- "$root"
  }
fi

if (( ! $+functions[show-path] && ! $+aliases[show-path] )); then
  show-path() {
    local entry
    for entry in $path; do print -r -- "$entry"; done
  }
fi

if (( ! $+functions[reload-zsh] && ! $+aliases[reload-zsh] )); then
  reload-zsh() { exec zsh -l; }
fi

# A single, memorable entry point for the managed workstation tools.
# The dispatcher keeps status views read-only and requires explicit action names.
if [[ -z ${ORBIT_ROOT:-} && -r "$HOME/.config/orbit/root" ]]; then
  IFS= read -r ORBIT_ROOT < "$HOME/.config/orbit/root"
  export ORBIT_ROOT
fi

if (( ! $+functions[orbit] && ! $+aliases[orbit] )); then
  orbit() {
    local root="${ORBIT_ROOT:-$HOME/.config/orbit}"
    if [[ ! -x "$root/scripts/orbit" ]]; then
      print -u2 "Orbit is unavailable at $root/scripts/orbit"
      return 1
    fi
    "$root/scripts/orbit" "$@"
  }
fi

if [[ -o interactive ]]; then
  if [[ -t 0 && -t 1 ]]; then
    bindkey -e
    bindkey '^P' up-line-or-search
    bindkey '^N' down-line-or-search
    bindkey '^R' history-incremental-pattern-search-backward
    bindkey '^[[1;5C' forward-word
    bindkey '^[[1;5D' backward-word
  fi

  typeset -U fpath
  if [[ -d "${HOMEBREW_PREFIX:-/opt/homebrew}/share/zsh-completions" ]]; then
    fpath=("${HOMEBREW_PREFIX:-/opt/homebrew}/share/zsh-completions" $fpath)
  fi
  if [[ -t 0 && -t 1 ]] &&
      grep -Fxq autocomplete "$HOME/.config/orbit/enabled-profiles" 2>/dev/null &&
      [[ -r "${HOMEBREW_PREFIX:-/opt/homebrew}/share/zsh-autocomplete/zsh-autocomplete.plugin.zsh" ]]; then
    # The plugin writes recent directories here but does not create the parent.
    mkdir -p "${XDG_DATA_HOME:-$HOME/.local/share}/zsh"
    source "${HOMEBREW_PREFIX:-/opt/homebrew}/share/zsh-autocomplete/zsh-autocomplete.plugin.zsh"
  elif (( ! $+functions[compdef] )); then
    autoload -Uz compinit
    zstyle ':completion:*' use-cache on
    zstyle ':completion:*' cache-path "${XDG_CACHE_HOME:-$HOME/.cache}/zsh/zcompcache"
    zstyle ':completion:*' menu select
    zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}' 'r:|[._-]=* r:|=*'
    zstyle ':completion:*:descriptions' format '%F{yellow}-- %d --%f'
    zstyle ':completion:*:default' list-prompt '%S%M matches%s'
    mkdir -p "${XDG_CACHE_HOME:-$HOME/.cache}/zsh"
    compinit -i -d "${XDG_CACHE_HOME:-$HOME/.cache}/zsh/zcompdump-${ZSH_VERSION}"
  fi

  # fzf owns its own completion/key bindings when Homebrew has installed it.
  fzf_root="${HOMEBREW_PREFIX:-/opt/homebrew}/opt/fzf/shell"
  if [[ -t 0 && -t 1 && -r "$fzf_root/completion.zsh" ]] && (( ! $+functions[_fzf_compgen_path] )); then
    source "$fzf_root/completion.zsh"
  fi
  if [[ -t 0 && -t 1 && -r "$fzf_root/key-bindings.zsh" ]] && (( ! $+functions[_fzf_history_widget] )); then
    source "$fzf_root/key-bindings.zsh"
  fi

  if (( $+commands[mise] )) && [[ ${MISE_SHELL:-} != zsh ]]; then
    eval "$(mise activate zsh)"
  fi
  if (( $+commands[direnv] )) && (( ! $+functions[_direnv_hook] )); then
    eval "$(direnv hook zsh)"
  fi
  if (( $+commands[zoxide] )) && (( ! $+functions[_zoxide_z] )); then
    eval "$(zoxide init zsh)"
  fi
  if (( $+commands[starship] )) && [[ ${TERM:-dumb} != dumb && -z ${STARSHIP_SHELL:-} ]]; then
    # zsh's stock prompt differs on macOS; recognize both stock forms while
    # preserving a prompt that the user or a framework explicitly configured.
    case ${PROMPT:-'%m%# '} in
      '%m%# '|'%n@%m %1~ %# ')
        eval "$(starship init zsh)"
        ;;
    esac
  fi

  if (( $+commands[eza] )); then
    (( $+aliases[ls] || $+functions[ls] )) || alias ls='eza --group-directories-first'
    (( $+aliases[ll] || $+functions[ll] )) || alias ll='eza -lah --group-directories-first'
    (( $+aliases[la] || $+functions[la] )) || alias la='eza -a --group-directories-first'
  fi
  if (( $+commands[bat] )); then
    (( $+aliases[cat] || $+functions[cat] )) || alias cat='bat --paging=never'
  fi
  (( $+aliases[g] || $+functions[g] )) || alias g='git'
  (( $+aliases[gst] || $+functions[gst] )) || alias gst='git status --short --branch'
  (( $+aliases[gd] || $+functions[gd] )) || alias gd='git diff'
  (( $+aliases[gds] || $+functions[gds] )) || alias gds='git diff --staged'
  (( $+aliases[gl] || $+functions[gl] )) || alias gl='git log --oneline --decorate --graph -20'
  (( $+aliases[gsw] || $+functions[gsw] )) || alias gsw='git switch'
  (( $+aliases[gnew] || $+functions[gnew] )) || alias gnew='git switch -c'

  if [[ -t 0 && -t 1 && -r "${HOMEBREW_PREFIX:-/opt/homebrew}/share/zsh-autosuggestions/zsh-autosuggestions.zsh" ]] && (( ! $+functions[_zsh_autosuggest_start] )); then
    source "${HOMEBREW_PREFIX:-/opt/homebrew}/share/zsh-autosuggestions/zsh-autosuggestions.zsh"
  fi
fi
