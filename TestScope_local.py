"""
SI Test Coverage Checker Tool (Local Version)
Compares golden limit files (local copy at C:\\si_test_limits) against
production limit files. No network or GitLab dependency at runtime.
Use UpdateGoldenLimits.bat to sync from GitLab separately.

GUI style modeled after the CDI Test Coverage Verification Tool V1.2.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import csv
import shutil
from pathlib import Path
from datetime import datetime


# --- Configuration ---

# Golden reference (local folder, synced separately via UpdateGoldenLimits.bat)
GOLDEN_LIMITS_DIR = Path(r"C:\si_test_limits")

# Valid tester types (subfolder names in the golden limits folder)
TESTER_TYPES = ["COAX", "HSAL2", "HSALC"]
DEFAULT_TESTER = "HSALC"

# Production tester's active limit files
PRODUCTION_LIMITS_DIR = Path(r"C:\FourPortTester\config\constellation_config\controller\limits")

# Part number lookup (from production tester's parts config)
PARTS_DIR = Path(r"C:\FourPortTester\config\constellation_config\controller\parts")


# --- Comparison Logic ---

def find_part_file(part_number: str) -> Path | None:
    """Search parts subdirectories for the part number JSON file."""
    for series_dir in PARTS_DIR.iterdir():
        if series_dir.is_dir():
            part_file = series_dir / f"{part_number}.json"
            if part_file.exists():
                return part_file
    return None


def load_json(file_path: Path) -> dict | None:
    """Load and parse a JSON file. Returns None if file doesn't exist or is invalid."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {file_path.name}: {e}")


def compare_limits(golden: dict, production: dict) -> list[str]:
    """
    Compare two limit file dictionaries.
    Returns a list of difference descriptions. Empty list = match.
    """
    differences = []

    golden_limits = golden.get("limits", {})
    production_limits = production.get("limits", {})

    golden_keys = list(golden_limits.keys())
    production_keys = list(production_limits.keys())

    # Check for missing parameters (in golden but not in production)
    missing = [k for k in golden_keys if k not in production_keys]
    if missing:
        differences.append("MISSING PARAMETERS (in golden but not in production):")
        for param in missing:
            differences.append(f"  • {param}")
        differences.append("")

    # Check for extra parameters (in production but not in golden)
    extra = [k for k in production_keys if k not in golden_keys]
    if extra:
        differences.append("EXTRA PARAMETERS (in production but not in golden):")
        for param in extra:
            differences.append(f"  • {param}")
        differences.append("")

    # Check parameter order (only for parameters that exist in both)
    common_golden_order = [k for k in golden_keys if k in production_keys]
    common_production_order = [k for k in production_keys if k in golden_keys]

    if common_golden_order != common_production_order:
        differences.append("ORDER MISMATCH:")
        differences.append(f"  Golden order:     {', '.join(common_golden_order)}")
        differences.append(f"  Production order: {', '.join(common_production_order)}")
        differences.append("")

    # Check value mismatches for common parameters
    value_diffs = []
    for param in common_golden_order:
        golden_param = golden_limits[param]
        production_param = production_limits[param]

        if golden_param != production_param:
            param_diffs = _compare_parameter(param, golden_param, production_param)
            value_diffs.extend(param_diffs)

    if value_diffs:
        differences.append("VALUE MISMATCHES:")
        differences.extend(value_diffs)
        differences.append("")

    return differences


