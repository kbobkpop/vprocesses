import os
import sys
import random
import shutil

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

import vprocesses as multiprocessing
from vprocesses import VManager
from vprocesses import VSelect as select

# target functions for processes:
def pingpong(i, wConn, rConn, iterations, outputdir="vtest/", initial_data=""):
    process = multiprocessing.multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    if initial_data:
        wConn.send(initial_data)
        output.write(str(initial_data))
        output.flush()
    for i in range(iterations):
        data = rConn.recv()
        print(f"{i}: {data}")
        output.write(f"{i}: {data}")
        output.flush()
        wConn.send(data)
        output.write(str(data))
        output.flush()
    if not initial_data:
        data = rConn.recv()
        print(f"{i}: {data}")

def lockedPingPong(i, lock, writeConn, readConn, iterations, outputdir="vtest/", initial_data=""):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    if initial_data:
        lock.acquire()
        writeConn.send(initial_data)
        output.write(str(initial_data))
        output.flush()
        lock.release()
    for i in range(iterations):
        data = readConn.recv()
        print(f"{i}: {data}")
        output.write(f"{i}: {data}")
        output.flush()
        lock.acquire()
        writeConn.send(data)
        output.write(str(data))
        output.flush()
        lock.release()
    if not initial_data:
        data = readConn.recv()
        print(f"{i}: {data}")
        output.write(str(data))
        output.flush()

