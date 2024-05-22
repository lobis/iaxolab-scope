from iaxolab_scope import Scope
from iaxolab_scope.waveform import read_single_frame
import matplotlib.pyplot as plt

scope = Scope()

scope.acquire_sequence = True
scope.acquire_sequence_count = 100

scope.acquire_memory_depth = "1k"

scope.waveform_source_channel = 3

scope.trigger_edge_source_channel = 3

plt.figure()

for i in range(scope.acquire_sequence_count):
    t, v = read_single_frame(scope, i + 1)
    plt.plot(t, v)

plt.show()
