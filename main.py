import argparse
import re
from pathlib import Path

import pandas as pd


SECTION_RE = re.compile(r"^\[result\.(?P<element>\S+)\s+(?P<group>[^\]]+)\]\s*$")
KEY_VALUE_RE = re.compile(r"^(?P<name>[^=]+?)\s*=\s*(?P<value>.*)\s*$")
TARGET_FIELDS = ["fitarea", "sigmaarea", "energy", "ratio", "fwhm", "chisq"]
OUTPUT_COLUMNS = ["element", "group", *TARGET_FIELDS]
SUMMARY_COLUMNS = ["element", "group", "sample", "fitarea", "sigma"]


def parse_scalar(value: str):
	value = value.strip()
	if not value:
		return ""

	lowered = value.lower()
	if lowered in {"true", "false"}:
		return lowered == "true"

	try:
		if any(ch in value for ch in (".", "e", "E")):
			return float(value)
		return int(value)
	except ValueError:
		return value


def parse_fit_file(file_path: Path) -> pd.DataFrame:
	rows = []
	current_element = None
	current_group = None
	current_row = None

	def flush_current_row():
		nonlocal current_row
		if current_row is None:
			return
		if any(current_row[field] is not None for field in TARGET_FIELDS):
			rows.append(current_row)
		current_row = None

	with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
		for raw_line in handle:
			line = raw_line.strip()
			if not line:
				continue

			section_match = SECTION_RE.match(line)
			if section_match:
				flush_current_row()
				current_element = section_match.group("element").strip()
				current_group = section_match.group("group").strip()
				current_row = {
					"element": current_element,
					"group": current_group,
					"fitarea": None,
					"sigmaarea": None,
					"energy": None,
					"ratio": None,
					"fwhm": None,
					"chisq": None,
				}
				continue

			if current_element is None or current_group is None or current_row is None:
				continue

			kv_match = KEY_VALUE_RE.match(line)
			if not kv_match:
				continue

			name = kv_match.group("name").strip()
			if name in TARGET_FIELDS:
				current_row[name] = parse_scalar(kv_match.group("value"))

	flush_current_row()

	return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def build_summary_row(df: pd.DataFrame, element: str, group: str, sample_name: str):
	element_rows = df[
		(df["element"] == element)
		& (df["group"] == group)
	]

	if element_rows.empty:
		return {
			"element": element,
			"group": group,
			"sample": sample_name,
			"fitarea": None,
			"sigma": None,
		}

	fitarea_sum = pd.to_numeric(element_rows["fitarea"], errors="coerce").fillna(0.0).sum()
	sigma_vals = pd.to_numeric(element_rows["sigmaarea"], errors="coerce").fillna(0.0)
	sigma_combined = (sigma_vals.pow(2).sum()) ** 0.5

	return {
		"element": element,
		"group": group,
		"sample": sample_name,
		"fitarea": fitarea_sum,
		"sigma": sigma_combined,
	}


def parse_elements_arg(elements_arg: str | None):
	if not elements_arg:
		return []

	parsed = []
	for part in elements_arg.split(","):
		item = part.strip()
		if not item:
			continue
		if ":" not in item:
			raise ValueError(
				f"Invalid --elements item '{item}'. Expected format element:group (example: Ar:K)."
			)
		element, group = item.split(":", 1)
		element = element.strip()
		group = group.strip()
		if not element or not group:
			raise ValueError(
				f"Invalid --elements item '{item}'. Both element and group must be non-empty."
			)
		parsed.append((element, group))

	return parsed


def process_fit_files(input_dir: Path, recursive: bool = False, elements: list[tuple[str, str]] | None = None) -> int:
	pattern = "**/*.fit" if recursive else "*.fit"
	fit_files = sorted(input_dir.glob(pattern))
	requested_elements = elements or []
	summary_rows = []

	if not fit_files:
		print(f"No .fit files found in: {input_dir}")
		return 0

	processed = 0
	for fit_file in fit_files:
		df = parse_fit_file(fit_file)
		output_csv = fit_file.with_suffix(".csv")
		sample_name = fit_file.name.split(".")[0]

		df.to_csv(output_csv, index=False)
		print(f"Saved: {output_csv}")

		for element, group in requested_elements:
			summary_rows.append(build_summary_row(df, element, group, sample_name))

		processed += 1

	if requested_elements:
		summary_df = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)
		summary_df = summary_df.sort_values(["element", "group", "sample"], ascending=[True, True, True], kind="stable")
		summary_path = input_dir / "output.csv"
		summary_df.to_csv(summary_path, index=False, decimal=".", sep=";")
		print(f"Saved: {summary_path}")

	print(f"Done. Processed {processed} file(s).")
	return processed


def main():
	parser = argparse.ArgumentParser(
		description="Parse [result.<element> <group>] sections from .fit files into CSV files."
	)
	parser.add_argument(
		"input_dir",
		nargs="?",
		default="html",
		help="Directory containing .fit files (default: html)",
	)
	parser.add_argument(
		"--recursive",
		action="store_true",
		help="Recursively search for .fit files in subdirectories.",
	)
	parser.add_argument(
		"--elements",
		default=None,
		help="Comma-separated list in element:group format for summary output.csv (example: Ar:K,Mn:K).",
		required=True
	)
	args = parser.parse_args()

	input_dir = Path(args.input_dir)
	if not input_dir.exists() or not input_dir.is_dir():
		raise SystemExit(f"Input directory does not exist or is not a directory: {input_dir}")

	try:
		elements = parse_elements_arg(args.elements)
	except ValueError as exc:
		raise SystemExit(str(exc))
	process_fit_files(input_dir=input_dir, recursive=args.recursive, elements=elements)


if __name__ == "__main__":
	main()

