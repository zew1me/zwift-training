#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat << 'USAGE'
Usage: scripts/init-repo.sh [options]

Creates a symlink from your Zwift workouts folder to this repo's workouts/
folder. Optionally installs tooling (prek, shellcheck, shfmt) via Homebrew.

Options:
  -u, --user-id ID       Zwift user id folder (numeric). If omitted, auto-detects.
  -z, --zwift-dir PATH   Zwift Workouts directory (default: ~/Documents/Zwift/Workouts)
  -l, --link-name NAME   Symlink name under the user id dir (default: custom)
  --import               Copy existing .zwo files into workouts/imported
  --backup               Backup the Zwift user folder before changes
  --list-users           List numeric user id folders under the Zwift directory and exit
  --install-tools        Install prek, shellcheck, shfmt via Homebrew and install hooks
  -h, --help             Show this help text
USAGE
}

die() {
  echo "error: $*" >&2
  exit 1
}

repo_root() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$script_dir/.." && pwd
}

expand_path() {
  local input="$1"
  if [[ "$input" == "~"* ]]; then
    echo "${input/#\~/$HOME}"
  else
    echo "$input"
  fi
}

install_tools() {
  if ! command -v brew > /dev/null 2>&1; then
    die "Homebrew not found. Install it first: https://brew.sh/"
  fi

  if ! brew list j178/tap/prek > /dev/null 2>&1; then
    brew install j178/tap/prek
  fi
  if ! brew list shellcheck > /dev/null 2>&1; then
    brew install shellcheck
  fi
  if ! brew list shfmt > /dev/null 2>&1; then
    brew install shfmt
  fi

  if command -v prek > /dev/null 2>&1; then
    prek install
  fi
}

user_id=""
zwift_dir="$HOME/Documents/Zwift/Workouts"
link_name="custom"
import_existing=false
backup_flag=false
install_flag=false
list_users=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -u | --user-id)
      user_id="$2"
      shift 2
      ;;
    -z | --zwift-dir)
      zwift_dir="$2"
      shift 2
      ;;
    -l | --link-name)
      link_name="$2"
      shift 2
      ;;
    --import)
      import_existing=true
      shift
      ;;
    --backup)
      backup_flag=true
      shift
      ;;
    --list-users)
      list_users=true
      shift
      ;;
    --install-tools)
      install_flag=true
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac

done

zwift_dir="$(expand_path "$zwift_dir")"

if [[ "$install_flag" == true ]]; then
  install_tools
fi

if [[ ! -d "$zwift_dir" ]]; then
  die "Zwift Workouts directory not found: $zwift_dir"
fi

if [[ "$list_users" == true ]]; then
  mapfile -t candidates < <(
    for path in "$zwift_dir"/*; do
      [[ -d "$path" ]] || continue
      basename "${path}"
    done | awk '/^[0-9]+$/'
  )
  if [[ ${#candidates[@]} -eq 0 ]]; then
    echo "No numeric user id folders found under: $zwift_dir"
    exit 0
  fi
  printf '%s\n' "${candidates[@]}"
  exit 0
fi

if [[ -z "$user_id" ]]; then
  mapfile -t candidates < <(
    for path in "$zwift_dir"/*; do
      [[ -d "$path" ]] || continue
      basename "${path}"
    done | awk '/^[0-9]+$/'
  )

  if [[ ${#candidates[@]} -eq 0 ]]; then
    die "no user id folders found under: $zwift_dir"
  fi
  if [[ ${#candidates[@]} -gt 1 ]]; then
    echo "Multiple user id folders found:" >&2
    printf '  %s\n' "${candidates[@]}" >&2
    die "rerun with --user-id"
  fi

  user_id="${candidates[0]}"
fi

if [[ ! "$user_id" =~ ^[0-9]+$ ]]; then
  die "user id must be numeric"
fi

repo_root_path="$(repo_root)"
repo_workouts="$repo_root_path/workouts"
mkdir -p "$repo_workouts"

zwift_user_dir="$zwift_dir/$user_id"
if [[ ! -d "$zwift_user_dir" ]]; then
  die "Zwift user directory not found: $zwift_user_dir"
fi

if [[ "$backup_flag" == true ]]; then
  if ! command -v rsync > /dev/null 2>&1; then
    die "rsync not found; cannot perform backup"
  fi
  backup_root="$repo_root_path/backups"
  ts="$(date +\"%Y%m%d%H%M%S\")"
  backup_dir="$backup_root/${user_id}-${ts}"
  mkdir -p "$backup_root"
  rsync -a "$zwift_user_dir/" "$backup_dir/"
  echo "Backed up Zwift user folder to: $backup_dir"
fi

if [[ "$import_existing" == true ]]; then
  import_dir="$repo_workouts/imported"
  mkdir -p "$import_dir"
  find "$zwift_user_dir" -maxdepth 1 -type f -name '*.zwo' -print0 |
    xargs -0 -I {} cp -n "{}" "$import_dir/"
fi

link_path="$zwift_user_dir/$link_name"

if [[ -L "$link_path" ]]; then
  existing_target="$(readlink "$link_path")"
  if [[ "$existing_target" == "$repo_workouts" ]]; then
    echo "Symlink already points to repo: $link_path -> $existing_target"
    exit 0
  fi
fi

if [[ -e "$link_path" || -L "$link_path" ]]; then
  ts="$(date +"%Y%m%d%H%M%S")"
  backup_path="${link_path}.bak-${ts}"
  mv "$link_path" "$backup_path"
  echo "Backed up existing path to: $backup_path"
fi

ln -s "$repo_workouts" "$link_path"

echo "Created symlink: $link_path -> $repo_workouts"
echo "Restart Zwift to refresh Custom Workouts."