def producer(conn, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        conn.send(i)
        output.write(str(i))
        output.flush()

def doubleProducer(conn1, conn2, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        conn1.send(i)
        print(f"{process.name} sent {i}")
        output.write(str(i))
        conn2.send(i)
        output.write(str(i))
        output.flush()

def doubleSendProducer(conn, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        conn.send(i)
        output.write(str(i))
        output.flush()
        conn.send("hello")
        output.write("hello")
        output.flush()

def consumer(conn, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, 'w')
    for i in range(iterations):
        data = conn.recv()
        print(f"{data}")
        output.write(str(data))
        output.flush()

def doubleRecvDoubleConsumer(conn1, conn2, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data1 = conn1.recv()
        data2 = conn2.recv()
        data3 = conn1.recv()
        data4 = conn2.recv()

        if data3 == "hello" and data4 == "hello":
            print(f"{data1}-{data2}")
        output.write(f"{data1}-{data2}-{data3}-{data4}")
        output.flush()

def doubleSendDoubleProducer(conn1, conn2, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        conn1.send(i)
        conn2.send("hello")
        conn1.send(i)
        conn2.send("hello")

        output.write(f"{i}-hello-{i}-hello")
        output.flush()

def doubleConsumer(conn1, conn2, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data1 = conn1.recv()
        data2 = conn2.recv()
        print(f"{data1}-{data2}")
        output.write(f"{data1}-{data2}")
        output.flush()

def trippleConsumer(conn1, conn2, conn3, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations * 3):
        print(f"trippleConsumer: {i} of {iterations * 3}")
        inputs, _ , _  = select.select([conn1, conn2, conn3], [], [])
        if conn1 in inputs:
            data = conn1.recv()
        elif conn2 in inputs:
            data = conn2.recv()
        elif conn3 in inputs:
            data = conn3.recv()
        output.write(f"{data}")
        output.flush()

def transmitter(conn1, conn2, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data = conn1.recv()
        conn2.send(data)
        output.write(f"{data}")
        output.flush()

def lockedTransmitter(conn1, conn2, lock, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data = conn1.recv()
        lock.acquire()
        conn2.send(data)
        output.write(f"{data}")
        output.flush()
        lock.release()

def doubleInTransmitter2(conn1, conn2, conn3, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        inputs, _ , _  = select.select([conn1, conn2], [], [])
        if conn1 in inputs:
            data = conn1.recv()
        elif conn2 in inputs:
            data = conn2.recv()
        conn3.send(data)
        output.write(str(data))
        output.flush()

def doubleInTransmitter(conn1, conn2, conn3, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data1 = conn1.recv()
        data2 = conn2.recv()

        send_data = str(data1) + "+" + str(data2)

        conn3.send(send_data)
        output.write(send_data)
        output.flush()

def doubleOutTransmitter(conn1, conn2, conn3, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data = conn1.recv()
        conn2.send(data)
        conn3.send(data)
        output.write(str(data))
        output.flush()

def lockedProducer(conn, lock, iterations, outputdir="vtest/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        lock.acquire()
        conn.send(i)
        output.write(str(i))
        output.flush()
        lock.release()

def selectSharedLockTwoLockedProducersTwoConsumers(conn1, conn2, conn3, conn4, lock1, lock2, iterations, outputdir="vtest/"):
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

def veryLockedProducer(locks, conn, iterations):
    for i in range(iterations):
        for lock in locks:
            lock.acquire()
        conn.send(i)
        for lock in locks:
             lock.release()

def veryLockedProducer2(lock1, lock2, lock3, conn, iterations):
    for i in range(iterations):
        lock1.acquire()
        lock2.acquire()
        lock1.release()
        lock3.acquire()
        conn.send(i)
        lock2.release()
        lock3.release()

def veryLockedProducer3(lock1, lock2, lock3, conn, iterations):
    for i in range(iterations):
        lock1.acquire()
        lock2.acquire()
        lock3.acquire()
        conn.send(i)
        lock1.release()
        lock2.release()
        lock3.release()

def veryLockedProducer4(lock1, lock2, lock3, conn, iterations):
    for i in range(iterations):
        lock1.acquire()
        lock2.acquire()
        lock1.release()
        lock3.acquire()
        conn.send(i)
        lock2.release()
        lock3.release()

def nestedLockedSelect(lock1, lock2, lock3, conn1, conn2, conn3, iterations):
    for i in range(iterations):
        lock1.acquire()
        lock2.acquire()
        inputs,_,_ = select.select([conn1, conn2, conn3], [], [])
        lock3.acquire()
        lock1.release()
        lock2.release()
        for input in inputs:
            input.recv()
        lock3.release()

def selectVariableProducersConsumers1(in_connections, out_connections, num, iterations):
    for i in range(num * iterations):
        (inputs, _, _) = select.select(in_connections, [], [])
        for i, connection in enumerate(in_connections):
          if connection in inputs:
              data = connection.recv()
              out_connections[i].send(data)

def selectVariableProducersConsumers2(in_connections, out_connections):
    sendIndex = 0
    maxIndex = len(out_connections)
    for i in range(30):
        (inputs, _, _) = select.select(in_connections, [], [])
        index = random.randint(0, len(inputs) - 1)
        data = inputs[index].recv()
        out_connections[sendIndex].send(data)
        sendIndex = (sendIndex + 1) % maxIndex
        print(f"Sending to: {sendIndex}")

# Tests

def transmitterTest(iterations, outputdir="vtest/"):
    pipe_1_in, pipe_1_out  = multiprocessing.Pipe()
    pipe_2_in, pipe_2_out  = multiprocessing.Pipe()

    processes = [
        multiprocessing.Process(
            target=producer,
            args=(pipe_1_in, iterations, outputdir),
            name="p1"
        ),
        multiprocessing.Process(
            target=transmitter,
            args=(pipe_1_out, pipe_2_in, iterations, outputdir),
            name="t1"
        ),
        multiprocessing.Process(
            target=consumer,
            args=(pipe_2_out, iterations, outputdir),
            name="c1"
        )
    ]

    channels = [
        pipe_1_in,
        pipe_1_out,
        pipe_2_in,
        pipe_2_out,
    ]
    return processes, channels

def doubleInTransmitterTest(iterations, outputdir="vtest/"):
    pipe_1_in, pipe_1_out  = multiprocessing.Pipe()
    pipe_2_in, pipe_2_out  = multiprocessing.Pipe()
    pipe_3_in, pipe_3_out  = multiprocessing.Pipe()

    processes = [
        multiprocessing.Process(
            target=producer,
            args=(pipe_1_in, iterations, outputdir),
            name="p2"
        ),
        multiprocessing.Process(
            target=producer,
            args=(pipe_2_in, iterations, outputdir),
            name="p3"
        ),
        multiprocessing.Process(
            target=doubleInTransmitter,
            args=(pipe_1_out, pipe_2_out, pipe_3_in, iterations, outputdir),
            name="t2"
        ),
        multiprocessing.Process(
            target=consumer,
            args=(pipe_3_out, iterations, outputdir),
            name="c2"
        )
    ]

    channels = [
        pipe_1_in,
        pipe_1_out,
        pipe_2_in,
        pipe_2_out,
        pipe_3_in,
        pipe_3_out
    ]
    return processes, channels

def doubleOutTransmitterTest(iterations, outputdir="vtest/"):
    pipe_1_in, pipe_1_out  = multiprocessing.Pipe()
    pipe_2_in, pipe_2_out  = multiprocessing.Pipe()
    pipe_3_in, pipe_3_out  = multiprocessing.Pipe()

    processes = [
        multiprocessing.Process(
            target=producer,
            args=(pipe_1_in, iterations, outputdir),
            name="p4"
        ),
        multiprocessing.Process(
            target=doubleOutTransmitter,
            args=(pipe_1_out, pipe_2_in, pipe_3_in, iterations, outputdir),
            name="t3"
        ),
        multiprocessing.Process(
            target=consumer,
            args=(pipe_2_out, iterations, outputdir),
            name="c3"
        ),
        multiprocessing.Process(
            target=consumer,
            args=(pipe_3_out, iterations, outputdir),
            name="c4"
        )
    ]

    channels = [
        pipe_1_in,
        pipe_1_out,
        pipe_2_in,
        pipe_2_out,
        pipe_3_in,
        pipe_3_out
    ]
    return processes, channels

def doubleOutTransmitterTransmitterTest(iterations, outputdir="vtest/"):
    pipe_1_in, pipe_1_out  = multiprocessing.Pipe()
    pipe_2_in, pipe_2_out  = multiprocessing.Pipe()
    pipe_3_in, pipe_3_out  = multiprocessing.Pipe()
    pipe_4_in, pipe_4_out  = multiprocessing.Pipe()

    processes = [
        multiprocessing.Process(
            target=producer,
            args=(pipe_1_in, iterations, outputdir),
            name="p4"
        ),
        multiprocessing.Process(
            target=doubleOutTransmitter,
            args=(pipe_1_out, pipe_2_in, pipe_3_in, iterations, outputdir),
            name="t3"
        ),
        multiprocessing.Process(
            target=transmitter,
            args=(pipe_2_out, pipe_4_in, iterations, outputdir),
            name="t4"
        ),
        multiprocessing.Process(
            target=consumer,
            args=(pipe_4_out, iterations, outputdir),
            name="c3"
        ),
        multiprocessing.Process(
            target=consumer,
            args=(pipe_3_out, iterations, outputdir),
            name="c4"
        )
    ]

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

    return processes, channels

def pingPongTest(iterations, outputdir="vtest/"):
    pipe_1_w, pipe_1_r  = multiprocessing.Pipe()
    pipe_2_w, pipe_2_r  = multiprocessing.Pipe()
    processes = [
        multiprocessing.Process(
            target=pingpong,
            args=(0, pipe_1_w, pipe_2_r, iterations, outputdir, "hello"),
            name="Albert"
        ),
        multiprocessing.Process(
            target=pingpong,
            args=(1, pipe_2_w, pipe_1_r, iterations, outputdir),
            name="Bertha"
        )
    ]
    channels = [
        pipe_1_w,
        pipe_1_r,
        pipe_2_w,
        pipe_2_r
    ]
    return processes, channels

def twoDoubleProducerDoubleSendDoubleConsumerDoubleRecvTest(iterations, outputdir="vtest/"):

    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()
    p3, c3 = multiprocessing.Pipe()
    p4, c4 = multiprocessing.Pipe()

    processes = [
        multiprocessing.Process(
            target=doubleSendDoubleProducer,
            args=(p1, p2, iterations, outputdir),
            name="p1"
        ),
        multiprocessing.Process(
            target=doubleSendDoubleProducer,
            args=(p3, p4, iterations, outputdir),
            name="p2"
        ),
        multiprocessing.Process(
            target=doubleRecvDoubleConsumer,
            args=(c1, c4, iterations, outputdir),
            name="c1"
        ),
        multiprocessing.Process(
            target=doubleRecvDoubleConsumer,
            args=(c3, c2, iterations, outputdir),
            name="c2"
        )
    ]

    channels = [c1, p1, c2, p2, c3, p3, c4, p4]
    return processes, channels



def producerDoubleConsumerTest(iterations, outputdir="vtest/"):
    q11, q12 = multiprocessing.Pipe()
    q21, q22 = multiprocessing.Pipe()

    processes = [
        multiprocessing.Process(
            target=producer,
            args=(q11, iterations, outputdir),
            name="p5"
        ),
        multiprocessing.Process(
            target=producer,
            args=(q21, iterations, outputdir),
            name="p6"
        ),
        multiprocessing.Process(
            target=doubleConsumer,
            args=(q12, q22, iterations, outputdir),
            name="c5"
        )
    ]
    channels = [q11, q12, q21, q22]
    return processes, channels

def producerConsumerTest(iterations, outputdir="vtest/"):
    q11, q12 = multiprocessing.Pipe()

    processes = [
        multiprocessing.Process(
            target=producer,
            args=(q11, iterations, outputdir),
            name="p1"
        ),
        multiprocessing.Process(
            target=consumer,
            args=(q12, iterations, outputdir),
            name="c1"
        )
    ]
    channels = [q11, q12]
    return processes, channels

def twoXProducerConsumerTest(iterations, outputdir="vtest/"):
    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()

    processes = [
        multiprocessing.Process(
            target=doubleProducer,
            args=(p1, p2, iterations, outputdir),
            name="p1"
        ),
        multiprocessing.Process(
            target=doubleConsumer,
            args=(c1, c2, iterations, outputdir),
            name="c1"
        )
    ]
    channels = [p1, p2, c1, c2]
    return processes, channels

def doubleProducerConsumerTest(iterations, outputdir="vtest/"):
    q11, q12 = multiprocessing.Pipe()
    q21, q22 = multiprocessing.Pipe()

    processes = [
        multiprocessing.Process(
            target=producer,
            args=(q11, iterations, outputdir),
            name="p7"
        ),
        multiprocessing.Process(
            target=producer,
            args=(q21, iterations, outputdir),
            name="p8"
        ),
        multiprocessing.Process(
            target=consumer,
            args=(q12, iterations, outputdir),
            name="c7"
        ),
        multiprocessing.Process(
            target=consumer,
            args=(q22, iterations, outputdir),
            name="c8"
        )
    ]
    channels = [q11, q12, q21, q22]
    return processes, channels


def oneLockLockedProducerConsumerTest(iterations, outputdir="vtest/"):

    vlock = multiprocessing.Lock()

    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()
    p3, c3 = multiprocessing.Pipe()
    p4, c4 = multiprocessing.Pipe()

    processes = [
            multiprocessing.Process(
                target=lockedProducer,
                args=(p1, vlock, iterations, outputdir),
                name="p1"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p2, vlock, iterations, outputdir),
                name="p2"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p3, vlock, iterations, outputdir),
                name="p3"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p4, vlock, iterations, outputdir),
                name="p4"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c1, iterations, outputdir),
                name="c1"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c2, iterations, outputdir),
                name="c2"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c3, iterations, outputdir),
                name="c3"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c4, iterations, outputdir),
                name="c4"
            )
    ]

    channels = [p1, c1, p2, c2, p3, c3, p4, c4]
    locks = [vlock]

    return processes, channels, locks

def twoLockLockedProducerConsumerTest(iterations, outputdir="vtest/"):

    vlock1 = multiprocessing.Lock()
    vlock2 = multiprocessing.Lock()

    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()
    p3, c3 = multiprocessing.Pipe()
    p4, c4 = multiprocessing.Pipe()
    p5, c5 = multiprocessing.Pipe()
    p6, c6 = multiprocessing.Pipe()

    processes = [
            multiprocessing.Process(
                target=lockedProducer,
                args=(p1, vlock1, iterations, outputdir),
                name="p1"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p2, vlock1, iterations, outputdir),
                name="p2"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p3, vlock1, iterations, outputdir),
                name="p3"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p4, vlock2, iterations, outputdir),
                name="p4"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p5, vlock2, iterations, outputdir),
                name="p5"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p6, vlock2, iterations, outputdir),
                name="p6"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c1, iterations, outputdir),
                name="c1"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c2, iterations, outputdir),
                name="c2"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c3, iterations, outputdir),
                name="c3"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c4, iterations, outputdir),
                name="c4"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c5, iterations, outputdir),
                name="c5"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c6, iterations, outputdir),
                name="c6"
            )
    ]

    channels = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6]
    locks = [vlock1, vlock2]

    return processes, channels, locks

