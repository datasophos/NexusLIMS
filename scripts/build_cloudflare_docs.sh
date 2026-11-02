#!/usr/bin/env bash
# Cloudflare Pages build command for documentation previews.
set -euo pipefail

python -m pip install uv
# pip may install executables outside PATH (for example, in the user bin dir).
export PATH="$(dirname "$(python -c 'from uv import find_uv_bin; print(find_uv_bin())')"):$PATH"
uv sync --frozen
export NX_INSTRUMENT_DATA_PATH=/tmp/nx_instrument_data
export NX_DATA_PATH=/tmp/nx_data
export NX_DB_PATH=/tmp/nexuslims_docs.db
export NX_CDCS_TOKEN=docs-build-placeholder
export NX_CDCS_URL=https://placeholder.example.com
mkdir -p "$NX_INSTRUMENT_DATA_PATH" "$NX_DATA_PATH"
touch "$NX_DB_PATH"
python scripts/generate_switcher_json.py
# Reuse published media; the Cloudflare image does not have VHS/ttyd.
for asset in main_screen.svg help_screen.svg db_browser_table_viewer.svg \
  config_main_screen.svg config_help_screen.svg config_field_detail.svg \
  demo_search_filter.mp4 demo_add_instrument.mp4 demo_edit_instrument.mp4 \
  demo_delete_instrument.mp4 demo_theme_switch.mp4 config_main.mp4 \
  config_field_help.mp4 config_nemo_management.mp4; do
    case "$asset" in
      *.svg) asset_dir=docs/images/tui/screenshots ;;
      *.mp4) asset_dir=docs/images/tui/recordings ;;
    esac
    mkdir -p "$asset_dir"
    git show "origin/gh-pages:latest/_images/$asset" > "$asset_dir/$asset"
done
./scripts/build_docs.sh --strict --skip-tui-demos
