import unittest
import subprocess
import os
import platform
from pathlib import Path
import numpy as np
import sys
from textwrap import dedent
from typing import Mapping, Tuple
import shlex

# Allow running from top of repository or from tests/
path = os.fspath(Path(__file__).resolve().parent)

cpp_double = {'native': 'double', 'numpy': 'float64'}

# Check if C++ compiler is GCC
CXX = os.getenv('CXX', 'c++')
cxx_vers = subprocess.run([CXX, "--version"], check=True, capture_output=True, text=True)
cxx_is_gxx = True if "Free Software Foundation" in cxx_vers.stdout else False

CXXFLAGS = ["-g", "-O0", "-std=c++11"]
# With GCC, '-g' defaults to '-gdwarf-2 -gstrict-dwarf' on macOS, and with these
# settings 'std::vector' is seen be GDB (and LLDB) as simply 'vector' so the regex to
# detect this type does not work. Manually setting a higher DWARF version
# fixes that.
if platform.system() == "Darwin" and cxx_is_gxx:
    CXXFLAGS.append("-gdwarf-4")

# Hide base test classes from unittest runner by nesting them
class TestCases:
    class TestCppArray(unittest.TestCase):

        success = 0

        @classmethod
        def setupClass(cls, name: str, types: Mapping[str, str], decl: str, shape: Tuple[int, ...], explicit_shape: bool = False, cleanup: str = '', header: str = ''):
            cls.name = name
            cls.types = types
            cls.shape = shape
            cls.explicit_shape = explicit_shape
            to_array_args_implicit = "'array'"
            to_array_args_explicit = f"'array', {shape}"
            gdb_command = ["gdb", "-x", "../setup.gdb", "-se", f"./{cls.name}", "-ex"]
            py_command_no_args = "python array = gdb_numpy.to_array"
            py_command_implicit = f"{py_command_no_args}({to_array_args_implicit})"
            py_command_explicit = f"{py_command_no_args}({to_array_args_explicit})"
            py_command = py_command_explicit if explicit_shape else py_command_implicit
            cls.gdb_command_interactive = gdb_command + [py_command]
            cls.gdb_command = cls.gdb_command_interactive + ["-batch"]
            if explicit_shape:
                cls.gdb_command_throws = gdb_command + [py_command_implicit] + ["-batch"]
            build_folder = "build"
            cls.fixtures_dir = os.path.join(path, "fixtures")
            cls.build_dir = os.path.join(cls.fixtures_dir, build_folder)
            cls.write_makefile()
            cls.ext = ".cpp"
            cls.write_source_code(decl, cleanup, header)
            # Create build directory
            # Hack: argparse accepts '-vv' for a 'store_const' '-v' argument, so use that to increase verbosity
            cls.capture_make_output = False if ('-vv' in sys.argv) else True
            cls.capture_make_stdout = None if ('-vv' in sys.argv) else subprocess.PIPE
            subprocess.run(["make", build_folder], cwd=cls.fixtures_dir, check=True, capture_output=cls.capture_make_output)
            # Build test fixture
            try:
                subprocess.run(["make", "-f", f"../{cls.name}.mk", cls.name], cwd=cls.build_dir, text=True,
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
                CXX = {CXX}
                CXXFLAGS = {" ".join(CXXFLAGS)}

                APP={cls.name}

                .PHONY: clean debug

                $(APP): ../$(APP).cpp
                	$(CXX) $(CXXFLAGS) $< -o $@

                build:
                	mkdir $@

                debug:
                	{' '.join(shlex.quote(arg) for arg in cls.gdb_command_interactive)}

                clean:
                	rm -rf *.o *.dSYM $(APP)
            ''').lstrip()

            with open(os.path.join(cls.fixtures_dir, f"{cls.name}.mk"), "w") as f:
                f.writelines(makefile)

        @classmethod
        def write_source_code(cls, decl: str, cleanup: str, header: str):
            code = dedent(f'''

                {header}

                void here() {{}};

                int main() {{
                    {decl}
                    here();
                    {cleanup}
                    return 0;
                }}
            ''').lstrip()

            with open(os.path.join(cls.fixtures_dir, cls.__name__ + cls.ext), "w") as f:
                f.writelines(code)

        def test_toarray(self):
            gdb = subprocess.run(self.gdb_command, 
                                 cwd=self.build_dir, text=True, capture_output=True)
            self.longMessage = False
            self.assertEqual(gdb.returncode, self.success, msg=f"GDB subprocess failed: {gdb.stderr}")
            if self.explicit_shape:
                gdb = subprocess.run(self.gdb_command_throws,
                                     cwd=self.build_dir, text=True, capture_output=True)
                self.assertNotEqual(gdb.returncode, self.success, msg="GDB subprocess should have failed, but did not!")
                exception = "ValueError"
                self.assertTrue(exception in gdb.stderr, msg=f"Expected {exception} to be raised, but got: {gdb.stderr}")

        def test_dtype(self):
            gdb = subprocess.run(self.gdb_command + ["-ex", "python print(array.dtype)"],
                                 cwd=self.build_dir, text=True, capture_output=True)
            self.assertEqual(get_last_line(gdb.stdout), self.types['numpy'])

        def test_shape(self):
            gdb = subprocess.run(self.gdb_command + ["-ex", "python print(array.shape)"],
                                 cwd=self.build_dir, text=True, capture_output=True)
            self.assertEqual(get_last_line(gdb.stdout), str(self.shape))

    class TestCppArray1D(TestCppArray):
        @classmethod
        def setupClass(cls, name: str, types: Mapping[str, str]):
            shape = (5,)
            decl = f'''
                    const int size = {shape[0]};
                    {types['native']} array[size] = {{1.0, 2.0, 3.0, 4.0, 5.0}};
            '''.strip()
            super().setupClass(name, types, decl, shape)

def get_last_line(lines: str) -> str:
    return lines.splitlines()[-1]

class TestCppArrayDouble(TestCases.TestCppArray1D):

    @classmethod
    def setUpClass(cls):
        types = cpp_double
        super().setupClass(name=cls.__name__, types=types)

class TestCppArrayFloat(TestCases.TestCppArray1D):

    @classmethod
    def setUpClass(cls):
        types = {'native': 'float', 'numpy': 'float32'}
        super().setupClass(name=cls.__name__, types=types)

class TestCppArrayDynamic(TestCases.TestCppArray):

    @classmethod
    def setUpClass(cls):
        types = cpp_double
        shape = (5,)
        decl = f"auto array{{ new {types['native']}[{shape[0]}]{{}} }};"
        cleanup = 'delete[] array;'
        super().setupClass(name=cls.__name__, types=types, decl=decl, shape=shape, explicit_shape=True, cleanup=cleanup)

class TestCppArray2D(TestCases.TestCppArray):

    @classmethod
    def setUpClass(cls):
        types = cpp_double
        shape = (2,3)
        decl = f'''
                    const int rows = {shape[0]};
                    const int cols = {shape[1]};
                    {types['native']} array[rows][cols] = {{}};
        '''.strip()
        super().setupClass(name=cls.__name__, types=types, decl=decl, shape=shape)

class TestCppArrayDynamic2D(TestCases.TestCppArray):

    @classmethod
    def setUpClass(cls):
        types = cpp_double
        shape = (4,3)
        decl = f"auto array{{ new {types['native']}[{shape[0]}][{shape[1]}]{{}} }};"
        cleanup = 'delete[] array;'
        super().setupClass(name=cls.__name__, types=types, decl=decl, shape=shape, explicit_shape=True, cleanup=cleanup)

@unittest.skipUnless(cxx_is_gxx, "Implementation is currently specific to libstdc++")
class TestCppStdVector(TestCases.TestCppArray):

    @classmethod
    def setUpClass(cls):
        types = cpp_double
        header = '#include <vector>'
        shape = (4,)
        decl = f"std::vector<{types['native']}> array({shape[0]});"
        super().setupClass(name=cls.__name__, types=types, decl=decl, shape=shape, header=header)

@unittest.skipUnless(cxx_is_gxx, "Implementation is currently specific to libstdc++")
class TestCppStdVectorStdVector(TestCases.TestCppArray):

    @classmethod
    def setUpClass(cls):
        types = cpp_double
        header = '#include <vector>'
        shape = (6,4)
        decl = f"std::vector<std::vector<{types['native']}>> array({shape[0]}, std::vector<{types['native']}>({shape[1]}));"
        super().setupClass(name=cls.__name__, types=types, decl=decl, shape=shape, header=header)


if __name__ == '__main__':
    unittest.main()