def _compare_parameter(param_name: str, golden_param: dict, production_param: dict) -> list[str]:
    """Compare a single parameter's ranges/transforms between golden and production."""
    diffs = []

    # Compare ranges
    golden_ranges = golden_param.get("ranges", [])
    production_ranges = production_param.get("ranges", [])

    if len(golden_ranges) != len(production_ranges):
        diffs.append(f"  • {param_name}: Different number of ranges "
                     f"(golden={len(golden_ranges)}, production={len(production_ranges)})")
    else:
        for i, (g_range, p_range) in enumerate(zip(golden_ranges, production_ranges)):
            range_diffs = _compare_range(param_name, i, g_range, p_range)
            diffs.extend(range_diffs)

    # Compare transforms
    golden_transforms = golden_param.get("transforms", [])
    production_transforms = production_param.get("transforms", [])

    if golden_transforms != production_transforms:
        diffs.append(f"  • {param_name}: Transform mismatch")
        if len(golden_transforms) != len(production_transforms):
            diffs.append(f"    Golden has {len(golden_transforms)} transform(s), "
                         f"production has {len(production_transforms)}")
        else:
            for i, (g_t, p_t) in enumerate(zip(golden_transforms, production_transforms)):
                for key in set(list(g_t.keys()) + list(p_t.keys())):
                    if g_t.get(key) != p_t.get(key):
                        diffs.append(f"    Transform[{i}].{key}: "
                                     f"golden={g_t.get(key)} vs production={p_t.get(key)}")

    return diffs


def _compare_range(param_name: str, index: int, golden_range: dict, production_range: dict) -> list[str]:
    """Compare a single range entry between golden and production."""
    diffs = []
    zone = golden_range.get("description", f"range[{index}]")

    for key in set(list(golden_range.keys()) + list(production_range.keys())):
        g_val = golden_range.get(key)
        p_val = production_range.get(key)
        if g_val != p_val:
            diffs.append(f"  • {param_name} ({zone}) → {key}: "
                         f"golden={g_val} vs production={p_val}")

    return diffs


# --- Structured Orchestrator for GUI ---

