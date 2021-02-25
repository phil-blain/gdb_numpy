import unittest
import subprocess
import os
from pathlib import Path
import numpy as np
import sys
from textwrap import dedent

# Allow running from top of repository or from tests/
path = os.fspath(Path(__file__).resolve().parent)

# Hide base test classes from unittest runner by nesting them
class TestCases:
    class TestCppArray(unittest.TestCase):
        @classmethod
        def setupClass(cls):
            build_folder = "build"
            cls.fixtures_dir = os.path.join(path, "fixtures")
            cls.build_dir = os.path.join(cls.fixtures_dir, build_folder)
            cls.write_makefile()
            # Create build directory
            # Hack: argparse accepts '-vv' for a 'store_const' '-v' argument, so use that to increase verbosity
            cls.capture_make_output = False if ('-vv' in sys.argv) else True
            subprocess.run(["make", build_folder], cwd=cls.fixtures_dir, check=True, capture_output=cls.capture_make_output)
        
        @classmethod
        def write_makefile(cls):
            makefile = dedent('''
                CXX = g++
                CXXFLAGS = -g -O0

                APP=TestCppArray

                .PHONY: clean

                $(APP): ../$(APP).cpp
                	$(CXX) $(CXXFLAGS) $< -o $@

                build:
                	mkdir $@

                clean:
                	rm -rf *.o *.dSYM $(APP)
            ''').strip()

            with open(os.path.join(cls.fixtures_dir, "Makefile"), "w") as f:
                f.writelines(makefile)

class TestCppArray(TestCases.TestCppArray):

    success = 0

    @classmethod
    def setUpClass(cls):
        super().setupClass()
        cls.name = cls.__name__
        # Build test fixture
        subprocess.run(["make", "-f", "../Makefile", cls.name], cwd=cls.build_dir, check=True, capture_output=cls.capture_make_output)

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
