#!/usr/bin/env python3
"""Observe FC26 filesystem calls before display initialization.

The previous hybrid ExeFS/RomFS experiment reproduced the updated-game NCE
crash. This safe probe leaves file operations unchanged; it only reports up to
96 operations per kind from FC26, including the game asset paths requested.
"""
from pathlib import Path
p=Path("src/core/hle/service/filesystem/fsp/fs_i_filesystem.cpp")
s=p.read_text()

def once(old,new):
    global s
    count=s.count(old)
    if count!=1:
        raise SystemExit(f"FC26_FS trace: expected one anchor, got {count}: {old[:75]!r}")
    s=s.replace(old,new,1)

once('#include "core/hle/service/cmif_serialization.h"',
     '#include <atomic>\n\n#include "core/hle/service/cmif_serialization.h"')
once(
    '    LOG_DEBUG(Service_FS, "called. file={}, mode={}", path->str, mode);',
    '''    LOG_DEBUG(Service_FS, "called. file={}, mode={}", path->str, mode);
    if (system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL) {
        static std::atomic<u32> count{0};
        if (count.fetch_add(1, std::memory_order_relaxed) < 96) {
            LOG_WARNING(Service_FS, "FC26_FS OpenFile file={} mode={}", path->str, mode);
        }
    }''')
once(
    '    LOG_DEBUG(Service_FS, "called. directory={}, mode={}", path->str, mode);',
    '''    LOG_DEBUG(Service_FS, "called. directory={}, mode={}", path->str, mode);
    if (system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL) {
        static std::atomic<u32> count{0};
        if (count.fetch_add(1, std::memory_order_relaxed) < 96) {
            LOG_WARNING(Service_FS, "FC26_FS OpenDirectory directory={} mode={}", path->str, mode);
        }
    }''')
once(
    '''Result IFileSystem::GetEntryType(
    Out<u32> out_type, const InLargeData<FileSys::Sf::Path, BufferAttr_HipcPointer> path) {
    LOG_DEBUG(Service_FS, "called. file={}", path->str);''',
    '''Result IFileSystem::GetEntryType(
    Out<u32> out_type, const InLargeData<FileSys::Sf::Path, BufferAttr_HipcPointer> path) {
    LOG_DEBUG(Service_FS, "called. file={}", path->str);
    if (system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL) {
        static std::atomic<u32> count{0};
        if (count.fetch_add(1, std::memory_order_relaxed) < 96) {
            LOG_WARNING(Service_FS, "FC26_FS GetEntryType file={}", path->str);
        }
    }''')
p.write_text(s)
print("FC26 filesystem trace installed, emulation results unchanged")
