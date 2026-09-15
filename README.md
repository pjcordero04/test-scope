# TestScope

Automated limit file verification tool for Constellation FourPort cable testers. Compares production test configuration against a golden reference to catch missing or modified parameters before production runs.

## Background

At another facility, engineers disabled a test parameter during tester maintenance. After the repair, the parameter was not re-enabled. Parts tested with the incomplete sequence escaped to the field and caused quality issues. TestScope was developed as a preventive measure to ensure the same problem cannot occur.

## How It Works

```
UpdateGoldenLimits.bat          TestScope_local.exe
(run when on network)           (runs fully offline)
        │                               │
        ▼                               ▼
   GitLab repo ──────▶ C:\si_test_limits ◀──── Golden reference
                                        │
                          Compare ◀─────┘
                                        │
   C:\FourPortTester\...\limits ◀───────┘──── Production limits
                                        │
                                        ▼
                              MATCH or UNMATCH
```

1. **Sync golden reference** — Run `UpdateGoldenLimits.bat` to pull the latest approved limit files from GitLab to a local folder (`C:\si_test_limits`). This is the only step that requires network access.
2. **Select tester type** — Choose COAX, HSAL2, or HSALC (each has its own set of limit files with different parameters and thresholds).
3. **Enter part number** — The app looks up which limit files the part uses from the tester's parts config.
4. **Click CHECK** — Compares the golden file against the production file. Both the primary limits and background limits are checked.
5. **View results** — MATCH (green) means the tester is correctly configured. UNMATCH (red) shows exactly what's wrong with one row per issue.
6. **Auto-fix** — If mismatches are found, the app offers to copy the correct golden files to the production directory.

## What Gets Compared

For each limit file, the tool checks five things:

| Check | Detects |
|-------|---------|
| Parameter existence | Missing or extra test parameters |
| Parameter order | Sequence changes in the test flow |
| Frequency/time ranges | Modified start/stop sweep values |
| Pass/fail thresholds | Changed upper/lower limit bounds |
| Zone definitions | Altered TDR impedance zone boundaries |

### Parameters covered

- **S-parameters**: SDD11, SDD22, SDD21, SCD21, SDC21, SCD12, SDC12, S2_1, S4_3
- **Impedance zones**: Plug Solder, Foil Strip, Raw Cable, PCB Trace, Header Waterfall
- **Derived metrics**: ILD, ILFITATNQ, IMR, IRL, Length

## Tester Types

The golden reference is organized by tester type. Each subfolder under `C:\si_test_limits` contains limit files specific to that test platform:

| Type | Description | Measurement Mode |
|------|-------------|-----------------|
| COAX | Coaxial cable tester | Single-ended (S1_1, Z1_1) |
| HSAL2 | HSAL Gen 2 tester | Differential (SDD11, ZDD11) |
| HSALC | HSALC FourPort tester | Differential (SDD11, ZDD11) |

Some limit files share the same name across tester types but have different content (e.g., `background_limits.json` uses single-ended parameters for COAX but differential parameters for HSALC). The tester type selection ensures the correct golden file is used.

## Directory Structure

```
C:\si_test_limits\              ← Golden reference (synced from GitLab)
├── COAX\
│   └── *.json                  ← 55 limit files
├── HSAL2\
│   └── *.json                  ← 25 limit files
└── HSALC\
    └── *.json                  ← 11 limit files

C:\FourPortTester\config\constellation_config\controller\
├── limits\                     ← Production limit files (checked against golden)
│   └── *.json
└── parts\                      ← Part number configs (maps part → limit file)
    ├── 103994\
    ├── 310044\
    └── 310052\
```

## Installation

### Prerequisites

- Windows PC (tester workstation)
- Git installed (for `UpdateGoldenLimits.bat`)
- Network access to GitLab (only for syncing golden files)

### Setup

1. Copy `TestScope_local.exe` and `UpdateGoldenLimits.bat` to the tester workstation
2. Run `UpdateGoldenLimits.bat` — this clones the golden limits repo to `C:\si_test_limits`
3. Run `TestScope_local.exe` — the app works fully offline from this point

### Building from Source

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "TestScope_local" --icon="testscope.ico" TestScope_local.py
```

The exe is output to `dist\TestScope_local.exe` (~11 MB, includes Python + tkinter).

## Usage

### Sync golden files (when on network)

Double-click `UpdateGoldenLimits.bat`. It will:
- Clone the repo on first run
- Pull latest changes on subsequent runs
- Set all limit files to read-only to prevent accidental edits

### Check a part

1. Open `TestScope_local.exe`
2. Select the tester type (COAX / HSAL2 / HSALC)
3. Enter a part number (e.g., `3100520083`)
4. Click **CHECK**

### Results

| Row Color | Status | Meaning |
|-----------|--------|---------|
| Green | MATCH | Limit file matches golden reference |
| Red | UNMATCH | Differences found — details in the row |
| Yellow | ERROR | File not found or parse error |
| Dark green | FIXED | Golden file was copied to production |

### Export

Click **Export Results CSV** to save all check results to a CSV file for audit records.

## Configuration

All paths are defined at the top of `TestScope_local.py`:

```python
GOLDEN_LIMITS_DIR = Path(r"C:\si_test_limits")
PRODUCTION_LIMITS_DIR = Path(r"C:\FourPortTester\config\constellation_config\controller\limits")
PARTS_DIR = Path(r"C:\FourPortTester\config\constellation_config\controller\parts")
```

## Files

| File | Purpose |
|------|---------|
| `TestScope_local.py` | Main application (fully offline) |
| `UpdateGoldenLimits.bat` | Syncs golden reference from GitLab |
| `testscope.ico` | Application icon |
| `README.md` | This file |
