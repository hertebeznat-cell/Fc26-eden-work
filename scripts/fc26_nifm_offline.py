#!/usr/bin/env python3
"""FC26-only fix/probe for inconsistent offline NIFM request completion.

In upstream NIFM, IRequest::Submit on a disconnected console stays OnHold;
GetResult may later report *success* even after state becomes Invalid, and
IRequest's second completion event is never signaled. This experiment reports
the true offline state and wakes the completion waiter for FC26 only.
"""
from pathlib import Path
p=Path("src/core/hle/service/nifm/nifm.cpp")
s=p.read_text()
def exact(old,new):
    global s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"FC26 NIFM: anchor count {n}, expected one: {old[:75]!r}")
    s=s.replace(old,new,1)

exact(
'''        if (state == RequestState::NotSubmitted) {
            UpdateState(RequestState::OnHold);
        }

        IPC::ResponseBuilder rb{ctx, 2};''',
'''        if (system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL &&
            Settings::values.airplane_mode.GetValue()) {
            // No connection attempt is possible. A pending request would leave
            // FC26 waiting on an event that upstream never signals.
            UpdateState(RequestState::Invalid);
            event2->Signal(system.Kernel());
            LOG_WARNING(Service_NIFM,
                        "FC26_NIFM Submit offline: marked invalid and completion signaled");
        } else if (state == RequestState::NotSubmitted) {
            UpdateState(RequestState::OnHold);
        }

        IPC::ResponseBuilder rb{ctx, 2};'''
)
exact(
'''            switch (state) {
            case RequestState::NotSubmitted:''',
'''            if (system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL &&
                !has_connection) {
                if (state != RequestState::Invalid) {
                    UpdateState(RequestState::Invalid);
                    event2->Signal(system.Kernel());
                }
                LOG_WARNING(Service_NIFM,
                            "FC26_NIFM GetResult: network unavailable, returning disabled");
                return ResultNetworkCommunicationDisabled;
            }
            switch (state) {
            case RequestState::NotSubmitted:'''
)
exact(
'''        LOG_WARNING(Service_NIFM, "(STUBBED) called");

        IPC::ResponseBuilder rb{ctx, 2, 2};
        rb.Push(ResultSuccess);
        rb.PushCopyObjects(ctx, event1->GetReadableEvent(), event2->GetReadableEvent());
''',
'''        LOG_WARNING(Service_NIFM, "(STUBBED) called");
        if (system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL) {
            LOG_WARNING(Service_NIFM, "FC26_NIFM GetSystemEventReadableHandles state={}",
                        static_cast<u32>(state));
        }
        IPC::ResponseBuilder rb{ctx, 2, 2};
        rb.Push(ResultSuccess);
        rb.PushCopyObjects(ctx, event1->GetReadableEvent(), event2->GetReadableEvent());
'''
)
exact(
'''    if (!st.connected) {
        out.type = 1;
        out.bars = 0;
        out.state = InternetConnectionStatus::ConnectingUnknown1;''',
'''    const bool fc26_airplane_mode =
        system.GetApplicationProcessProgramID() == 0x01004FF021942000ULL &&
        Settings::values.airplane_mode.GetValue();
    if (!st.connected || fc26_airplane_mode) {
        out.type = 1;
        out.bars = 0;
        out.state = InternetConnectionStatus::ConnectingUnknown1;
        if (fc26_airplane_mode) {
            LOG_WARNING(Service_NIFM, "FC26_NIFM InternetConnectionStatus: offline");
        }'''
)
p.write_text(s)
print("FC26-only NIFM offline request completion/consistency fix applied")
