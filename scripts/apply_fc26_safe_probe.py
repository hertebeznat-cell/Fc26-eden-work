#!/usr/bin/env python3
"""Apply a tightly scoped FC26 NCE probe to the already-patched Eden tree.

This intentionally replaces an unsafe fault-skipping experiment. It does not
pretend to repair the root cause of the game's null pointer.
"""
from pathlib import Path


def replace_exact(path: str, before: str, after: str) -> None:
    file = Path(path)
    source = file.read_text()
    count = source.count(before)
    if count != 1:
        raise SystemExit(f"FC26 safe probe: expected one match in {path}, found {count}")
    file.write_text(source.replace(before, after, 1))


replace_exact(
    "src/core/arm/nce/arm_nce.h",
    "    std::atomic<u64> m_last_guest_fault_address{};\n",
    "    std::atomic<u64> m_last_guest_fault_address{};\n"
    "    std::atomic<u32> m_fc26_null_ldr_workarounds{};\n",
)

replace_exact(
    "src/core/arm/nce/arm_nce.cpp",
    """    const bool is_null_data_abort =
        !is_prefetch_abort && reinterpret_cast<uintptr_t>(info->si_addr) == 0;
    if (!is_prefetch_abort && !is_null_data_abort) {
        host_ctx.pc += 4;
        return true;
    }
""",
    """    const bool is_null_data_abort =
        !is_prefetch_abort && reinterpret_cast<uintptr_t>(info->si_addr) == 0;

    // FC26 startup compatibility probe: the guest executes
    // LDR X8, [SP,#24]; MOV X20, X8; LDRB W9, [X20],#1 with X20 == 0.
    // Redirect this one read to the existing zero-valued stack slot.
    // The original instruction executes; we never skip it.
    if (is_null_data_abort && host_ctx.regs[20] == 0 && host_ctx.sp > 0x1000 &&
        guest_ctx->parent->m_running_thread->GetOwnerProcess()->GetProgramId() ==
            0x01004FF021942000ULL) {
        u32 op{}, previous{}, before_previous{};
        std::memcpy(&op, reinterpret_cast<const void*>(host_ctx.pc), sizeof(op));
        std::memcpy(&previous, reinterpret_cast<const void*>(host_ctx.pc - 4),
                    sizeof(previous));
        std::memcpy(&before_previous, reinterpret_cast<const void*>(host_ctx.pc - 8),
                    sizeof(before_previous));
        if (op == 0x38401689 && previous == 0xaa0803f4 &&
            before_previous == 0xf9400fe8) {
            auto& count = guest_ctx->parent->m_fc26_null_ldr_workarounds;
            if (count.fetch_add(1, std::memory_order_relaxed) == 0) {
                host_ctx.regs[20] = host_ctx.sp + 0x18;
                return true;
            }
        }
    }

    // An unhandled data abort must return to the guest kernel rather than
    // blindly advancing PC. Skipping instructions generated 926k errors
    // while FC26 scanned unmapped pages.
""",
)