def lockedPingPongTest(iterations, outputdir="vtest/"):

    vlock1 = multiprocessing.Lock()

    pipe_1_in, pipe_1_out  = multiprocessing.Pipe()
    pipe_2_in, pipe_2_out  = multiprocessing.Pipe()


    processes = [
        multiprocessing.Process(
            target=lockedPingPong,
            args=(0, vlock1, pipe_1_in, pipe_2_out, iterations, outputdir, "hello"),
            name="Albert"
        ),
        multiprocessing.Process(
            target=lockedPingPong,
            args=(1, vlock1, pipe_2_in, pipe_1_out, iterations, outputdir),
            name="Bertha"
        )
    ]

    locks = [vlock1]

    channels = [
        pipe_1_in,
        pipe_1_out,
        pipe_2_in,
        pipe_2_out
    ]
    return processes, channels, locks

def lockedMultiplePingPongTest(iterations, outputdir="vtest/"):

    vlock = multiprocessing.Lock()

    pipe_1_in, pipe_1_out  = multiprocessing.Pipe()
    pipe_2_in, pipe_2_out  = multiprocessing.Pipe()
    pipe_3_in, pipe_3_out  = multiprocessing.Pipe()
    pipe_4_in, pipe_4_out  = multiprocessing.Pipe()

    processes = [
        multiprocessing.Process(
            target=lockedPingPong,
            args=(0, vlock, pipe_1_in, pipe_2_out, iterations, outputdir,"hello"),
            name="Albert"
        ),
        multiprocessing.Process(
            target=lockedPingPong,
            args=(1, vlock, pipe_2_in, pipe_1_out, iterations, outputdir),
            name="Bertha"
        ),
        multiprocessing.Process(
            target=lockedPingPong,
            args=(0, vlock, pipe_3_in, pipe_4_out, iterations, outputdir,"hello"),
            name="Cindy"
        ),
        multiprocessing.Process(
            target=lockedPingPong,
            args=(1, vlock, pipe_4_in, pipe_3_out, iterations, outputdir),
            name="Dennis"
        ),
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
    return processes, channels, locks

def selectSharedLockTwoLockedProducersTwoConsumersTest(iterations, outputdir="vtest/"):

    vlock1 = multiprocessing.Lock()
    vlock2 = multiprocessing.Lock()

    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()
    p3, c3 = multiprocessing.Pipe()
    p4, c4 = multiprocessing.Pipe()

    processes = [
            multiprocessing.Process(
                target=lockedProducer,
                args=(p1,vlock1, iterations, outputdir),
                name="p1"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p2,vlock2, iterations, outputdir),
                name="p2"
            ),
            multiprocessing.Process(
                target=selectSharedLockTwoLockedProducersTwoConsumers,
                args=(c1, c2, p3, p4, vlock1, vlock2, iterations, outputdir),
                name="DS"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c3, iterations, outputdir),
                name="c1"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c4, iterations, outputdir),
                name="c2"
            )]

    locks = [vlock1, vlock2]
    connections = [p1, c1, p2, c2, p3, c3, p4, c4]

    return processes, connections, locks

