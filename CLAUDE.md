# watch8 — Watch Face Format (WFF) v4 for Galaxy Watch 8

## The rule: no rendering code, ever

Watch Face Format is **declarative XML only**. The entire watch face is
`MinimalAnalog/watchface/src/main/res/raw/watchface.xml` plus the drawables it
references.

Never add rendering code to this project. Concretely, do not add:

- any `.java` or `.kt` source, or a `src/main/java` / `src/main/kotlin` tree;
- a `WatchFaceService`, `Renderer`, `CanvasRenderer`, or any `androidx.wear.watchface.*` dependency;
- any dependency block in `watchface/build.gradle.kts` at all;
- `android:hasCode="true"`, or removal of `android:hasCode="false"`.

`android:hasCode="false"` and `enableKotlin = false` are load-bearing: the WFF
runtime (`com.google.wear.watchface.runtime`) renders the XML, and a WFF package
that ships code is rejected. If something seems to need code, it is either a
WFF feature that already exists (expressions, `Condition`, `Variant`,
`Transform`) or it is out of scope — ask, do not write a renderer.

Behaviour changes go in `watchface.xml`. Asset changes go through
`MinimalAnalog/tools/gen_assets.py`, which is a build-time generator, not
runtime code.

## Version and platform

| Setting | Value | Source |
| --- | --- | --- |
| WFF version | **4** | `com.google.wear.watchface.format.version` property in `AndroidManifest.xml` |
| `minSdk` / `compileSdk` | 36 (Wear OS 6) | copied from the WFF v4 samples |
| `targetSdk` | 37 | copied from the WFF v4 samples |
| AGP | 9.0.0 | `gradle/libs.versions.toml` |
| Gradle | 9.2.1 | `gradle/wrapper/gradle-wrapper.properties` |
| Canvas | 450×450 | `<WatchFace width="450" height="450">` |

