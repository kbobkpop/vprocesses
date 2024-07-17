import os
import sys

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

import random
import vprocesses as multiprocessing
from vprocesses import VManager
from vprocesses import VSelect as select

def lockedProducer(conn, lock, iterations):
    for i in range(iterations):
        lock.acquire()
        conn.send(i)
        lock.release()

def consumer(conn, iterations):
    for i in range(iterations):
        data = conn.recv()
        print(f"{data}")

def selectSharedLockTwoLockedProducersTwoConsumers(conn1, conn2, conn3, conn4, lock1, lock2, iterations):
    for i in range(iterations*2):
        data1 = None
        data2 = None
        (inputs, _, _) = select.select([conn1, conn2], [], [])
        if conn1 in inputs and conn2 in inputs:
            num = random.randint(0, 1)
            if num == 0:
                data1 = conn1.recv()
            else:
                data2 = conn2.recv()
        elif conn1 in inputs:
            data1 = conn1.recv()
        elif conn2 in inputs:
            data2 = conn2.recv()
        
        if data1 != None:
            lock1.acquire()
            conn3.send(data1)
            lock1.release()
        elif data2 != None:
            lock2.acquire()
            conn4.send(data2)
            lock2.release()

vlock1 = multiprocessing.Lock()
vlock2 = multiprocessing.Lock()
vlock3 = multiprocessing.Lock()
vlock4 = multiprocessing.Lock()
vlock5 = multiprocessing.Lock()

p1, c1 = multiprocessing.Pipe()
p2, c2 = multiprocessing.Pipe()
p3, c3 = multiprocessing.Pipe()
p4, c4 = multiprocessing.Pipe()
p5, c5 = multiprocessing.Pipe()
p6, c6 = multiprocessing.Pipe()
p7, c7 = multiprocessing.Pipe()
p8, c8 = multiprocessing.Pipe()
p9, c9 = multiprocessing.Pipe()
p10, c10 = multiprocessing.Pipe()

processes = [
        multiprocessing.Process(
            target=lockedProducer, 
            args=(p1,vlock2, 2),
            name="p1"
        ),
        multiprocessing.Process(
            target=lockedProducer, 
            args=(p2,vlock2, 2),
            name="p2"
        ),
        multiprocessing.Process(
            target=lockedProducer, 
            args=(p3,vlock3, 2),
            name="p3"
        ),
        multiprocessing.Process(
            target=lockedProducer, 
            args=(p4,vlock3, 2),
            name="p4"
        ),
        multiprocessing.Process(
            target=selectSharedLockTwoLockedProducersTwoConsumers, 
            args=(c1, c2, p5, p6, vlock1, vlock5, 2),
            name="Slct1"
        ),
        multiprocessing.Process(
            target=selectSharedLockTwoLockedProducersTwoConsumers, 
            args=(c3, c4, p7, p8, vlock4, vlock5, 2),
            name="Slct2"
        ),
        multiprocessing.Process(
            target=selectSharedLockTwoLockedProducersTwoConsumers, 
            args=(c6, c7, p9, p10, vlock1, vlock4, 2),
            name="Slct3"
        ),
        multiprocessing.Process(
            target=consumer, 
            args=(c5, 2),
            name="c1"
        ),
        multiprocessing.Process(
            target=consumer, 
            args=(c9, 2),
            name="c2"
        ),
        multiprocessing.Process(
            target=consumer, 
            args=(c10, 2),
            name="c3"
        ),
        multiprocessing.Process(
            target=consumer, 
            args=(c8, 2),
            name="c4"
        )
        ]

connections = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6, p7, c7, p8, c8, p9, c9, p10, c10]
locks = [vlock1, vlock2, vlock3, vlock4, vlock5]

vm = VManager(processes, connections, locks, outputFormat='png', tickTock=True)
vm.start()
vm.runTicksToEnd(processes)