def complexTest(iterations, outputdir="vtest/"):

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
                args=(p1,vlock2, iterations, outputdir),
                name="p1"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p2,vlock2, iterations, outputdir),
                name="p2"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p3,vlock3, iterations, outputdir),
                name="p3"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p4,vlock3, iterations, outputdir),
                name="p4"
            ),
            multiprocessing.Process(
                target=selectSharedLockTwoLockedProducersTwoConsumers,
                args=(c1, c2, p5, p6, vlock1, vlock5, iterations),
                name="DS1"
            ),
            multiprocessing.Process(
                target=selectSharedLockTwoLockedProducersTwoConsumers,
                args=(c3, c4, p7, p8, vlock4, vlock5, iterations),
                name="DS2"
            ),
            multiprocessing.Process(
                target=selectSharedLockTwoLockedProducersTwoConsumers,
                args=(c6, c7, p9, p10, vlock1, vlock4, iterations),
                name="DS3"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c5, iterations, outputdir),
                name="c1"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c9, iterations, outputdir),
                name="c2"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c10, iterations, outputdir),
                name="c3"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c8, iterations, outputdir),
                name="c4"
            )
            ]

    locks = [vlock1, vlock2, vlock3, vlock4, vlock5]

    connections = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6, p7, c7, p8, c8, p9, c9, p10, c10]

    return processes, connections, locks

