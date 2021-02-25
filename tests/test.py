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

        success = 0

        @classmethod
        def setupClass(cls, name: str):
            cls.name = name
            build_folder = "build"
            cls.fixtures_dir = os.path.join(path, "fixtures")
            cls.build_dir = os.path.join(cls.fixtures_dir, build_folder)
            cls.write_makefile()
            cls.ext = ".cpp"
            cls.write_source_code()
            # Create build directory
            # Hack: argparse accepts '-vv' for a 'store_const' '-v' argument, so use that to increase verbosity
            cls.capture_make_output = False if ('-vv' in sys.argv) else True
            cls.capture_make_stdout = None if ('-vv' in sys.argv) else subprocess.PIPE
            subprocess.run(["make", build_folder], cwd=cls.fixtures_dir, check=True, capture_output=cls.capture_make_output)
            # Build test fixture
            try:
                subprocess.run(["make", "-f", "../Makefile", cls.name], cwd=cls.build_dir, text=True,
                               check=True, stdout=cls.capture_make_stdout, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                # Monkey-patch CalledProcessError.__str__ to also show stderr
                orig_str = subprocess.CalledProcessError.__str__
                def verbose_str(self: subprocess.CalledProcessError):
                    return orig_str(self) + f"\nstderr was: {self.stderr}"
                subprocess.CalledProcessError.__str__  = verbose_str
                raise
        
        @classmethod
        def write_makefile(cls):
            makefile = dedent(f'''
                CXX = {os.getenv('CXX', 'g++')}
                CXXFLAGS = -g -O0

                APP={cls.name}

                .PHONY: clean

                $(APP): ../$(APP).cpp
                	$(CXX) $(CXXFLAGS) $< -o $@

                build:
                	mkdir $@

                clean:
                	rm -rf *.o *.dSYM $(APP)
            ''').lstrip()

            with open(os.path.join(cls.fixtures_dir, "Makefile"), "w") as f:
                f.writelines(makefile)

        @classmethod
        def write_source_code(cls):
            code = dedent('''
            void here() {};

            int main() {
                const int size = 5;
                double array[size] = {1.0, 2.0, 3.0, 4.0, 5.0};
                here();
                return 0;
            }
            ''').lstrip()

            with open(os.path.join(cls.fixtures_dir, cls.__name__ + cls.ext), "w") as f:
                f.writelines(code)

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

class TestCppArray(TestCases.TestCppArray):

    @classmethod
    def setUpClass(cls):
        super().setupClass(name=cls.__name__)

if __name__ == '__main__':
    unittest.main()
