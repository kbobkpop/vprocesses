import multiprocessing
import select
import random
import os
import shutil
import time

def pingpong(i, inConn, outConn, iterations, outputdir="test/", initial_data=""):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    if initial_data:
        outConn.send(initial_data)
        output.write(str(initial_data))
        output.flush()
    for i in range(iterations):
        data = inConn.recv()
        print(f"{i}: {data}")
        output.write(f"{i}: {data}")
        output.flush()
        outConn.send(data)
        output.write(str(data))
        output.flush()
    if not initial_data:
        data = inConn.recv()
        print(f"{i}: {data}")

def lockedPingPong(i, lock, inConn, outConn, iterations, outputdir="test/", initial_data=""):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    if initial_data:
        lock.acquire()
        outConn.send(initial_data)
        output.write(str(initial_data))
        output.flush()
        lock.release()
    for i in range(iterations):
        data = inConn.recv()
        print(f"{i}: {data}")
        output.write(f"{i}: {data}")
        output.flush()
        lock.acquire()
        outConn.send(data)
        output.write(str(data))
        output.flush()
        lock.release()
    if not initial_data:
        data = inConn.recv()
        print(f"{i}: {data}")
        output.write(str(data))
        output.flush()

def producer(conn, iterations, outputdir="test/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        conn.send(i)
        output.write(str(i))
        output.flush()
    time.sleep(0.2)

def doubleSendProducer(conn, iterations, outputdir="test/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        conn.send(i)
        output.write(str(i))
        output.flush()
        conn.send("hello")
        output.write("hello")
        output.flush()

def consumer(conn, iterations, outputdir="test/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, 'w')
    for i in range(iterations):
        data = conn.recv()
        print(f"{data}")
        output.write(str(data))
        output.flush()

def doubleRecvDoubleConsumer(conn1, conn2, iterations, outputdir="test/"):
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


def doubleSendDoubleProducer(conn1, conn2, iterations, outputdir="test/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        conn1.send(i)
        conn2.send("hello")
        conn1.send(i)
        conn2.send("hello")

        output.write(f"{i}-hello-{i}-hello")
        output.flush()

def doubleConsumer(conn1, conn2, iterations, outputdir="test/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data1 = conn1.recv()
        data2 = conn2.recv()
        print(f"{data1}-{data2}")
        output.write(f"{data1}-{data2}")
        output.flush()

def transmitter(conn1, conn2, iterations, outputdir="test/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data = conn1.recv()
        conn2.send(data)
        output.write(f"{data}")
        output.flush()

def doubleInTransmitter(conn1, conn2, conn3, iterations, outputdir="test/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data1 = conn1.recv()
        data2 = conn2.recv()
        dataout = str(data1) + " + " + str(data2) 
        conn3.send(dataout)
        output.write(str(dataout))
        output.flush()

def doubleOutTransmitter(conn1, conn2, conn3, iterations, outputdir="test/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        data = conn1.recv()
        conn2.send(data)
        conn3.send(data)
        output.write(str(data))
        output.flush()

def lockedProducer(conn, lock, iterations, outputdir="test/"):
    process = multiprocessing.current_process()
    output = open(outputdir + process.name, "w")
    for i in range(iterations):
        lock.acquire()
        conn.send(i)
        output.write(str(i))
        output.flush()
        lock.release()
    time.sleep(0.1)

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
    time.sleep(0.2)

def selectVariableProducersConsumers1(in_connections, out_connections, num, iterations):
    for i in range(num*iterations):
        (inputs, _, _) = select.select(in_connections, [], [])
        for i, connection in enumerate(in_connections):
          if connection in inputs:
              data = connection.recv()
              out_connections[i].send(data)
    time.sleep(0.2)

def selectVariableProducersConsumers2(in_connections, out_connections, vselect):
    sendIndex = 0
    maxIndex = len(out_connections)
    for i in range(30):
        (inputs, _, _) = vselect.select(in_connections, [], [])
        index = random.randint(0, len(inputs) - 1)
        data = inputs[index].recv()
        out_connections[sendIndex].send(data)
        sendIndex = (sendIndex + 1) % maxIndex
        print(f"Sending to: {sendIndex}")

# Tests

def transmitterTest(iterations, outputdir="test/"):
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

    #channels = [
    #    pipe_1_in,
    #    pipe_1_out,
    #    pipe_2_in,
    #    pipe_2_out,
    #]

    return processes

def doubleInTransmitterTest(iterations, outputdir="test/"):
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

    #channels = [
    #    pipe_1_in,
    #    pipe_1_out,
    #    pipe_2_in,
    #    pipe_2_out,
    #    pipe_3_in, 
    #    pipe_3_out
    #]

    return processes

def doubleOutTransmitterTest(iterations, outputdir="test/"):
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

    #channels = [
    #    pipe_1_in,
    #    pipe_1_out,
    #    pipe_2_in,
    #    pipe_2_out,
    #    pipe_3_in, 
    #    pipe_3_out
    #]

    return processes

def pingPongTest(iterations, outputdir="test/"):
    pipe_1_in, pipe_1_out  = multiprocessing.Pipe()
    pipe_2_in, pipe_2_out  = multiprocessing.Pipe()
    processes = [
        multiprocessing.Process(
            target=pingpong, 
            args=(0, pipe_1_in, pipe_2_out, iterations, outputdir, "hello"),
            name="Albert"
        ),
        multiprocessing.Process(
            target=pingpong, 
            args=(1, pipe_2_in, pipe_1_out, iterations, outputdir),
            name="Bertha"
        )
    ]
    #channels = [
    #    pipe_1_in,
    #    pipe_1_out,
    #    pipe_2_in,
    #    pipe_2_out
    #]

    return processes

def twoDoubleProducerDoubleSendDoubleConsumerDoubleRecvTest(iterations, outputdir="test/"):

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

    #channels = [c1, p1, c2, p2, c3, p3, c4, p4]
    
    return processes



def producerDoubleConsumerTest(iterations, outputdir="test/"):
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
    #channels = [q11, q12, q21, q22]
    
    return processes

def producerConsumerTest(iterations, outputdir="test/"):
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
    #channels = [q11, q12, q21, q22]
    
    return processes

def oneLockLockedProducerConsumerTest(iterations, outputdir="test/"):

    lock = multiprocessing.Lock()

    #vlock1 = VLock(lock)
    #vlock2 = VLock(lock)
    #vlock3 = VLock(lock)
    #vlock4 = VLock(lock)

    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()
    p3, c3 = multiprocessing.Pipe()
    p4, c4 = multiprocessing.Pipe()

    processes = [
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p1, lock, iterations, outputdir),
                name="p1"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p2, lock, iterations, outputdir),
                name="p2"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p3, lock, iterations, outputdir),
                name="p3"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p4, lock, iterations, outputdir),
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

    #channels = [p1, c1, p2, c2, p3, c3, p4, c4]
    #locks = [vlock1, vlock2, vlock3, vlock4]

    return processes

def twoLockLockedProducerConsumerTest(iterations, outputdir="test/"):

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()

    #vlock1 = VLock(lock1)
    #vlock2 = VLock(lock1)
    #vlock3 = VLock(lock1)
    #vlock4 = VLock(lock2)
    #vlock5 = VLock(lock2)
    #vlock6 = VLock(lock2)

    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()
    p3, c3 = multiprocessing.Pipe()
    p4, c4 = multiprocessing.Pipe()
    p5, c5 = multiprocessing.Pipe()
    p6, c6 = multiprocessing.Pipe()

    processes = [
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p1, lock1, iterations, outputdir),
                name="p1"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p2, lock1, iterations, outputdir),
                name="p2"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p3, lock1, iterations, outputdir),
                name="p3"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p4, lock2, iterations, outputdir),
                name="p4"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p5, lock2, iterations, outputdir),
                name="p5"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p6, lock2, iterations, outputdir),
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

    #channels = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6]
    #locks = [vlock1, vlock2, vlock3, vlock4, vlock5, vlock6]

    return processes

