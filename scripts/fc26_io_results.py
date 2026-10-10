#!/usr/bin/env python3
"""FC26-only observe actual file-open/read results without changing guest data."""
from pathlib import Path

def exact(path: str, before: str, after: str):
    p = Path(path)
    source = p.read_text()
    count = source.count(before)
    if count != 1:
        raise SystemExit(f"FC26_IO results: {path} expected 1 anchor, found {count}: {before[:75]!r}")
    p.write_text(source.replace(before, after, 1))

fs = "src/core/hle/service/filesystem/fsp/fs_i_filesystem.cpp"
file_cpp = "src/core/hle/service/filesystem/fsp/fs_i_file.cpp"
file_h = "src/core/hle/service/filesystem/fsp/fs_i_file.h"

exact(fs,
    """    R_TRY(backend->OpenFile(&vfs_file, FileSys::Path(path->str),
                            static_cast<FileSys::OpenMode>(mode)));

    *out_interface = std::make_shared<IFile>(system, vfs_file);""",
    """    const Result result = backend->OpenFile(&vfs_file, FileSys::Path(path->str),
                                            static_cast<FileSys::OpenMode>(mode));
    if (system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL) {
        LOG_WARNING(Service_FS, "FC26_IO OpenFile path={} mode={} result={:#x}",
                    path->str, mode, result.raw);
    }
    R_TRY(result);

    *out_interface = std::make_shared<IFile>(system, vfs_file, std::string(path->str));""")

exact(fs,
    """    R_TRY(backend->OpenDirectory(&vfs_dir, FileSys::Path(path->str),
                                 static_cast<FileSys::OpenDirectoryMode>(mode)));

    *out_interface = std::make_shared<IDirectory>(system, vfs_dir,""",
    """    const Result result = backend->OpenDirectory(&vfs_dir, FileSys::Path(path->str),
                                                 static_cast<FileSys::OpenDirectoryMode>(mode));
    if (system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL) {
        LOG_WARNING(Service_FS, "FC26_IO OpenDirectory path={} mode={} result={:#x}",
                    path->str, mode, result.raw);
    }
    R_TRY(result);

    *out_interface = std::make_shared<IDirectory>(system, vfs_dir,""")

exact(fs,
    """    R_TRY(backend->GetEntryType(&vfs_entry_type, FileSys::Path(path->str)));

    *out_type = static_cast<u32>(vfs_entry_type);""",
    """    const Result result = backend->GetEntryType(&vfs_entry_type, FileSys::Path(path->str));
    if (system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL) {
        LOG_WARNING(Service_FS, "FC26_IO GetEntryType path={} result={:#x} type={}",
                    path->str, result.raw,
                    result.IsSuccess() ? static_cast<u32>(vfs_entry_type) : 0);
    }
    R_TRY(result);

    *out_type = static_cast<u32>(vfs_entry_type);""")

exact(file_h,
    """    explicit IFile(Core::System& system_, FileSys::VirtualFile file_);""",
    """    explicit IFile(Core::System& system_, FileSys::VirtualFile file_, std::string debug_path_);""")

exact(file_h,
    """    std::unique_ptr<FileSys::Fsa::IFile> backend;""",
    """    std::unique_ptr<FileSys::Fsa::IFile> backend;
    std::string debug_path;""")

exact(file_cpp,
    """#include "core/file_sys/errors.h" """.rstrip(),
    """#include <atomic>
#include <string>
#include <utility>

#include "core/file_sys/errors.h" """.rstrip())

exact(file_cpp,
    """IFile::IFile(Core::System& system_, FileSys::VirtualFile file_)
    : ServiceFramework{system_, "IFile"}, backend{std::make_unique<FileSys::Fsa::IFile>(file_)} {""",
    """IFile::IFile(Core::System& system_, FileSys::VirtualFile file_, std::string debug_path_)
    : ServiceFramework{system_, "IFile"}, backend{std::make_unique<FileSys::Fsa::IFile>(file_)},
      debug_path{std::move(debug_path_)} {""")

exact(file_cpp,
    """    // Read the data from the Storage backend
    R_RETURN(
        backend->Read(reinterpret_cast<size_t*>(out_size.Get()), offset, out_buffer.data(), size));""",
    """    // Read the data from the Storage backend. FC26 probe is read-only.
    const Result result =
        backend->Read(reinterpret_cast<size_t*>(out_size.Get()), offset, out_buffer.data(), size);
    if (system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL) {
        static std::atomic<u32> count{0};
        if (count.fetch_add(1, std::memory_order_relaxed) < 128 || result.IsError()) {
            LOG_WARNING(Service_FS,
                        "FC26_IO Read path={} offset={:#x} requested={} actual={} result={:#x}",
                        debug_path, offset, size,
                        result.IsSuccess() ? *out_size.Get() : 0, result.raw);
        }
    }
    R_RETURN(result);""")

exact(file_cpp,
    """Result IFile::GetSize(Out<s64> out_size) {
    LOG_DEBUG(Service_FS, "called");

    R_RETURN(backend->GetSize(out_size));
}""",
    """Result IFile::GetSize(Out<s64> out_size) {
    LOG_DEBUG(Service_FS, "called");
    const Result result = backend->GetSize(out_size);
    if (system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL) {
        LOG_WARNING(Service_FS, "FC26_IO GetSize path={} size={} result={:#x}",
                    debug_path, result.IsSuccess() ? *out_size.Get() : 0, result.raw);
    }
    R_RETURN(result);
}""")

print("FC26_IO: read-only open, stat, and read result telemetry installed")