def selectMultipleLockedProducersConsumersTest(iterations, outputdir="vtest/"):

    vlock = multiprocessing.Lock()

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
    p11, c11 = multiprocessing.Pipe()
    p12, c12 = multiprocessing.Pipe()

    in_connections = [c1, c2, c3, c4, c5, c6]
    out_connections = [p7, p8, p9, p10, p11, p12]

    processes = [
            multiprocessing.Process(
                target=lockedProducer,
                args=(p1, vlock, iterations, outputdir),
                name="p1"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p2, vlock, iterations, outputdir),
                name="p2"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p3, vlock, iterations, outputdir),
                name="p3"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p4, vlock, iterations, outputdir),
                name="p4"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p5, vlock, iterations, outputdir),
                name="p5"
            ),
            multiprocessing.Process(
                target=lockedProducer,
                args=(p6, vlock, iterations, outputdir),
                name="p6"
            ),
            multiprocessing.Process(
                target=selectVariableProducersConsumers1,
                args=(in_connections, out_connections, 6, iterations),
                name="DS"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c7, iterations, outputdir),
                name="c7"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c8, iterations, outputdir),
                name="c8"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c9, iterations, outputdir),
                name="c9"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c10, iterations, outputdir),
                name="c10"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c11, iterations, outputdir),
                name="c11"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c12, iterations, outputdir),
                name="c12"
            )]

    locks = [vlock]
    connections = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6, p7, c7, p8, c8, p9, c9, p10, c10, p11, c11, p12, c12]

    return processes, connections, locks, selects

