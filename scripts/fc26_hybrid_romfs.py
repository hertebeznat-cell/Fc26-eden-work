#!/usr/bin/env python3
"""FC26-only controlled hybrid startup experiment.

Keep original/base ExeFS to avoid the confirmed null-pointer crash in the
installed update, but use the installed *RomFS resources* from that update.
Only the in-memory list of disabled update names is altered in PatchRomFS;
neither installed NSP nor user files are modified. Mixing versions may still
be incompatible; this is a diagnosis, not a claimed compatibility fix.
"""
from pathlib import Path
p=Path("src/core/file_sys/patch_manager.cpp")
src=p.read_text()
before="""    auto romfs = base_romfs;

    // Game Updates
    const auto update_tid = GetUpdateTitleID(title_id);
    const auto disabled = GetDisabledAddons();

    bool update_disabled = true;
"""
after="""    auto romfs = base_romfs;

    // Game Updates
    const auto update_tid = GetUpdateTitleID(title_id);
    auto disabled = GetDisabledAddons();
    if (title_id == 0x01004FF021942000ULL && type == ContentRecordType::Program) {
        // The updated FC26 executable crashes in NCE; the original one
        // boots but never creates a display layer. Test whether base code
        // can load update assets by enabling the update for RomFS only.
        std::erase_if(disabled, [](const std::string& entry) {
            return entry == "Update" || entry == "Update (NAND)" ||
                   entry == "Update (SDMC)" || entry.starts_with("Update@");
        });
        LOG_WARNING(Loader,
                    "FC26_HYBRID: using base ExeFS with installed update RomFS (test only)");
    }

    bool update_disabled = true;
"""
n=src.count(before)
if n != 1:
    raise SystemExit(f"FC26 hybrid probe: expected one PatchRomFS anchor, got {n}")
p.write_text(src.replace(before,after,1))
print("FC26 hybrid base ExeFS / update RomFS compatibility probe applied")
