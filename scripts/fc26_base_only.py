#!/usr/bin/env python3
"""FC26-only A/B compatibility test: launch original base content.

The user's FC26 update v0.27.0 consistently crashes in guest NCE. Others
report reaching the menu when the installed update is disabled. Treat this as
a temporary compatibility test: do not modify user game files or other titles.
"""
from pathlib import Path

source_file = Path("src/core/file_sys/patch_manager.cpp")
source = source_file.read_text()
old = """std::vector<std::string> PatchManager::GetDisabledAddons() const {
    auto disabled = Settings::values.disabled_addons[title_id];
    if (parent_title_id) {
"""
new = """std::vector<std::string> PatchManager::GetDisabledAddons() const {
    auto disabled = Settings::values.disabled_addons[title_id];
    if (title_id == 0x01004FF021942000ULL) {
        // Force base FC26 ExeFS AND RomFS in this diagnostic build.
        // Check NAND/SDMC and versioned external updates as well.
        disabled.emplace_back("Update");
        disabled.emplace_back("Update (NAND)");
        disabled.emplace_back("Update (SDMC)");
        LOG_WARNING(Loader,
                    "FC26_BASE_ONLY active: update disabled in memory (game files untouched)");
    }
    if (parent_title_id) {
"""
if source.count(old) != 1:
    raise SystemExit(f"FC26 base-only: expected one GetDisabledAddons() match, found {source.count(old)}")
source_file.write_text(source.replace(old, new, 1))
print("FC26 BASE_ONLY: update ignored for FC26 by PatchManager")