def selectMultipleProducersConsumersTest(iterations, outputdir="vtest/"):

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
    p11, c11 = multiprocessing.Pipe()
    p12, c12 = multiprocessing.Pipe()

    in_connections = [c1, c2, c3, c4, c5, c6]
    out_connections = [p7, p8, p9, p10, p11, p12]

    processes = [
            multiprocessing.Process(
                target=producer,
                args=(p1, iterations, outputdir),
                name="p1"
            ),
            multiprocessing.Process(
                target=producer,
                args=(p2, iterations, outputdir),
                name="p2"
            ),
            multiprocessing.Process(
                target=producer,
                args=(p3, iterations, outputdir),
                name="p3"
            ),
            multiprocessing.Process(
                target=producer,
                args=(p4, iterations, outputdir),
                name="p4"
            ),
            multiprocessing.Process(
                target=producer,
                args=(p5, iterations, outputdir),
                name="p5"
            ),
            multiprocessing.Process(
                target=producer,
                args=(p6, iterations, outputdir),
                name="p6"
            ),
            multiprocessing.Process(
                target=selectVariableProducersConsumers1,
                args=(in_connections, out_connections, 6, iterations),
                name="DS"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c7, iterations, outputdir),
                name="c7"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c8, iterations, outputdir),
                name="c8"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c9, iterations, outputdir),
                name="c9"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c10, iterations, outputdir),
                name="c10"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c11, iterations, outputdir),
                name="c11"
            ),
            multiprocessing.Process(
                target=consumer,
                args=(c12, iterations, outputdir),
                name="c12"
            )]

    connections = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6, p7, c7, p8, c8, p9, c9, p10, c10, p11, c11, p12, c12]

    return processes, connections, selects