def check_part_for_gui(part_number: str, tester_type: str) -> list[dict]:
    """
    Check a part number against golden limits and return structured results.
    Returns a list of dicts — one row per individual issue found.
    A MATCH produces one row; an UNMATCH produces one row per issue.
    """
    check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _make_row(status, limit_file, limit_type, issue, parameter, details):
        return {
            "status": status,
            "part_number": part_number,
            "tester_type": tester_type,
            "limit_file": limit_file,
            "limit_type": limit_type,
            "issue": issue,
            "parameter": parameter,
            "details": details,
            "check_time": check_time,
        }

    # Verify golden limits folder exists
    golden_tester_dir = GOLDEN_LIMITS_DIR / tester_type
    if not golden_tester_dir.exists():
        return [_make_row("ERROR", "N/A", "N/A", "FOLDER NOT FOUND", "",
                          f"Golden limits folder not found: {golden_tester_dir}\n"
                          f"Run UpdateGoldenLimits.bat to download from GitLab.")]

    # Find the part file
    part_file = find_part_file(part_number)
    if part_file is None:
        return [_make_row("ERROR", "N/A", "N/A", "FILE NOT FOUND",
                          "", f"Part number '{part_number}' not found in parts directory.")]

    # Load part configuration
    try:
        part_config = load_json(part_file)
    except ValueError as e:
        return [_make_row("ERROR", "N/A", "N/A", "PARSE ERROR", "", str(e))]

    if part_config is None:
        return [_make_row("ERROR", "N/A", "N/A", "LOAD ERROR",
                          "", f"Could not load part file for '{part_number}'.")]

    # Extract limit file references
    primary_limits_name = part_config.get("cable", {}).get("limits")
    background_limits_name = part_config.get("failure_limits")

    if not primary_limits_name:
        return [_make_row("ERROR", "N/A", "N/A", "CONFIG ERROR",
                          "", f"Part '{part_number}' has no 'cable.limits' field defined.")]

    # Build list of files to check
    files_to_check = [(primary_limits_name, "PRIMARY LIMITS")]
    if background_limits_name:
        files_to_check.append((background_limits_name, "BACKGROUND LIMITS"))

    results = []

    for limits_name, label in files_to_check:
        golden_path = GOLDEN_LIMITS_DIR / tester_type / f"{limits_name}.json"
        production_path = PRODUCTION_LIMITS_DIR / f"{limits_name}.json"
        limit_file = f"{limits_name}.json"

        # Load golden
        try:
            golden_data = load_json(golden_path)
        except ValueError as e:
            results.append(_make_row("ERROR", limit_file, label, "PARSE ERROR", "", str(e)))
            continue

        if golden_data is None:
            results.append(_make_row("ERROR", limit_file, label, "FILE NOT FOUND",
                                     "", f"Golden file not found: {limit_file}"))
            continue

        # Load production
        try:
            production_data = load_json(production_path)
        except ValueError as e:
            results.append(_make_row("ERROR", limit_file, label, "PARSE ERROR", "", str(e)))
            continue

        if production_data is None:
            results.append(_make_row("UNMATCH", limit_file, label, "FILE MISSING",
                                     "", f"Production file not found: {limit_file}"))
            continue

        # Compare limits — one row per individual issue
        golden_limits = golden_data.get("limits", {})
        production_limits = production_data.get("limits", {})
        golden_keys = list(golden_limits.keys())
        production_keys = list(production_limits.keys())

        has_issues = False

        # Missing parameters (in golden but not in production)
        missing = [k for k in golden_keys if k not in production_keys]
        for param in missing:
            has_issues = True
            results.append(_make_row("UNMATCH", limit_file, label,
                                     "MISSING PARAM", param,
                                     "In golden but not in production"))

        # Extra parameters (in production but not in golden)
        extra = [k for k in production_keys if k not in golden_keys]
        for param in extra:
            has_issues = True
            results.append(_make_row("UNMATCH", limit_file, label,
                                     "EXTRA PARAM", param,
                                     "In production but not in golden"))

        # Order mismatch
        common_golden = [k for k in golden_keys if k in production_keys]
        common_prod = [k for k in production_keys if k in golden_keys]
        if common_golden != common_prod:
            has_issues = True
            results.append(_make_row("UNMATCH", limit_file, label,
                                     "ORDER MISMATCH", "",
                                     f"Golden: {', '.join(common_golden[:5])}... "
                                     f"vs Production: {', '.join(common_prod[:5])}..."))

        # Value mismatches — one row per mismatched parameter
        for param in common_golden:
            golden_param = golden_limits[param]
            production_param = production_limits[param]
            if golden_param != production_param:
                has_issues = True
                param_diffs = _compare_parameter(param, golden_param, production_param)
                detail_text = "; ".join(d.strip().lstrip("• ") for d in param_diffs if d.strip())
                results.append(_make_row("UNMATCH", limit_file, label,
                                         "VALUE MISMATCH", param, detail_text))

        # If no issues found — it's a MATCH
        if not has_issues:
            results.append(_make_row("MATCH", limit_file, label,
                                     "OK", "", "All parameters match."))

    return results


# --- GUI ---

TREEVIEW_COLUMNS = (
    "Status", "Part Number", "Tester", "Limit File", "Type",
    "Issue", "Parameter", "Details", "Check Time"
)

COLUMN_WIDTHS = {
    "Status": 100, "Part Number": 120, "Tester": 80,
    "Limit File": 250, "Type": 130, "Issue": 140,
    "Parameter": 150, "Details": 400, "Check Time": 150,
}

# Maps Treeview column names to result dict keys
COLUMN_KEYS = {
    "Status": "status",
    "Part Number": "part_number",
    "Tester": "tester_type",
    "Limit File": "limit_file",
    "Type": "limit_type",
    "Issue": "issue",
    "Parameter": "parameter",
    "Details": "details",
    "Check Time": "check_time",
}


