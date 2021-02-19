# Break on "here" to have a consistent place to stop in all tests
break here
run
# Go back one frame where the array is defined
up
python
# Add gdb_numpy location (../../../) to sys.path
import sys,os
sys.path.append(os.path.join(*[os.pardir] * 3))
import gdb_numpy
array = gdb_numpy.to_array("array")
end