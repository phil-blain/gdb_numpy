import unittest
import subprocess
import os
from pathlib import Path
import numpy as np

# Allow running from top of repository or from tests/
path = os.fspath(Path(__file__).resolve().parent)

# Hide base test classes from unittest runner by nesting them
class TestCases:
    class TestCppArray(unittest.TestCase):
        pass

class TestCppArray(TestCases.TestCppArray):

    success = 0

    @classmethod
    def setUpClass(cls):
        build_folder = "build"
        fixtures_dir = os.path.join(path, "fixtures")
        cls.build_dir = os.path.join(fixtures_dir, build_folder)
        # Create build directory
        subprocess.run(["make", build_folder], cwd=fixtures_dir, check=True, capture_output=True)
        cls.name = cls.__name__
        # Build test fixture
        subprocess.run(["make", "-f", "../Makefile", cls.name], cwd=cls.build_dir, check=True, capture_output=True)

    def test_toarray(self):
        gdb = subprocess.run(["gdb", "-batch", "-x", "../setup.gdb", f"./{self.name}"], 
                             cwd=self.build_dir, text=True, capture_output=True)
        self.longMessage = False
        self.assertEqual(gdb.returncode, self.success, msg=f"GDB subprocess failed: {gdb.stderr}")
    def test_dtype(self):
        gdb = subprocess.run(["gdb", "-batch", "-x", "../setup.gdb", "-ex", "python print(array.dtype)", f"./{self.name}"], 
                             cwd=self.build_dir, text=True, capture_output=True)
        # Check last line of GDB output
        self.assertEqual(*gdb.stdout.splitlines()[-1:], 'float64')
    def test_shape(self):
        gdb = subprocess.run(["gdb", "-batch", "-x", "../setup.gdb", "-ex", "python print(array.shape)", f"./{self.name}"], 
                             cwd=self.build_dir, text=True, capture_output=True)
        self.assertEqual(*gdb.stdout.splitlines()[-1:], '(5,)')

if __name__ == '__main__':
    unittest.main()