replace_exact(
    "src/core/arm/nce/arm_nce.cpp",
    """    if (hr == HaltReason::DataAbort || hr == HaltReason::PrefetchAbort) {
        static std::atomic<u32> reported_faults{0};
""",
    """    if (hr == HaltReason::DataAbort || hr == HaltReason::PrefetchAbort) {
        LOG_WARNING(Core_ARM, "FC26_COMPAT stack-slot redirects on this core: {}",
                    m_fc26_null_ldr_workarounds.load(std::memory_order_relaxed));
        static std::atomic<u32> reported_faults{0};
""",
)
replace_exact(
    "src/core/arm/nce/arm_nce.cpp",
    """            const u32 instruction = instruction_mapped ? guest_memory.Read32(fault_pc) : 0;
""",
    """            const u32 instruction = instruction_mapped ? guest_memory.Read32(fault_pc) : 0;
            // FC26: inspect where the invalid pointer came from; do not
            // overwrite pointers or skip instructions. All reads are mapped.
            if (process->GetProgramId() == 0x01004FF021942000ULL) {
                const u64 guest_sp = m_guest_ctx.sp;
                if (guest_sp != 0 &&
                    guest_memory.IsValidVirtualAddressRange(
                        Common::ProcessAddress{guest_sp}, 64)) {
                    LOG_ERROR(Core_ARM,
                              "FC26_DIAG stack sp={:#x} +0={:#x} +8={:#x} +16={:#x} "
                              "+24={:#x} +32={:#x} +40={:#x} +48={:#x} +56={:#x}",
                              guest_sp,
                              guest_memory.Read64(Common::ProcessAddress{guest_sp}),
                              guest_memory.Read64(Common::ProcessAddress{guest_sp + 8}),
                              guest_memory.Read64(Common::ProcessAddress{guest_sp + 16}),
                              guest_memory.Read64(Common::ProcessAddress{guest_sp + 24}),
                              guest_memory.Read64(Common::ProcessAddress{guest_sp + 32}),
                              guest_memory.Read64(Common::ProcessAddress{guest_sp + 40}),
                              guest_memory.Read64(Common::ProcessAddress{guest_sp + 48}),
                              guest_memory.Read64(Common::ProcessAddress{guest_sp + 56}));
                }
                const u64 table_base = m_guest_ctx.cpu_registers[9];
                const u64 table_index = m_guest_ctx.cpu_registers[8];
                if (table_base != 0 && table_index < 64 &&
                    table_base < 0x1000000000000ULL) {
                    const u64 table_slot = table_base + table_index * sizeof(u64);
                    if (guest_memory.IsValidVirtualAddressRange(
                            Common::ProcessAddress{table_slot}, 8)) {
                        LOG_ERROR(Core_ARM,
                                  "FC26_DIAG table base={:#x} idx={} slot={:#x} "
                                  "value={:#x} x27={:#x}",
                                  table_base, table_index, table_slot,
                                  guest_memory.Read64(Common::ProcessAddress{table_slot}),
                                  m_guest_ctx.cpu_registers[27]);
                    }
                    if (guest_memory.IsValidVirtualAddressRange(
                            Common::ProcessAddress{table_base}, 48)) {
                        LOG_ERROR(Core_ARM,
                                  "FC26_DIAG table first6={:#x},{:#x},{:#x},"
                                  "{:#x},{:#x},{:#x}",
                                  guest_memory.Read64(Common::ProcessAddress{table_base}),
                                  guest_memory.Read64(Common::ProcessAddress{table_base + 8}),
                                  guest_memory.Read64(Common::ProcessAddress{table_base + 16}),
                                  guest_memory.Read64(Common::ProcessAddress{table_base + 24}),
                                  guest_memory.Read64(Common::ProcessAddress{table_base + 32}),
                                  guest_memory.Read64(Common::ProcessAddress{table_base + 40}));
                    }
                }
                if (m_guest_ctx.pc >= 64 &&
                    guest_memory.IsValidVirtualAddressRange(
                        Common::ProcessAddress{m_guest_ctx.pc - 64}, 64)) {
                    for (u64 delta = 64; delta >= 16; delta -= 16) {
                        const u64 at = m_guest_ctx.pc - delta;
                        LOG_ERROR(Core_ARM,
                                  "FC26_DIAG asm -{:#x}={:#010x} -{:#x}={:#010x} "
                                  "-{:#x}={:#010x} -{:#x}={:#010x}",
                                  delta, guest_memory.Read32(Common::ProcessAddress{at}),
                                  delta - 4, guest_memory.Read32(Common::ProcessAddress{at + 4}),
                                  delta - 8, guest_memory.Read32(Common::ProcessAddress{at + 8}),
                                  delta - 12, guest_memory.Read32(Common::ProcessAddress{at + 12}));
                    }
                }
            }
""",
)

print("FC26 safe NCE probe applied: unhandled data faults no longer skipped")
