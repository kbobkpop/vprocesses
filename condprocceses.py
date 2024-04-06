import time
import multiprocessing
import graphviz


#condition variables are initialized with Re-entrant locks by default.
workercond = multiprocessing.Condition()
managercond = multiprocessing.Condition()

def initProcesses(numberOfPairs, wbool, mbool):
    consumerbools = [multiprocessing.Value(c_bool, False) for i in range(numberOfPairs)] 
    pipes = [multiprocessing.Pipe() for i in range(numberOfPairs)]
    processPairs = [(multiprocessing.Process(target=producer, args=(pipes[i][0], workercond, managercond, wbool, mbool, consumerbools[i])),
                multiprocessing.Process(target=consumer, args=(pipes[i][1], workercond, managercond, wbool, mbool, consumerbools[i])))
                for i in range(numberOfPairs)]
    return processPairs
    
def startProcesses(processPairs):
    for p in processPairs:
        p[0].start()
        p[1].start()
    
def joinProcesses(processPairs):
    for p in processPairs:
        p[0].join()
        p[1].join()

def producer(consumer_producer_connection, wcond, mcond, wgo, mgo, cgo):
    #time.sleep(1) #This can force producer to sleep first, to check that it doesn't block even if the consumer(s) acquires the locks first
    print(f"producer: {multiprocessing.process.current_process()} start: mgo: {id(mgo)}, wgo: {id(wgo)}")
    for i in range(5):
        with wcond:
            while not wgo.value or cgo.value: 
                print(f"producer: {multiprocessing.process.current_process()} is waiting: mgo: {mgo}, wgo: {wgo}")
                wcond.wait()
                print(f"producer: {multiprocessing.process.current_process()} just awoke, mgo.go: {mgo.value}, wgo.go: {wgo.value}, cgo.go: {cgo.value}")
            mcond.acquire()
            consumer_producer_connection.send(f"hello {i}")
            print(f"{i}. iteration of producer: {multiprocessing.process.current_process()}")
            cgo.value = True
            mgo.value = True
            wgo.value = False
            print(f"producer: {multiprocessing.process.current_process()} notifies manager: mgo: {mgo.value}, wgo: {wgo.value}")
            mcond.notify()
            mcond.release()

def consumer(consumer_producer_connection, wcond, mcond, wgo, mgo, cgo):
    print(f"consumer: {multiprocessing.process.current_process()} start: mgo: {id(mgo)}, wgo: {id(wgo)}")
    for i in range(5):
        with wcond:
            while not wgo.value or not cgo.value:
                print(f"consumer: {multiprocessing.process.current_process()} is waiting: mgo.go: {mgo.value}, wgo.go: {wgo.value}")
                wcond.wait()
                print(f"consumer: {multiprocessing.process.current_process()} just awoke, mgo.go: {mgo.value}, wgo.go: {wgo.value}, cgo.go: {cgo.value}")
            mcond.acquire()
            data = consumer_producer_connection.recv()
            print(f"{i}. iteration of consumer: {multiprocessing.process.current_process()} - {data} received")
            cgo.value = False
            mgo.value = True
            wgo.value = False
            print(f"consumer: {multiprocessing.process.current_process()} notifies manager: mgo.go: {mgo.value}, wgo.go: {wgo.value}")
            mcond.notify()
            mcond.release()

def manage(wcond, mcond, wgo, mgo):
    print(f"mgo: {id(mgo)}, wgo: {id(wgo)}")
    while True:
        with mcond:
            #print(f"manager (with wcond): mgo: {id(mgo)}, wgo: {id(wgo)}")
            while not mgo.value:
                print(f"manager is waiting: mgo: {mgo.value}, wgo: {wgo.value}")
                mcond.wait()
                print(f"manager just awoke mgo.go: {mgo.value}, wgo.go: {wgo.value}")
            wcond.acquire()
            mgo.value = False
            wgo.value = True
            print(f"manager notifies all: mgo: {mgo.value}, wgo: {wgo.value}")
            wcond.notify_all()
            wcond.release()

from ctypes import c_bool

if __name__ == '__main__':
    workerbool = multiprocessing.Value(c_bool, True)
    managerbool = multiprocessing.Value(c_bool, False)
    ps = initProcesses(8, workerbool, managerbool)
    startProcesses(ps)
    manage(workercond, managercond, workerbool, managerbool)
   