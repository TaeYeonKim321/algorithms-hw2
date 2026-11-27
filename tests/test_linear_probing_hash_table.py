import unittest

from src.linear_probing_hash_table import LinearProbingHashTable
from test_hash_table import HashTableTests


class LinearProbingHashTableTests(HashTableTests):
    table_class = LinearProbingHashTable
    has_fixed_capacity = True

    def test_collisions_wrap_from_last_slot_to_first_slot(self):
        table = self.make_table(bucket_count=4, max_load=None)
        keys = ("c", "g", "k")
        for key in keys:
            table.set(key, key.upper())

        values = []
        probes = []
        for key in keys:
            values.append(table.get(key))
            probes.append(table.last_probes)

        self.assertEqual(values, ["C", "G", "K"])
        self.assertEqual(probes, [1, 2, 3])

    def test_deleted_slot_does_not_break_lookup_and_is_reused_without_duplicates(self):
        table = self.make_table(bucket_count=4, max_load=None)
        for key in ("c", "g", "k"):
            table.set(key, key)

        table.delete("g")
        self.assertEqual(table.get("k"), "k")
        self.assertEqual(table.last_comparisons, 2)
        self.assertEqual(table.last_probes, 3)

        table.set("k", "updated")
        self.assertEqual(len(table), 2)
        table.set("o", "new")
        self.assertEqual(len(table), 3)
        self.assertEqual(table.get("k"), "updated")
        self.assertEqual(table.get("o"), "new")
        self.assertEqual(table.last_probes, 2)

    def test_full_table_supports_lookup_and_rejects_an_extra_key(self):
        table = self.make_table(bucket_count=3, max_load=None)
        for key in ("c", "g", "k"):
            table.set(key, key)

        for key in ("c", "g", "k"):
            self.assertEqual(table.get(key), key)
        with self.assertRaises(KeyError):
            table.get("s")
        self.assertEqual(table.last_comparisons, 3)
        self.assertEqual(table.last_probes, 3)

        with self.assertRaises(OverflowError):
            table.set("w", "extra")
        self.assertEqual(len(table), 3)

    def test_resize_rehashes_keys_and_lookup_records_probes(self):
        table = self.make_table(bucket_count=4, max_load=0.75)
        for key in ("c", "g", "k"):
            table.set(key, key)
        self.assertEqual(table.bucket_count, 4)

        table.set("a", "a")

        self.assertEqual(table.bucket_count, 8)
        for key in ("c", "g", "k", "a"):
            self.assertEqual(table.get(key), key)

    def test_get_records_comparisons_and_all_probes(self):
        table = self.make_table(bucket_count=8, max_load=None)
        for key in ("a", "i", "q"):
            table.set(key, key)

        self.assertEqual(table.get("q"), "q")
        self.assertEqual(table.last_comparisons, 3)
        self.assertEqual(table.last_probes, 3)

        with self.assertRaises(KeyError):
            table.get("y")
        self.assertEqual(table.last_comparisons, 3)
        self.assertEqual(table.last_probes, 4)

    def test_failed_get_in_empty_table_records_one_probe_and_no_comparisons(self):
        table = self.make_table(bucket_count=8, max_load=None)

        with self.assertRaises(KeyError):
            table.get("missing")

        self.assertEqual(table.last_comparisons, 0)
        self.assertEqual(table.last_probes, 1)

    def test_max_load_at_least_one_is_rejected(self):
        for max_load in (1, 1.0, 1.5):
            with self.subTest(max_load=max_load):
                with self.assertRaises(ValueError):
                    self.make_table(max_load=max_load)


if __name__ == "__main__":
    unittest.main()
