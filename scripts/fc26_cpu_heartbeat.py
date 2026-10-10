#!/usr/bin/env python3
"""Rate-limited FC26 guest CPU activity trace for a no-frame startup.

A pair of entry/exit samples tells us whether NCE is making progress or
remaining inside guest code. This is diagnostic only; no memory modifications.
"""
from pathlib import Path
path=Path("src/core/arm/nce/arm_nce.cpp")
src=path.read_text()
def replace(old,new):
    global src
    n=src.count(old)
    if n!=1:
        raise SystemExit(f"FC26 CPU trace: expected one anchor, got {n}: {old[:55]!r}")
    src=src.replace(old,new,1)

replace("#include <cinttypes>\n", "#include <chrono>\n#include <cinttypes>\n")
replace(
"""    auto* process = thread->GetOwnerProcess();

    // Move non-critical operations outside the locked section
""",
"""    auto* process = thread->GetOwnerProcess();

    // FC26 base game reaches file-system initialization but makes no visible
    // presentation. Trace only a few CPU entries, then one every two seconds.
    static thread_local u32 fc26_first_reports{};
    static thread_local std::chrono::steady_clock::time_point fc26_last_report{};
    const bool fc26_current_game = process->GetProgramId() == 0x01004FF021942000ULL;
    const auto fc26_now = std::chrono::steady_clock::now();
    const bool fc26_report = fc26_current_game &&
        (fc26_first_reports < 12 ||
         fc26_now - fc26_last_report >= std::chrono::seconds(2));
    if (fc26_report) {
        ++fc26_first_reports;
        fc26_last_report = fc26_now;
        LOG_WARNING(Core_ARM,
                    "FC26_CPU enter core={} thread={} pc={:#x} sp={:#x} x0={:#x} "
                    "x1={:#x} last_svc={:#x}",
                    m_core_index, static_cast<const void*>(thread), m_guest_ctx.pc,
                    m_guest_ctx.sp, m_guest_ctx.cpu_registers[0],
                    m_guest_ctx.cpu_registers[1], m_guest_ctx.svc);
    }

    // Move non-critical operations outside the locked section
""")
replace(
"""    // Return the halt reason.
    return hr;
""",
"""    if (fc26_report) {
        LOG_WARNING(Core_ARM,
                    "FC26_CPU exit core={} thread={} reason={:#x} pc={:#x} "
                    "sp={:#x} x0={:#x} x1={:#x} last_svc={:#x}",
                    m_core_index, static_cast<const void*>(thread),
                    static_cast<u64>(hr), m_guest_ctx.pc, m_guest_ctx.sp,
                    m_guest_ctx.cpu_registers[0], m_guest_ctx.cpu_registers[1],
                    m_guest_ctx.svc);
    }
    // Return the halt reason.
    return hr;
""")
path.write_text(src)
print("FC26 CPU heartbeat diagnostics installed")
