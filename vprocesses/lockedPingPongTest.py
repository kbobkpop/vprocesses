import vprocesses as multiprocessing
from vprocesses import VManager

def lockedPingPong(lock, out_conn, in_conn, iterations, initial_data=""):
    process = multiprocessing.current_process().name

    if initial_data:
        lock.acquire()
        out_conn.send(initial_data)
        lock.release()
    for i in range(iterations):
        data = in_conn.recv()
        print(f"{process} says {data}")
        lock.acquire()
        out_conn.send(data)
        lock.release()
    if not initial_data:
        data = in_conn.recv()
        print(f"{process} says {data}")


vlock = multiprocessing.Lock()

pipe_1_in, pipe_1_out  = multiprocessing.Pipe()
pipe_2_in, pipe_2_out  = multiprocessing.Pipe()
pipe_3_in, pipe_3_out  = multiprocessing.Pipe()
pipe_4_in, pipe_4_out  = multiprocessing.Pipe()
    
processes = [
    multiprocessing.Process(
        target=lockedPingPong, 
        args=(vlock, pipe_1_in, pipe_2_out, 1, "hello"),
        name="Albert"
    ),
    multiprocessing.Process(
        target=lockedPingPong, 
        args=(vlock, pipe_2_in, pipe_1_out, 1),
        name="Bertha"
    ),
    multiprocessing.Process(
        target=lockedPingPong, 
        args=(vlock, pipe_3_in, pipe_4_out, 1, "hi"),
        name="Cindy"
    ),
    multiprocessing.Process(
        target=lockedPingPong, 
        args=(vlock, pipe_4_in, pipe_3_out, 1),
        name="Dennis"
    )
]

locks = [vlock]

channels = [
    pipe_1_in,
    pipe_1_out,
    pipe_2_in,
    pipe_2_out,
    pipe_3_in,
    pipe_3_out,
    pipe_4_in,
    pipe_4_out
]

vm = VManager(processes, channels, vlock, outputFormat='png')
vm.start()
vm.runTicksToEnd(processes)