def lockedPingPongTest(iterations, outputdir="test/"):
    lock = multiprocessing.Lock()
    
    #vlock1 = VLock(lock)
    #vlock2 = VLock(lock)
    
    pipe_1_in, pipe_1_out  = multiprocessing.Pipe()
    pipe_2_in, pipe_2_out  = multiprocessing.Pipe()
    
    
    processes = [
        multiprocessing.Process(
            target=lockedPingPong, 
            args=(0, lock, pipe_1_in, pipe_2_out, iterations, outputdir, "hello",),
            name="Albert"
        ),
        multiprocessing.Process(
            target=lockedPingPong, 
            args=(1, lock, pipe_2_in, pipe_1_out, iterations, outputdir),
            name="Bertha"
        )
    ]

    #locks = [vlock1, vlock2]

    #channels = [
    #    pipe_1_in,
    #    pipe_1_out,
    #    pipe_2_in,
    #    pipe_2_out
    #]

    return processes

def lockedMultiplePingPongTest(iterations, outputdir="test/"):
    lock = multiprocessing.Lock()
    
    #vlock1 = VLock(lock)
    #vlock2 = VLock(lock)
    #vlock3 = VLock(lock)
    #vlock4 = VLock(lock)
    

    pipe_1_in, pipe_1_out  = multiprocessing.Pipe()
    pipe_2_in, pipe_2_out  = multiprocessing.Pipe()
    pipe_3_in, pipe_3_out  = multiprocessing.Pipe()
    pipe_4_in, pipe_4_out  = multiprocessing.Pipe()
    
    processes = [
        multiprocessing.Process(
            target=lockedPingPong, 
            args=(0, lock, pipe_1_in, pipe_2_out, iterations, outputdir, "hello"),
            name="Albert"
        ),
        multiprocessing.Process(
            target=lockedPingPong, 
            args=(1, lock, pipe_2_in, pipe_1_out, iterations, outputdir),
            name="Bertha"
        ),
        multiprocessing.Process(
            target=lockedPingPong, 
            args=(0, lock, pipe_3_in, pipe_4_out, iterations, outputdir, "hello"),
            name="Cindy"
        ),
        multiprocessing.Process(
            target=lockedPingPong, 
            args=(1, lock, pipe_4_in, pipe_3_out, iterations, outputdir),
            name="Dennis"
        ),
    ]

    #locks = [vlock1, vlock2, vlock3, vlock4]

    #channels = [
    #    pipe_1_in,
    #    pipe_1_out,
    #    pipe_2_in,
    #    pipe_2_out,
    #    pipe_3_in,
    #    pipe_3_out,
    #    pipe_4_in,
    #    pipe_4_out
    #]

    return processes

