#!/bin/bash
# Shared setup presentation. Sourcing this file does not change machine or repo state.
phase_total=7
resume_requested=${resume_requested:-0}
resume_phase=${resume_phase:-}
interactive=0
color_reset=''
color_indigo=''
color_mint=''
color_amber=''
color_rose=''
color_muted=''
if [ -t 1 ] && [ "${TERM:-}" != dumb ]; then
  interactive=1
fi
if [ "$interactive" -eq 1 ] && [ -z "${NO_COLOR+x}" ]; then
  color_reset=$'\033[0m'
  color_indigo=$'\033[38;2;180;190;254m'
  color_mint=$'\033[38;2;148;226;213m'
  color_amber=$'\033[38;2;249;226;175m'
  color_rose=$'\033[38;2;243;139;168m'
  color_muted=$'\033[38;2;166;173;200m'
fi

terminal_columns() {
  local size
  if size=$(stty size 2>/dev/null </dev/tty); then
    size=${size##* }
    if [ "$size" -gt 0 ] 2>/dev/null; then
      printf '%s\n' "$size"
      return
    fi
  fi
  printf '%s\n' "${COLUMNS:-80}"
}

rule() {
  local spaces
  printf -v spaces '%*s' "$1" ''
  printf '%s' "${spaces// /─}"
}

phase_title() {
  case "$1" in
    bootstrap) printf 'Bootstrap\n' ;;
    apply) printf 'Tools & config\n' ;;
    preferences) printf 'macOS settings\n' ;;
    services) printf 'Container service\n' ;;
    container-smoke) printf 'Container check\n' ;;
    repository-check) printf 'Repository checks\n' ;;
    readiness) printf 'Readiness\n' ;;
  esac
}

duration() {
  local elapsed=$1
  if [ "$elapsed" -ge 3600 ]; then
    printf '%sh %sm\n' "$((elapsed / 3600))" "$(((elapsed % 3600) / 60))"
  elif [ "$elapsed" -ge 60 ]; then
    printf '%sm %ss\n' "$((elapsed / 60))" "$((elapsed % 60))"
  else
    printf '%ss\n' "$elapsed"
  fi
}

setup_heading() {
  local width
  if [ "$interactive" -eq 0 ]; then
    printf 'ORBIT / SETUP\n  %s phases · tools, settings, checks\n' "$phase_total"
    if [ "$resume_requested" -eq 1 ]; then
      printf '  RESUME · from %s\n' "$(phase_title "$resume_phase")"
    fi
    return
  fi
  width=$(terminal_columns)
  case "$width" in
    ''|*[!0-9]*) width=80 ;;
  esac
  printf '\n  %s◉ ORBIT / SETUP%s\n' "$color_indigo" "$color_reset"
  if [ "$width" -ge 50 ]; then
    printf '  %s%s phases · tools, settings, checks%s\n' \
      "$color_muted" "$phase_total" "$color_reset"
  elif [ "$width" -lt 24 ]; then
    printf '  %s%s phases%s\n' "$color_muted" "$phase_total" "$color_reset"
  else
    printf '  %s%s phases · setup%s\n' "$color_muted" "$phase_total" "$color_reset"
  fi
  if [ "$resume_requested" -eq 1 ]; then
    if [ "$width" -lt 42 ]; then
      printf '  %sRESUME%s\n' "$color_amber" "$color_reset"
    else
      printf '  %sRESUME%s  from %s\n' "$color_amber" "$color_reset" \
        "$(phase_title "$resume_phase")"
    fi
  fi
}

phase_heading() {
  local number=$1 label=$2 width marks='' index marks_visible
  width=$(terminal_columns)
  case "$width" in
    ''|*[!0-9]*) width=80 ;;
  esac
  if [ "$width" -lt 20 ]; then width=20; fi
  if [ "$width" -gt 80 ]; then width=80; fi
  for ((index = 1; index <= phase_total; index++)); do
    if [ "$index" -lt "$number" ]; then
      marks+="${color_mint}●${color_reset} "
    elif [ "$index" -eq "$number" ]; then
      marks+="${color_indigo}◉${color_reset} "
    else
      marks+="${color_muted}○${color_reset} "
    fi
  done
  marks=${marks% }
  marks_visible=$((phase_total * 2 - 1))
  if [ "$width" -lt 42 ]; then
    printf '\n  %s%02d/%02d%s\n' "$color_indigo" "$number" "$phase_total" "$color_reset"
    printf '  %s%s%s\n' "$color_indigo" "$label" "$color_reset"
  else
    printf '\n  %s%02d/%02d%s  %s\n' "$color_indigo" "$number" "$phase_total" "$color_reset" "$label"
  fi
  printf '  %s  %s%s%s\n' "$marks" "$color_muted" \
    "$(rule "$((width - 4 - marks_visible))")" "$color_reset"
}

