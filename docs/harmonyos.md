# Kea2 on HarmonyOS / OpenHarmony

Kea2 was Android-first (Fastbot + uiautomator2 + adb). This fork adds a **HarmonyOS path** so the same **property-based testing** style works on real phones via **hdc + hmdriver2**.

## What works

| Feature | Android | HarmonyOS (`--platform harmony`) |
|---|---|---|
| Feature 1 — stress exploration | Fastbot | **Random UI explorer** (no Fastbot binary) |
| Feature 2 — scripted steps | uiautomator2 | **hmdriver2** (`self.d(text=...).click()`) |
| Feature 3 — `@precondition` properties | yes | **yes** |

Roadmap note from upstream: full Hypium/Appium backends later. This is the practical MVP.

## Requirements

- `hdc` on `PATH` (`hdc list targets` shows **Connected**)
- Python 3.8+ with Kea2 deps **and** `hmdriver2`
- Working uitest agent on device (HarmonyOS 6.x often needs agent ~1.1.7)
- Test phone without blocking PIN (or unlocked)

```bash
pip install hmdriver2
# or: uv add hmdriver2
```

## Run

```bash
cd /path/to/Kea2
uv sync   # or pip install -e .
kea2 init   # once per project dir

kea2 run \
  --platform harmony \
  -s <SERIAL> \
  -p com.huawei.hmos.clock \
  --running-minutes 5 \
  --max-step 30 \
  --throttle 800 \
  propertytest discover -p 'test_*.py' -s .
```

## Write a property (same shape as Android)

```python
import unittest
from kea2 import precondition, KeaTestRunner, Options
# self.d is injected by Kea2 (HM driver on Harmony)

class MusicTest(unittest.TestCase):
    @precondition(lambda self: self.d(text="Home").exists())
    def test_home_tab(self):
        self.d(text="Home").click()
        assert self.d(text="Home").exists()
```

Selectors: prefer exact `text=` / `description=` / `id=` from a live `dumpLayout`.  
**Do not** call instance methods inside `@precondition` lambdas if you port old Kea PDL helpers—inline `self.d(...).exists()`.

## Env

| Env | Meaning |
|---|---|
| `HDC_PATH` | path to `hdc` binary |
| `PBT_KEA_ABILITY` | ability name for `aa start` (default `EntryAbility`) |

## Limits (honest)

- Explorer is **weaker** than Fastbot (random taps, not industrial RL).
- No Fastbot activity coverage / monkey agent on Harmony.
- xpath / many u2-only APIs unsupported.
- Enterprise **sample lock** / screen-off still break automation—unlock first.

## Architecture

```
--platform harmony
    → HMDriver (hmdriver2) for self.d
    → HarmonyExplorer for steps (dump + random click)
    → same KeaTestRunner property loop as Android
```
