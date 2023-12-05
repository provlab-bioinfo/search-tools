"""
Unit tests for functions from searchTools.

To run, use: python -m unittest tests.test_searchTools
"""
import unittest, os, shutil, tempfile, pathlib

from searchTools import findNestedDirs, flattenDirectory


class TestNestedFolderUtils(unittest.TestCase):
    """
    Unit tests for functions pertaining to finding/removing nested folders.
    """
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_findNestedDirs(self):
        os.makedirs(os.path.join(self.test_dir, "dir1", "dir2", "dir3"))
        nested_dirs = findNestedDirs(self.test_dir)
        expected_dirs = [
            os.path.join(self.test_dir, "dir1"),
            os.path.join(self.test_dir, "dir1", "dir2"),
            os.path.join(self.test_dir, "dir1", "dir2", "dir3")
        ]
        self.assertEqual(set(nested_dirs), set(expected_dirs))
        
    def test_flattenDirectory(self):
        nested_path = os.path.join(self.test_dir, "dir1", "dir2", "dir3")
        os.makedirs(nested_path)

        with open(os.path.join(nested_path, "test.txt"), "w") as f:
            f.write("test content")

        # flattenDirectory(os.path.join(self.test_dir, "dir1", "dir2", "dir3"))
        # flattenDirectory(os.path.join(self.test_dir, "dir1", "dir2"))
        # flattenDirectory(os.path.join(self.test_dir, "dir1"))
        nested_dirs = findNestedDirs(self.test_dir)[::-1]
        for dir in nested_dirs: flattenDirectory(dir)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "test.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "dir1", "dir2")))


if __name__ == "__main__":
    unittest.main()