def nestedLocksSelectTest(iterations):

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()
    lock3 = multiprocessing.Lock()

    locks = [lock1, lock2, lock3]

    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()
    p3, c3 = multiprocessing.Pipe()

    channels = [p1, c1, p2, c2, p3, c3]

    processes = [
            multiprocessing.Process(
                    target=nestedLockedSelect,
                    args=(lock1, lock2, lock3, c1, c2, c3, iterations),
                    ),
            multiprocessing.Process(
                    target=producer,
                    args=(p1, iterations),
                    ),
            multiprocessing.Process(
                    target=producer,
                    args=(p2, iterations),
                    ),
            multiprocessing.Process(
                    target=producer,
                    args=(p3, iterations),
                    )
                 ]

    return processes, channels, locks

def nestedLocksTest1(iterations):
    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()
    lock3 = multiprocessing.Lock()
    lock4 = multiprocessing.Lock()

    locks = [lock1, lock2, lock3, lock4]

    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()
    p3, c3 = multiprocessing.Pipe()
    p4, c4 = multiprocessing.Pipe()

    channels = [p1, c1, p2, c2, p3, c3, p4, c4]

    processes = [
            multiprocessing.Process(
                    target=veryLockedProducer,
                    args=(locks, p1, iterations),
                    ),
            multiprocessing.Process(
                    target=veryLockedProducer,
                    args=(locks, p2, iterations),
                    ),
            multiprocessing.Process(
                    target=veryLockedProducer,
                    args=(locks, p3, iterations),
                    ),
            multiprocessing.Process(
                    target=veryLockedProducer,
                    args=(locks, p4, iterations),
                    ),
            multiprocessing.Process(
                    target=consumer,
                    args=(c1, iterations),
                    ),
            multiprocessing.Process(
                    target=consumer,
                    args=(c2, iterations),
                    ),
            multiprocessing.Process(
                    target=consumer,
                    args=(c3, iterations),
                    ),
            multiprocessing.Process(
                    target=consumer,
                    args=(c4, iterations),
                    )
                 ]

    return processes, channels, locks

def nestedLocksTest2(iterations):

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()
    lock3 = multiprocessing.Lock()

    locks = [lock1, lock2, lock3]

    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()
    p3, c3 = multiprocessing.Pipe()
    p4, c4 = multiprocessing.Pipe()

    channels = [p1, c1, p2, c2, p3, c3, p4, c4]

    processes = [
            multiprocessing.Process(
                    target=veryLockedProducer2,
                    args=(lock1, lock2, lock3, p1, iterations),
                    ),
            multiprocessing.Process(
                    target=veryLockedProducer2,
                    args=(lock1, lock2, lock3, p2, iterations),
                    ),
            multiprocessing.Process(
                    target=veryLockedProducer2,
                    args=(lock1, lock2, lock3, p3, iterations),
                    ),
            multiprocessing.Process(
                    target=veryLockedProducer2,
                    args=(lock1, lock2, lock3, p4, iterations),
                    ),
            multiprocessing.Process(
                    target=consumer,
                    args=(c1, iterations),
                    ),
            multiprocessing.Process(
                    target=consumer,
                    args=(c2, iterations),
                    ),
            multiprocessing.Process(
                    target=consumer,
                    args=(c3, iterations),
                    ),
            multiprocessing.Process(
                    target=consumer,
                    args=(c4, iterations),
                    )
                 ]

    return processes, channels, locks

