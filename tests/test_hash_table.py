import unittest

from src.hash_table import HashTable


class HashTableTests(unittest.TestCase):
    table_class = HashTable
    has_fixed_capacity = False

    def make_table(self, *args, **kwargs):
        return self.table_class(*args, **kwargs)

    def test_empty_table_and_empty_string_key(self):
        table = self.make_table()
        self.assertEqual(len(table), 0)
        table.set("", "empty")
        self.assertEqual(table.get(""), "empty")
        self.assertEqual(len(table), 1)

    def test_colliding_keys_are_stored_and_retrieved_independently(self):
        table = self.make_table(bucket_count=8, max_load=None)
        # These single-character keys have the same bucket with the specified
        # Horner hash and an initial bucket count of 8.
        keys = ("a", "i", "q")
        for key in keys:
            table.set(key, key.upper())

        self.assertEqual([table.get(key) for key in keys], ["A", "I", "Q"])
        self.assertEqual(len(table), 3)

    def test_setting_existing_key_replaces_its_value_without_growing(self):
        table = self.make_table()
        table.set("key", "first")
        table.set("key", "second")

        self.assertEqual(table.get("key"), "second")
        self.assertEqual(len(table), 1)

    def test_missing_get_and_delete_raise_key_error(self):
        table = self.make_table()
        with self.assertRaises(KeyError):
            table.get("missing")
        with self.assertRaises(KeyError):
            table.delete("missing")
        self.assertEqual(len(table), 0)

    def test_delete_removes_key_and_decrements_length(self):
        table = self.make_table()
        table.set("key", "value")
        table.delete("key")

        self.assertEqual(len(table), 0)
        with self.assertRaises(KeyError):
            table.get("key")

    def test_resize_happens_only_after_load_factor_exceeds_limit(self):
        table = self.make_table(bucket_count=8, max_load=0.75)
        for number in range(6):
            table.set(f"key-{number}", str(number))
        self.assertEqual(table.bucket_count, 8)

        table.set("key-6", "6")
        self.assertEqual(table.bucket_count, 16)
        self.assertEqual(len(table), 7)
        for number in range(6):
            self.assertEqual(table.get(f"key-{number}"), str(number))
        self.assertEqual(table.get("key-6"), "6")

    def test_delete_does_not_shrink_the_table(self):
        table = self.make_table(bucket_count=8, max_load=0.75)
        for number in range(7):
            table.set(f"key-{number}", str(number))
        self.assertEqual(table.bucket_count, 16)

        table.delete("key-0")
        self.assertEqual(table.bucket_count, 16)
        self.assertEqual(len(table), 6)

    def test_none_max_load_disables_resizing(self):
        table = self.make_table(bucket_count=2, max_load=None)
        item_count = 2 if self.has_fixed_capacity else 20
        for number in range(item_count):
            table.set(f"key-{number}", str(number))

        self.assertEqual(table.bucket_count, 2)
        self.assertEqual(len(table), item_count)
        for number in range(item_count):
            self.assertEqual(table.get(f"key-{number}"), str(number))

    def test_get_records_number_of_compared_nodes(self):
        table = self.make_table(bucket_count=8, max_load=None)
        keys = ("a", "i", "q")
        for key in keys:
            table.set(key, key)

        comparisons = []
        for key in keys:
            self.assertEqual(table.get(key), key)
            comparisons.append(table.last_comparisons)
        self.assertEqual(sorted(comparisons), [1, 2, 3])

    def test_failed_get_in_empty_bucket_records_zero_comparisons(self):
        table = self.make_table()
        with self.assertRaises(KeyError):
            table.get("missing")
        self.assertEqual(table.last_comparisons, 0)

    def test_set_and_delete_do_not_change_last_get_comparison_count(self):
        table = self.make_table()
        table.set("key", "value")
        table.get("key")
        comparisons = table.last_comparisons

        table.set("other", "value")
        self.assertEqual(table.last_comparisons, comparisons)
        table.delete("other")
        self.assertEqual(table.last_comparisons, comparisons)

    def test_failed_get_in_nonempty_bucket_records_comparisons(self):
        table = self.make_table(bucket_count=8, max_load=None)
        for key in ("a", "i", "q"):
            table.set(key, key)

        with self.assertRaises(KeyError):
            table.get("y")
        self.assertEqual(table.last_comparisons, 3)

    def test_delete_from_colliding_chain_keeps_other_keys(self):
        keys = ("a", "i", "q")
        for deleted in keys:
            with self.subTest(deleted=deleted):
                table = self.make_table(bucket_count=8, max_load=None)
                for key in keys:
                    table.set(key, key)

                table.delete(deleted)

                with self.assertRaises(KeyError):
                    table.get(deleted)
                for key in keys:
                    if key != deleted:
                        self.assertEqual(table.get(key), key)
                self.assertEqual(len(table), 2)


if __name__ == "__main__":
    unittest.main()