These were taken from the `PhotosMask` and `PhotosMulti` samples in
[android/wear-os-samples](https://github.com/android/wear-os-samples) — the only
two samples that declare WFF version 4 — not from memory. `SimpleAnalog` and
`SimpleDigital` are **version 1** samples (`compileSdk = 33`); do not copy build
config from them. The validator supports up to WFF v5.

## Layout

```
MinimalAnalog/
├── Makefile                        the build loop (see below)
├── settings.gradle.kts             rootProject "MinimalAnalog", includes :watchface
├── build.gradle.kts                declares AGP, applies nothing
├── gradle/libs.versions.toml       AGP version catalog
├── tools/gen_assets.py             generates the drawables + preview
└── watchface/
    ├── build.gradle.kts            enableKotlin = false, no dependencies block
    └── src/main/
        ├── AndroidManifest.xml     hasCode=false, format.version=4
        └── res/
            ├── raw/watchface.xml   the entire watch face
            ├── drawable-nodpi/     hour/minute/second/preview PNGs
            ├── values/strings.xml  watch_face_name
            └── xml/watch_face_info.xml   preview declaration
```

Drawables live in `drawable-nodpi/` on purpose: the platform must not rescale
them, and the memory evaluator charges 4 bytes per pixel of the decoded bitmap,
so each PNG is authored at exactly the size it is drawn at.

## Build loop

All commands run from `MinimalAnalog/`. `make help` lists them.

```shell
make tools      # clone google/watchface and build both jars into .tools/
make assets     # regenerate res/drawable-nodpi/*.png
make validate   # XSD-validate watchface.xml at WFF v4; any SEVERE fails
make assemble   # build the APK
make memcheck   # memory footprint of the APK; over limit fails
make deploy     # validate, assemble, install, set as active watch face
make logs       # logcat filtered to the WFF runtime process
make check      # validate + assemble + memcheck
```

Useful overrides: `BUILD_TYPE=debug`, `SERIAL=<ip:port>`,
`ACTIVE_LIMIT_MB=`, `AMBIENT_LIMIT_MB=`, `WFF_VERSION=`.

### Tooling

Both jars are built from source out of
[google/watchface](https://github.com/google/watchface) by `make tools`:

```shell
git clone --depth 1 https://github.com/google/watchface.git .tools/watchface
cd .tools/watchface/play-validations
./gradlew :validator:executable-jar        # -> third_party/wff/specification/validator/build/libs/wff-validator.jar
./gradlew :memory-footprint:executable-jar # -> memory-footprint/build/libs/memory-footprint.jar
```

### Validator, invoked directly

```shell
java -jar .tools/wff-validator.jar 4 --stop-on-fail \
  watchface/src/main/res/raw/watchface.xml
```

Usage is `<format-version> [options] <xml>...`. Findings print to **stderr** at
`SEVERE:` level with line and column, e.g.

```
SEVERE: [Line 113:Column 46]: cvc-enumeration-valid: Value 'NOT_A_FREQUENCY' is not facet-valid ...
```

`--stop-on-fail` makes it exit non-zero. `make validate` additionally greps for
`^SEVERE:` and fails on any hit, so a SEVERE can never pass silently even if the
exit code were to change.

### Memory footprint evaluator, invoked directly

```shell
java -jar .tools/memory-footprint.jar \
  --watch-face watchface/build/outputs/apk/release/watchface-release.apk \
  --schema-version 4 \
  --ambient-limit-mb 10 \
  --active-limit-mb 100 \
  --apply-v1-offload-limitations \
  --estimate-optimization \
  --verbose
```

`--verbose` prints the figures; the interactive number is the "active" one:

```
Total images memory footprint: X.XX MB
Max memory footprint in active: X.XX MB
Max memory footprint in ambient: X.XX MB
```

It exits 1 when either limit is exceeded, so `make memcheck` fails the build.
Add `--report` for JSON instead of the pass/fail test. The 10 MB ambient /
100 MB active limits come from `play-validations/README.md`; they are described
upstream as reasonable evaluation settings, not a guarantee of what Play
enforces.

### Runtime logs

A WFF watch face has no process of its own — it is rendered by the WFF runtime,
so that is where errors land:

```shell
adb logcat --pid=$(adb shell pidof -s com.google.wear.watchface.runtime) '*:W'
```

Typical failures: `Invalid resource ID 0x00000000` (a `resource=` name that does
not exist in `drawable-nodpi/`), and warnings about unparseable expressions,
which the XSD cannot catch because it only checks syntax.

## Pairing the Galaxy Watch 8 over wireless debugging

Nothing here assumes a connection exists. `make pair-help` reprints this.

On the watch, once:

1. Settings → About watch → Software info → tap **Software version** 7×.
2. Settings → Developer options → **ADB debugging** → On.
3. Settings → Developer options → **Wireless debugging** → On.
4. Put the watch on the same Wi-Fi network as the workstation.

Then, from `MinimalAnalog/`:

```shell
# 1. Watch: Wireless debugging > Pair new device.
#    It shows an IP:PORT and a 6-digit code. Both are single-use.
adb pair <ip>:<pairing-port> <code>

# 2. Watch: the Wireless debugging main screen shows IP and Port.
#    This port is DIFFERENT from the pairing port.
adb connect <ip>:<port>

# 3. Confirm.
adb devices -l          # expect "<ip>:<port>   device"

# 4. Deploy.
make deploy SERIAL=<ip:port>
```

Pairing is once per workstation. The connect port changes after a watch reboot
or a Wi-Fi drop, so step 2 is the one to repeat. If `adb devices` shows
`unauthorized`, accept the prompt on the watch.

### Setting the active watch face

`make deploy` ends with the debug-surface broadcast:

```shell
adb shell am broadcast -a com.google.android.wearable.app.DEBUG_SURFACE \
  --es operation set-watchface \
  --es watchFaceId 'com.watch8.minimalanalog'
```

WFF watch faces are identified by **package id** via `--es watchFaceId`, not by
a component name — there is no service class to point at.

## Current face

Minimal analog, WFF v4:

- black background, 12 vector hour markers (no bitmap cost);
- hour / minute / second hands as `drawable-nodpi` PNGs, white, coloured
  declaratively with `tintColor`;
- one date element — short weekday plus day of month;
- one step-count element — `[STEP_COUNT]`, which needs no manifest permission;
- an ambient variant that removes the second hand and the centre cap
  (`alpha` → 0) and dims the markers and text.

`PREVIEW_TIME` is `10:08:32` and `tools/gen_assets.py` renders `preview.png` at
that same time, so the two stay in sync.

**Not present, by instruction: complications and animation.** Ask before adding
either.