def nestedLocksTest3(iterations):

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()
    lock3 = multiprocessing.Lock()
    lock4 = multiprocessing.Lock()
    lock5 = multiprocessing.Lock()

    locks = [lock1, lock2, lock3, lock4, lock5]

    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()

    channels = [p1, c1, p2, c2]

    processes = [
            multiprocessing.Process(
                    target=veryLockedProducer3,
                    args=(lock1, lock2, lock3, p1, iterations),
                    ),
            multiprocessing.Process(
                    target=veryLockedProducer4,
                    args=(lock4, lock5, lock3, p2, iterations),
                    ),
            multiprocessing.Process(
                    target=consumer,
                    args=(c1, iterations),
                    ),
            multiprocessing.Process(
                    target=consumer,
                    args=(c2, iterations),
                    )
                 ]

    return processes, channels, locks

def multipleSimpleConnectionsTest(iterations, outputdir="vtest/"):
    p = []
    c = []

    processes, channels = pingPongTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = producerDoubleConsumerTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = doubleProducerConsumerTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = transmitterTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = doubleInTransmitterTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = doubleOutTransmitterTest(iterations, outputdir)
    p.extend(processes)
    c.extend(channels)
    processes, channels = p, c

    return processes, channels

def multipleNestedLocksTest(iterations, outputdir="vtest/"):
    p = []
    c = []
    l = []

    processes, channels, locks = nestedLocksTest1(iterations)
    p.extend(processes)
    c.extend(channels)
    l.extend(locks)
    processes, channels, locks = nestedLocksTest2(iterations)
    p.extend(processes)
    c.extend(channels)
    l.extend(locks)
    processes, channels, locks = nestedLocksTest3(iterations)
    p.extend(processes)
    c.extend(channels)
    l.extend(locks)

    processes, channels, locks = p, c, l

    return processes, channels, locks


outputdir = "vtest/"
if os.path.exists(outputdir):
    shutil.rmtree(outputdir)
os.mkdir(outputdir)

locks = []
selects = []

# Test 1
#processes, channels = multipleSimpleConnectionsTest(5, outputdir)
processes, channels = doubleOutTransmitterTransmitterTest(1, outputdir)

# Test 2
#processes, channels, locks = lockedPingPongTest(2, outputdir) #terminates

# Test 3
#processes, channels = twoDoubleProducerDoubleSendDoubleConsumerDoubleRecvTest(5, outputdir) # terminates

# Test 4
#processes, channels, locks = twoLockLockedProducerConsumerTest(10, outputdir) # terminates

# Test 5
#processes, channels, locks = lockedMultiplePingPongTest(2, outputdir) #terminates

# Test 6
#processes, channels, locks, selects = selectMultipleLockedProducersConsumersTest(5, outputdir) # terminates

# Test 7
#processes, channels, locks = complexTest(5, outputdir) # terminates

# Test 8
#processes, channels, locks = nestedLocksTest1(4) # terminates

# Test 9
#processes, channels, locks = nestedLocksTest2(4) # terminates

# Test 10
#processes, channels, locks = nestedLocksTest3(4) # terminates

# Test 11
#processes, channels, locks = nestedLocksSelectTest(2) # terminates

# Test 12
#processes, channels, locks = multipleNestedLocksTest(4) # terminates

vmanager = VManager(processes, channels, locks, output_format="png", logging=False, interactive_locks=False, draw=True, tick_tock=True)

#vmanager.init_graph()
vmanager.start()

#vmanager.stepwise_ticks(processes) # uncomment this line and comment the one below for stepwise execution, if draw is disabled, you can choose when to draw the graph by typing in 'd'
vmanager.run_ticks_to_end(processes)