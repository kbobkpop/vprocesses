import os
import sys

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

import vprocesses as multiprocessing
from vprocesses import VManager

def producer(conn, iterations):
    for i in range(iterations):
        conn.send(i)
        
def consumer(conn, iterations):
    for i in range(iterations):
        data = conn.recv()
        print(data)

p1, c1 = multiprocessing.Pipe()

processes = [multiprocessing.Process(target=producer, args=(p1, 3)),
             multiprocessing.Process(target=consumer, args=(c1, 3))]

vm = VManager(processes, [p1, c1], outputFormat='png')
vm.start()
vm.runTicksToEnd(processes)