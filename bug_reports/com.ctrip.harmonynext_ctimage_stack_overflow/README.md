# 携程 CTImage Stack overflow (jscrash)

Developer-facing package for a confirmed HarmonyOS JS crash in 携程.

| | |
|--|--|
| App | `com.ctrip.harmonynext` 8.94.6 |
| Bug | `@ctcommon/ctimage` reactive loop → `RangeError: Stack overflow!` |
| Full write-up | **[BUG_REPORT.md](./BUG_REPORT.md)** |
| Repro | `bash repro.sh` |

Send **BUG_REPORT.md** + at least one `jscrash-*.log` / `crash-dump_*.log` to component owners.
