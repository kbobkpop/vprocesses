import time
import multiprocessing
import vprocess

dot = vprocess.VDigraph(format='png')

waittime = 1 

def producer(queue : vprocess.VConn, sending_vp, receiving_vp):
    queue.connect(sending_vp, receiving_vp)
    for i in range(5):
        time.sleep(waittime)
        queue.set_waiting(sending_vp)
        time.sleep(waittime)
        queue.conn.send(i)
        time.sleep(waittime)
        queue.set_ready(sending_vp)

        queue.set_waiting(sending_vp)
        time.sleep(waittime)
        queue.conn.send("hello")
        time.sleep(waittime)
        queue.set_ready(sending_vp)

def consumer(queue1 : vprocess.VConn, queue2 : vprocess.VConn, vp):
    while True:
        queue1.set_waiting(vp)
        data1 = queue1.conn.recv()
        queue1.set_ready(vp)
        queue2.set_waiting(vp)
        data2 = queue2.conn.recv()
        queue2.set_ready(vp)

        print("received")

        queue1.set_waiting(vp)
        data3 = queue1.conn.recv()
        queue1.set_ready(vp)
        queue1.set_waiting(vp)
        data4 = queue2.conn.recv()
        queue2.set_ready(vp)

        if data3 == "hello" and data4 == "hello":
            print(f"{data1}-{data2}")

q11, q12 = multiprocessing.Pipe()
q21, q22 = multiprocessing.Pipe()
vc11 = vprocess.VConn(dot, q11)
vc12 = vprocess.VConn(dot, q12)
vc21 = vprocess.VConn(dot, q21)
vc22 = vprocess.VConn(dot, q22)


processes = [
    vprocess.VProcess(dot, 'A',
        target=producer, 
        args=(vc11, 'A', 'C')
    ),
    vprocess.VProcess(dot, 'B',
        target=producer, 
        args=(vc21, 'B', 'C')
    ),
    vprocess.VProcess(dot, 'C',
        target=consumer, 
        args=(vc12, vc22, 'C')
    )
]

for process in processes:
    process.start()

for process in processes:
    process.join()