class SITestCoverageCheckerApp:
    """Tkinter GUI for the SI Test Coverage Checker (fully local, no network)."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TestScope Local — SI Test Coverage Checker")
        self.root.geometry("1200x700")

        self.results = []
        self.tester_var = tk.StringVar(value=DEFAULT_TESTER)
        self.part_var = tk.StringVar()
        self.summary_var = tk.StringVar(value="Ready — Run UpdateGoldenLimits.bat to sync golden files from GitLab")

        self._build_gui()
        self._configure_tree_tags()
        self._check_golden_folder()

    def _build_gui(self):
        # Main container
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        # --- Input Frame ---
        input_frame = ttk.LabelFrame(main, text="Input", padding=10)
        input_frame.pack(fill="x", pady=(0, 10))

        # Row 0: Tester Type radio buttons
        ttk.Label(input_frame, text="Tester Type:").grid(row=0, column=0, sticky="w")
        radio_frame = ttk.Frame(input_frame)
        radio_frame.grid(row=0, column=1, columnspan=3, sticky="w", padx=5)
        for ttype in TESTER_TYPES:
            ttk.Radiobutton(
                radio_frame, text=ttype,
                variable=self.tester_var, value=ttype,
            ).pack(side="left", padx=(0, 20))

        # Row 1: Part Number entry + CHECK button
        ttk.Label(input_frame, text="Part Number:").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        part_entry = ttk.Entry(input_frame, textvariable=self.part_var, width=40)
        part_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=(8, 0))
        part_entry.bind("<Return>", lambda e: self._on_check())

        ttk.Button(input_frame, text="CHECK", command=self._on_check).grid(
            row=1, column=2, padx=3, pady=(8, 0)
        )

        input_frame.columnconfigure(1, weight=1)

        # --- Action Buttons ---
        action_frame = ttk.Frame(main)
        action_frame.pack(fill="x", pady=(0, 10))
        ttk.Button(action_frame, text="Clear Results", command=self._clear_results).pack(
            side="left"
        )
        ttk.Button(action_frame, text="Export Results CSV", command=self._export_csv).pack(
            side="left", padx=8
        )

        # --- Treeview Table ---
        self.tree = ttk.Treeview(main, columns=TREEVIEW_COLUMNS, show="headings")
        for col in TREEVIEW_COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=COLUMN_WIDTHS.get(col, 120), anchor="w")
        self.tree.pack(fill="both", expand=True)

        # Horizontal scrollbar
        scrollbar_x = ttk.Scrollbar(main, orient="horizontal", command=self.tree.xview)
        scrollbar_x.pack(fill="x")
        self.tree.configure(xscrollcommand=scrollbar_x.set)

        # --- Summary Label ---
        ttk.Label(main, textvariable=self.summary_var).pack(anchor="w", pady=(10, 0))

        # Focus the part entry on startup
        part_entry.focus_set()

    def _configure_tree_tags(self):
        """Configure row colors matching CDI tool style."""
        self.tree.tag_configure("MATCH", background="#d9ead3")
        self.tree.tag_configure("UNMATCH", background="#f4cccc")
        self.tree.tag_configure("ERROR", background="#fff2cc")
        self.tree.tag_configure("FIXED", background="#b6d7a8")

    def _check_golden_folder(self):
        """Warn on startup if golden limits folder is missing."""
        if not GOLDEN_LIMITS_DIR.exists():
            messagebox.showwarning(
                "Golden Limits Not Found",
                f"Golden limits folder not found:\n{GOLDEN_LIMITS_DIR}\n\n"
                f"Run UpdateGoldenLimits.bat to download from GitLab first."
            )

    def _on_check(self):
        """Handle the CHECK button click — fully local, no network call."""
        part_number = self.part_var.get().strip()
        if not part_number:
            messagebox.showwarning("Input Required", "Please enter a part number.")
            return

        tester_type = self.tester_var.get()

        # Run structured check (no GitLab sync — fully local)
        check_results = check_part_for_gui(part_number, tester_type)

        # Insert results into Treeview
        for result in check_results:
            self.results.append(result)
            values = tuple(result[COLUMN_KEYS[col]] for col in TREEVIEW_COLUMNS)
            self.tree.insert("", "end", values=values, tags=(result["status"],))

        # Auto-fix: offer to copy golden files if mismatches found
        mismatched_files = sorted(set(
            r["limit_file"] for r in check_results
            if r["status"] == "UNMATCH" and r["limit_file"] != "N/A"
        ))

        if mismatched_files:
            file_list = "\n".join(f"  • {f}" for f in mismatched_files)
            fix = messagebox.askyesno(
                "Mismatch Detected",
                f"Found mismatches in {len(mismatched_files)} limit file(s):\n"
                f"{file_list}\n\n"
                f"Copy correct golden files to production?"
            )
            if fix:
                self._auto_fix(mismatched_files, tester_type)

        # Update summary
        self._update_summary()

        # Clear entry for next check
        self.part_var.set("")

    def _auto_fix(self, mismatched_files, tester_type):
        """Copy golden limit files from local golden folder to production directory."""
        check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        copied = []
        failed = []

        for limit_file in mismatched_files:
            golden_path = GOLDEN_LIMITS_DIR / tester_type / limit_file
            production_path = PRODUCTION_LIMITS_DIR / limit_file

            try:
                shutil.copy2(str(golden_path), str(production_path))
                copied.append(limit_file)

                # Add a FIXED row to the Treeview
                fix_row = {
                    "status": "FIXED",
                    "part_number": "",
                    "tester_type": tester_type,
                    "limit_file": limit_file,
                    "limit_type": "",
                    "issue": "AUTO-FIX",
                    "parameter": "",
                    "details": f"Copied from {GOLDEN_LIMITS_DIR / tester_type} → {PRODUCTION_LIMITS_DIR}",
                    "check_time": check_time,
                }
                self.results.append(fix_row)
                values = tuple(fix_row[COLUMN_KEYS[col]] for col in TREEVIEW_COLUMNS)
                self.tree.insert("", "end", values=values, tags=("FIXED",))

            except Exception as e:
                failed.append(f"{limit_file}: {e}")

        if copied and not failed:
            messagebox.showinfo(
                "Auto-Fix Complete",
                f"Successfully copied {len(copied)} file(s) to production.\n\n"
                f"Re-check the part number to verify the fix."
            )
        elif failed:
            messagebox.showwarning(
                "Auto-Fix Partial",
                f"Copied {len(copied)} file(s), but {len(failed)} failed:\n"
                + "\n".join(failed)
            )

    def _update_summary(self):
        """Update the summary label with accumulated counts."""
        total = len(self.results)
        match_count = sum(1 for r in self.results if r["status"] == "MATCH")
        issue_count = sum(1 for r in self.results if r["status"] == "UNMATCH")
        error_count = sum(1 for r in self.results if r["status"] == "ERROR")
        self.summary_var.set(
            f"Total rows: {total}  |  "
            f"MATCH: {match_count},  Issues: {issue_count},  Errors: {error_count}"
        )

    def _clear_results(self):
        """Clear the Treeview and reset summary."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results = []
        self.summary_var.set("Ready")

    def _export_csv(self):
        """Export accumulated results to a CSV file."""
        if not self.results:
            messagebox.showwarning("No Results", "Run at least one check before exporting.")
            return

        default_name = f"si_coverage_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        output = filedialog.asksaveasfilename(
            title="Save results", defaultextension=".csv", initialfile=default_name,
            filetypes=[("CSV files", "*.csv")]
        )
        if not output:
            return

        fields = list(TREEVIEW_COLUMNS)
        with open(output, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for result in self.results:
                row = {col: result[COLUMN_KEYS[col]] for col in fields}
                writer.writerow(row)

        messagebox.showinfo("Export Complete", f"Results saved:\n{output}")

    def run(self):
        """Start the application."""
        self.root.mainloop()


if __name__ == "__main__":
    app = SITestCoverageCheckerApp()
    app.run()
