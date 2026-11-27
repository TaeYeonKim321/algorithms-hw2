import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments import compare_hash_tables


class CompareHashTablesTests(unittest.TestCase):
    def test_experiment_uses_specified_bucket_count_and_load_factors(self):
        self.assertEqual(compare_hash_tables.BUCKET_COUNT, 4093)
        self.assertEqual(
            tuple(compare_hash_tables.LOAD_FACTORS),
            tuple(step / 10 for step in range(1, 10)),
        )
        self.assertEqual(compare_hash_tables.REPEAT_COUNT, 5)

    def test_csv_contains_all_load_points_repeat_count_and_both_lookup_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            records = []

            def recording_factory(strategy, table_class):
                class RecordingTable:
                    def __init__(self, *args, **kwargs):
                        self.table = table_class(*args, **kwargs)
                        self.keys = []
                        records.append(
                            (
                                strategy,
                                self.table.bucket_count,
                                self.table.max_load,
                                self.keys,
                            )
                        )

                    def set(self, key, value):
                        self.keys.append(key)
                        self.table.set(key, value)

                    def get(self, key):
                        return self.table.get(key)

                    def __len__(self):
                        return len(self.table)

                    def __getattr__(self, name):
                        return getattr(self.table, name)

                return RecordingTable

            with (
                patch.object(compare_hash_tables, "BUCKET_COUNT", 20),
                patch.object(compare_hash_tables, "RESULTS_DIR", Path(directory)),
                patch.object(
                    compare_hash_tables,
                    "HashTable",
                    recording_factory("chaining", compare_hash_tables.HashTable),
                ),
                patch.object(
                    compare_hash_tables,
                    "LinearProbingHashTable",
                    recording_factory(
                        "linear", compare_hash_tables.LinearProbingHashTable
                    ),
                ),
            ):
                measurements = compare_hash_tables._measurements()
                csv_path = compare_hash_tables._write_csv(measurements)
                svg_path = compare_hash_tables._write_svg(measurements)

            chaining_records = [
                record for record in records if record[0] == "chaining"
            ]
            linear_records = [record for record in records if record[0] == "linear"]
            self.assertEqual(len(chaining_records), 45)
            self.assertEqual(len(linear_records), 45)
            self.assertEqual(
                sorted(len(record[3]) for record in chaining_records),
                sorted(
                    round(step / 10 * 20)
                    for step in range(1, 10)
                    for _ in range(5)
                ),
            )
            for item_count in range(2, 19, 2):
                same_load_chaining = [
                    record
                    for record in chaining_records
                    if len(record[3]) == item_count
                ]
                same_load_linear = [
                    record
                    for record in linear_records
                    if len(record[3]) == item_count
                ]
                self.assertEqual(len(same_load_chaining), 5)
                self.assertEqual(len(same_load_linear), 5)
                for chaining, linear in zip(same_load_chaining, same_load_linear):
                    self.assertEqual(chaining[1:3], (20, None))
                    self.assertEqual(linear[1:3], (20, None))
                    self.assertEqual(chaining[3], linear[3])

            with csv_path.open(newline="", encoding="utf-8") as source:
                reader = csv.DictReader(source)
                rows = list(reader)
                headers = reader.fieldnames or []
            normalized_headers = [header.lower() for header in headers]

            self.assertEqual(len(rows), 9)
            actual_header = next(
                header for header in headers if "actual" in header.lower()
            )
            repeat_header = next(
                header for header in headers if "repeat" in header.lower()
            )
            self.assertTrue(any("item" in header for header in normalized_headers))
            for strategy in ("chain", "linear"):
                for outcome in ("success", "unsuccess"):
                    matching_headers = [
                        header.lower()
                        for header in headers
                        if strategy in header.lower() and outcome in header.lower()
                    ]
                    self.assertTrue(matching_headers)
                    self.assertTrue(
                        any(
                            "theory" in header for header in matching_headers
                        )
                    )
                    self.assertTrue(
                        any(
                            any(
                                marker in header
                                for marker in ("average", "observed", "measured")
                            )
                            for header in matching_headers
                        )
                    )
            self.assertTrue(svg_path.is_file())

            for step, row in enumerate(rows, start=1):
                self.assertAlmostEqual(float(row["target_alpha"]), step / 10)
                self.assertEqual(int(row[repeat_header]), 5)
                self.assertTrue(all(value != "" for value in row.values()))
                alpha = float(row[actual_header])
                expected_theory = (
                    1 + alpha / 2,
                    alpha,
                    0.5 * (1 + 1 / (1 - alpha)),
                    0.5 * (1 + 1 / (1 - alpha) ** 2),
                )
                theory_headers = [
                    header
                    for header in headers
                    if "theory" in header.lower()
                ]
                for strategy, outcome, expected in zip(
                    ("chain", "chain", "linear", "linear"),
                    ("success", "unsuccess", "success", "unsuccess"),
                    expected_theory,
                ):
                    header = next(
                        header
                        for header in theory_headers
                        if strategy in header.lower() and outcome in header.lower()
                    )
                    self.assertAlmostEqual(float(row[header]), expected)
            svg = svg_path.read_text(encoding="utf-8").lower()
            self.assertIn("chain", svg)
            self.assertIn("linear", svg)
            self.assertIn("theor", svg)

    def test_repeated_measurements_are_reproducible(self):
        with patch.object(compare_hash_tables, "BUCKET_COUNT", 20):
            first = compare_hash_tables._measurements()
            second = compare_hash_tables._measurements()

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