def selectSharedLockTwoLockedProducersTwoConsumersTest(iterations, outputdir="test/"):
    
    #vs = VSelect(name="vselector")

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()

    #vlock1 = VLock(lock1)
    #vlock2 = VLock(lock2)
    #vlock3 = VLock(lock1)
    #vlock4 = VLock(lock2)


    p1, c1 = multiprocessing.Pipe()
    p2, c2 = multiprocessing.Pipe()
    p3, c3 = multiprocessing.Pipe()
    p4, c4 = multiprocessing.Pipe()

    processes = [
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p1,lock1, iterations, outputdir),
                name="p1"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p2,lock2, iterations, outputdir),
                name="p2"
            ),
            multiprocessing.Process(
                target=selectSharedLockTwoLockedProducersTwoConsumers, 
                args=(c1, c2, p3, p4, lock1, lock2, iterations),
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

    #locks = [vlock1, vlock2, vlock3, vlock4]
    #connections = [p1, c1, p2, c2, p3, c3, p4, c4]
    #selects = [vs]

    return processes

def complexTest(iterations, outputdir="test/"):
    
    #vs1 = VSelect(name="s1")
    #vs2 = VSelect(name="s2")
    #vs3 = VSelect(name="s3")

    lock1 = multiprocessing.Lock()
    lock2 = multiprocessing.Lock()
    lock3 = multiprocessing.Lock()
    lock4 = multiprocessing.Lock()
    lock5 = multiprocessing.Lock()

    #vlock11 = VLock(lock1)
    #vlock12 = VLock(lock1)
    #vlock21 = VLock(lock2)
    #vlock22 = VLock(lock2)
    #vlock31 = VLock(lock3)
    #vlock32 = VLock(lock3)
    #vlock41 = VLock(lock4)
    #vlock42 = VLock(lock4)
    #vlock51 = VLock(lock5)
    #vlock52 = VLock(lock5)

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
                args=(p1,lock2, iterations, outputdir),
                name="p1"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p2,lock2, iterations, outputdir),
                name="p2"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p3,lock3, iterations, outputdir),
                name="p3"
            ),
            multiprocessing.Process(
                target=lockedProducer, 
                args=(p4,lock3, iterations, outputdir),
                name="p4"
            ),
            multiprocessing.Process(
                target=selectSharedLockTwoLockedProducersTwoConsumers, 
                args=(c1, c2, p5, p6, lock1, lock5, iterations),
                name="DS1"
            ),
            multiprocessing.Process(
                target=selectSharedLockTwoLockedProducersTwoConsumers, 
                args=(c3, c4, p7, p8, lock4, lock5, iterations),
                name="DS2"
            ),
            multiprocessing.Process(
                target=selectSharedLockTwoLockedProducersTwoConsumers, 
                args=(c6, c7, p9, p10, lock1, lock4, iterations),
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

    #locks = [vlock11, vlock12, vlock21, vlock22, vlock31, vlock32, vlock41, vlock42, vlock51, vlock52]
    #connections = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6, p7, c7, p8, c8, p9, c9, p10, c10]
    #selects = [vs1, vs2, vs3]

    return processes

def selectMultipleLockedProducersConsumersTest(iterations, outputdir="test/"):
    
    #vs = VSelect(name="vselector")

    lock1 = multiprocessing.Lock()

    #vlock1 = VLock(lock1)
    #vlock2 = VLock(lock1)
    #vlock3 = VLock(lock1)
    #vlock4 = VLock(lock1)
    #vlock5 = VLock(lock1)
    #vlock6 = VLock(lock1)

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
                args=(p1, lock1, iterations, outputdir),
                name="p1"
            ),
            multiprocessing.Process(
                target=producer, 
                args=(p2, lock1, iterations, outputdir),
                name="p2"
            ),
            multiprocessing.Process(
                target=producer, 
                args=(p3, lock1, iterations, outputdir),
                name="p3"
            ),
            multiprocessing.Process(
                target=producer, 
                args=(p4, lock1, iterations, outputdir),
                name="p4"
            ),
            multiprocessing.Process(
                target=producer, 
                args=(p5, lock1, iterations, outputdir),
                name="p5"
            ),
            multiprocessing.Process(
                target=producer, 
                args=(p6, lock1, iterations, outputdir),
                name="p6"
            ),
            multiprocessing.Process(
                target=selectVariableProducersConsumers1, 
                args=(in_connections, out_connections, 6 , iterations),
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

    #locks = [vlock1, vlock2, vlock3, vlock4, vlock5, vlock6]
    #connections = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6, p7, c7, p8, c8, p9, c9, p10, c10, p11, c11, p12, c12]
    #selects = [vs]

    return processes

def selectMultipleProducersConsumersTest(iterations, outputdir="test/"):
    
    #vs = VSelect(name="vselector")

    lock1 = multiprocessing.Lock()

    #vlock1 = VLock(lock1)
    #vlock2 = VLock(lock1)
    #vlock3 = VLock(lock1)
    #vlock4 = VLock(lock1)
    #vlock5 = VLock(lock1)
    #vlock6 = VLock(lock1)

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
                args=(in_connections, out_connections, 6 , iterations),
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

    #locks = [vlock1, vlock2, vlock3, vlock4, vlock5, vlock6]
    #connections = [p1, c1, p2, c2, p3, c3, p4, c4, p5, c5, p6, c6, p7, c7, p8, c8, p9, c9, p10, c10, p11, c11, p12, c12]
    #selects = [vs]

    return processes

def multipleSimpleConnectionsTest(iterations, outputdir="test/"):
    p = []
    #c = []

    processes = pingPongTest(iterations, outputdir)
    p.extend(processes)
    #c.extend(channels)
    processes = producerDoubleConsumerTest(iterations, outputdir)
    p.extend(processes)
    #c.extend(channels)
    processes = producerConsumerTest(iterations, outputdir)
    p.extend(processes)
    #c.extend(channels)
    processes = transmitterTest(iterations, outputdir)
    p.extend(processes)
    #c.extend(channels)
    processes = doubleInTransmitterTest(iterations, outputdir)
    p.extend(processes)
    #c.extend(channels)
    processes = doubleOutTransmitterTest(iterations, outputdir)
    p.extend(processes)
    #c.extend(channels)
    processes = p
    
    return processes

outputdir = "selectMultipleProducersConsumersTest/"
if os.path.exists(outputdir):
    shutil.rmtree(outputdir)    
os.mkdir(outputdir)


locks = []
selects = []


# Test 1
#processes = multipleSimpleConnectionsTest(100, outputdir)

# Test 2
#processes = lockedMultiplePingPongTest(100, outputdir)

# Test 3
#processes = twoDoubleProducerDoubleSendDoubleConsumerDoubleRecvTest(100, outputdir)

# Test 4
#processes = twoLockLockedProducerConsumerTest(100, outputdir)

# Test 5
#processes = selectSharedLockTwoLockedProducersTwoConsumersTest(100, outputdir)

# Test 6
#processes = selectMultipleLockedProducersConsumersTest(50, outputdir)

# Test 7
processes = complexTest(100, outputdir)

for process in processes:
    process.start()

for process in processes:
    process.join()