phase_started() {
  local number=$1 label=$2
  if [ "$interactive" -eq 1 ]; then
    phase_heading "$number" "$label"
  else
    printf '\nORBIT / %02d/%02d %s\n' "$number" "$phase_total" "$label"
  fi
}

setup_outcome() {
  local state=$1 detail=$2 hint=$3 action=$4 tone=$5
  local short_detail=$6 short_hint=$7 width line
  if [ "$interactive" -eq 1 ]; then
    width=$(terminal_columns)
    case "$width" in
      ''|*[!0-9]*) width=80 ;;
    esac
    printf '\n  %s◉ ORBIT / %s%s\n' "$tone" "$state" "$color_reset"
    if [ "$width" -lt 42 ]; then
      while IFS= read -r line; do printf '  %s\n' "$line"; done <<< "$short_detail"
      printf '  %sNEXT%s\n' "$color_amber" "$color_reset"
      while IFS= read -r line; do printf '    %s\n' "$line"; done <<< "$short_hint"
      if [ "$width" -lt 24 ]; then
        printf '  %s%s%s\n' "$tone" "$action" "$color_reset"
      else
        printf '    %s↳ %s%s\n' "$tone" "$action" "$color_reset"
      fi
    else
      printf '  %s\n' "$detail"
      printf '  %sNEXT%s  %s\n' "$color_amber" "$color_reset" "$hint"
      printf '    %s↳ %s%s\n' "$tone" "$action" "$color_reset"
    fi
  else
    printf '\nORBIT / %s\n' "$state"
    printf '  %s\n' "$detail"
    printf '  NEXT · %s %s\n' "$hint" "$action"
  fi
}

phase_skipped() {
  local number=$1 label=$2 phase=$3 resume_from=$4 width
  if [ "$interactive" -eq 0 ]; then
    printf '  SKIP · %s (resume starts at %s)\n' "$phase" "$resume_from"
    return
  fi
  width=$(terminal_columns)
  case "$width" in
    ''|*[!0-9]*) width=80 ;;
  esac
  if [ "$width" -lt 42 ]; then
    printf '  %s↷ %02d/%02d skipped%s\n' \
      "$color_muted" "$number" "$phase_total" "$color_reset"
    printf '  %s%s%s\n' "$color_muted" "$label" "$color_reset"
  else
    printf '  %s↷ %02d/%02d  %s · already complete%s\n' \
      "$color_muted" "$number" "$phase_total" "$label" "$color_reset"
  fi
}

phase_finished() {
  local phase=$1 label=$2 elapsed=$3
  if [ "$interactive" -eq 1 ]; then
    printf '  %s✓%s  %s · %s\n' "$color_mint" "$color_reset" "$label" "$elapsed"
  else
    printf '  DONE · %s · %s\n' "$phase" "$elapsed"
  fi
}

setup_ui_preview() {
  # These examples call the same renderers as setup, before any state or lock work.
  local width
  if [ "$interactive" -eq 1 ]; then
    width=$(terminal_columns)
    case "$width" in
      ''|*[!0-9]*) width=80 ;;
    esac
    printf '\n  %s◉ ORBIT / APPEARANCE%s\n' "$color_indigo" "$color_reset"
    if [ "$width" -lt 42 ]; then
      printf '  %sRead-only samples%s\n' "$color_muted" "$color_reset"
    else
      printf '  %sSample states · no setup or state changes%s\n' "$color_muted" "$color_reset"
    fi
  else
    printf 'ORBIT / APPEARANCE\n  Sample states · no setup or state changes\n'
  fi
  if [ "$interactive" -eq 0 ]; then printf '\n'; fi
  setup_heading
  phase_started 1 'Bootstrap'
  phase_finished bootstrap 'Bootstrap' '12s'

  resume_requested=1
  resume_phase=services
  if [ "$interactive" -eq 0 ]; then printf '\n'; fi
  setup_heading
  phase_skipped 1 'Bootstrap' bootstrap services
  phase_skipped 2 'Tools & config' apply services
  phase_skipped 3 'macOS settings' preferences services
  phase_started 4 'Container service'

  setup_outcome HOLD '4/7 Container service · exit 1 · 3s' \
    'Resolve the error above, then run from Orbit:' './setup --resume' "$color_rose" \
    $'4/7\nContainer service\nexit 1 · 3s' $'Fix error above.\nIn Orbit folder:'

  setup_outcome READY '7/7 phases complete · 2m 14s' \
    'Open a new terminal, then run:' 'orbit status' "$color_mint" \
    $'7/7 complete\n2m 14s elapsed' 'New terminal.'
}
