# Eden FC26 experimental build

This repository builds a test Android APK of Eden with an experimental NCE null-data-fault patch. It does not contain games, keys, or firmware.

In GitHub, open Actions -> Build Eden FC26 test APK -> Run workflow. Download the APK from the `eden-fc26-test` artifact if the build succeeds.

The patch is **not a verified FC26 fix**. It reports null data faults instead of skipping an instruction; it may expose a clearer error without making FC26 launch. Back up app data before testing.
