import os
import sys

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

import vprocesses.vpprocesses as multiprocessing
from vprocesses.vpprocesses import VManager
from vprocesses.vpprocesses import VSelect as select

def producer(conn, iterations):
    for i in range(iterations):
        conn.send(i)
        
def consumer(conn, iterations):
    for i in range(iterations):
        data = conn.recv()
        print(data)

def selector(in_connections, out_connections, iterations):
    for i in range(iterations):
        (inputs, _, _) = select.select(in_connections, [], [])
        for i, connection in enumerate(in_connections):
          if connection in inputs:
              data = connection.recv()
              out_connections[i].send(data)

p1, c1 = multiprocessing.Pipe()
p2, c2 = multiprocessing.Pipe()
p3, c3 = multiprocessing.Pipe()
p4, c4 = multiprocessing.Pipe()
p5, c5 = multiprocessing.Pipe()
p6, c6 = multiprocessing.Pipe()

processes = [multiprocessing.Process(target=producer, args=(p1, 2), name="p1"),
            multiprocessing.Process(target=producer, args=(p2, 2), name="p2"),
            multiprocessing.Process(target=producer, args=(p3, 2), name="p3"),
            multiprocessing.Process(target=selector, args=([c1, c2, c3], [p4, p5, p6], 2), name="s1"),
            multiprocessing.Process(target=consumer, args=(c4, 2), name="c1"),
            multiprocessing.Process(target=consumer, args=(c5, 2), name="c2"),
            multiprocessing.Process(target=consumer, args=(c6, 2), name="c3")
            ]

channels = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6]

vm = VManager(processes, channels, outputFormat='png')
vm.start()
vm.runTicksToEnd(processes)