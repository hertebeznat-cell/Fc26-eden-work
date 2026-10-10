#!/usr/bin/env python3
"""Observe VI display/layer creation and Vulkan frame submissions.

Do not change emulation results. The base FC26 game currently reaches
filesystem initialization but has no visible image; distinguish absent
display/layer creation from frames missing at the presentation backend.
"""
from pathlib import Path

def patch(path: str, old: str, new: str):
    f=Path(path)
    s=f.read_text()
    n=s.count(old)
    if n != 1:
        raise SystemExit(f"FC26 VI trace: expected exactly 1 anchor in {path}; got {n}")
    f.write_text(s.replace(old,new,1))

vi="src/core/hle/service/vi/application_display_service.cpp"
for signature in [
    'Result IApplicationDisplayService::OpenDisplay(Out<u64> out_display_id, DisplayName display_name) {',
    'Result IApplicationDisplayService::OpenDefaultDisplay(Out<u64> out_display_id) {',
    'Result IApplicationDisplayService::GetDisplayResolution(Out<s64> out_width, Out<s64> out_height,',
    'Result IApplicationDisplayService::OpenLayer(Out<u64> out_size,',
    'Result IApplicationDisplayService::CreateStrayLayer(',
    'Result IApplicationDisplayService::GetDisplayVsyncEvent(',
]:
    # Insert warning immediately after signature / opening brace.
    s=Path(vi).read_text()
    start=s.find(signature)
    if start < 0:
        raise SystemExit(f"Missing VI method: {signature}")
    brace=s.find("{",start)
    key=s[start:brace+1]
    if key.count("{") != 1:
        raise SystemExit(f"Unexpected VI signature: {signature}")
    name=signature.split("::")[-1].split("(")[0]
    patch(vi,key,key+'\n    LOG_WARNING(Service_VI, "FC26_VIDEO VI '+name+' invoked");')

renderer="src/video_core/renderer_vulkan/renderer_vulkan.cpp"
patch(renderer,
    'void RendererVulkan::Composite(std::span<const Tegra::FramebufferConfig> framebuffers) {',
    '''void RendererVulkan::Composite(std::span<const Tegra::FramebufferConfig> framebuffers) {
    static std::atomic<u32> fc26_video_frame_count{0};
    const auto fc26_video_frame = fc26_video_frame_count.fetch_add(1, std::memory_order_relaxed);
    if (fc26_video_frame < 8 || fc26_video_frame % 120 == 0) {
        LOG_WARNING(Render_Vulkan,
                    "FC26_VIDEO Composite frame={} framebuffer_count={} shown={}",
                    fc26_video_frame, framebuffers.size(), render_window.IsShown());
    }''')
print("FC26 VI activity and Vulkan Composite tracing installed")
