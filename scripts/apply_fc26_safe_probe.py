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
print("FC26 safe NCE probe applied: unhandled data faults no longer skipped")
