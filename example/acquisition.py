from iaxolab_scope import Scope

scope = Scope()

scope.write("CH1:SCALE 1.0")
scope.write("TIMEBASE:SCALE 0.0002")

scope.write("TRIG:A:TYPE EDGE")
scope.write("TRIG:A:MODE NORMAL")
scope.write("TRIG:A:EDGE:SLOPE RISE")
scope.write("TRIG:A:LEVEL 2.5")
scope.write("TRIG:A:EDGE:SOURCE CH1")
scope.write("TRIG:A:EDGE:COUPLING DC")

scope.write("ACQ:SEQ ON")
scope.write("ACQ:SEQ:COUNT 5")

# toggle run/stop
scope.write(":RUN")  # haven't found the run command
scope.write(":STOP")
