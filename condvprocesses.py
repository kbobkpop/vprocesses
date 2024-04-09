import time
import multiprocessing
import graphviz

#condition variables are initialized with Re-entrant locks by default.
workercond = multiprocessing.Condition()
managercond = multiprocessing.Condition()

def initProcesses(dot, numberOfPairs, wbool, mbool, list):
    for i in range(numberOfPairs):
        prod = 'p' + str(i)
        cons = 'c' + str(i)
        dot.node(prod, color='black')
        dot.node(cons, color='black')
    #consumerbools are bools for pairwise synchronization between each producer/consumer
    for i in range(numberOfPairs):
        prod = 'p' + str(i)
        cons = 'c' + str(i)
        dot.edge(prod, cons)
    consumerbools = [multiprocessing.Value(c_bool, False) for i in range(numberOfPairs)] 
    pipes = [multiprocessing.Pipe() for i in range(numberOfPairs)]
    processPairs = [(multiprocessing.Process(target=producer, args=(list, i, pipes[i][0], workercond, managercond, wbool, mbool, consumerbools[i])),
                multiprocessing.Process(target=consumer, args=(list, i, pipes[i][1], workercond, managercond, wbool, mbool, consumerbools[i])))
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

def producer(list, index, consumer_producer_connection, wcond, mcond, wgo, mgo, cgo):
    for i in range(5):
        with wcond:
            while not wgo.value or cgo.value: 
                wcond.wait()

            mcond.acquire()
            list[index][0] = 'r'
            list[index][1] = 'b'
            consumer_producer_connection.send(f"hello {i}")
            print(f"{i}. iteration of producer: {multiprocessing.process.current_process()}")
            cgo.value = True
            mgo.value = True
            wgo.value = False
            mcond.notify()
            mcond.release()

def consumer(list, index, consumer_producer_connection, wcond, mcond, wgo, mgo, cgo):
    for i in range(5):
        with wcond:
            while not wgo.value or not cgo.value:
                wcond.wait()
            mcond.acquire()
            list[index][0] = 'b'
            list[index][1] = 'r'
            data = consumer_producer_connection.recv()
            print(f"{i}. iteration of consumer: {multiprocessing.process.current_process()} - {data} received")
            cgo.value = False
            mgo.value = True
            wgo.value = False
            mcond.notify()
            mcond.release()

def updateDigraph(dot, currentGraph, oldGraph, numberOfPairs, iter):
    print(f'updateDigraph, iter: {iter}')
    print(currentGraph[0], currentGraph[1])
    print(oldGraph[0], oldGraph[1])

    for i in range(numberOfPairs):
        
        if currentGraph[i][0] != oldGraph[i][0]:
            
            if currentGraph[i][0] == 'r':
                dot.body[i * 2] = f'\tp{str(i)} [color=red]\n'
            
            if currentGraph[i][0] == 'b':
                dot.body[i * 2] = f'\tp{str(i)} [color=black]\n'
        
        if currentGraph[i][1] != oldGraph[i][1]:
            
            if currentGraph[i][1] == 'r':
                dot.body[i * 2 + 1] = f'\tc{str(i)} [color=red]\n'
            
            if currentGraph[i][1] == 'b':
                dot.body[i * 2 + 1] = f'\tc{str(i)} [color=black]\n'
    
    dot.render('output/test_' + str(iter))



def manage(dot, wcond, mcond, wgo, mgo, graphList, numberOfPairs):
    oldGraphList = [graphList[i]._getvalue() for i in range(numberOfPairs)]
    #print(f"initial state of oldGraphList: {oldGraphList}")
    i = 0
    while True:
        with mcond:
            while not mgo.value:
                mcond.wait()
            wcond.acquire()
            updateDigraph(dot, graphList, oldGraphList, numberOfPairs, i)
            i += 1
            oldGraphList = [graphList[i]._getvalue() for i in range(numberOfPairs)]
            mgo.value = False
            wgo.value = True
            wcond.notify_all()
            wcond.release()

from ctypes import c_bool
from ctypes import c_int     

from multiprocessing.managers import SyncManager

if __name__ == '__main__':
    managertest = SyncManager(ctx=multiprocessing.get_context())
    managertest.start()
    numPairs = 4
    
    #outer_list is a proxy object used to maintain the state of the nodes
    outer_list = [managertest.list(['b', 'b']) for i in range(numPairs)]
    dot = graphviz.Digraph()

    #the bools are ctypes
    workerbool = multiprocessing.Value(c_bool, False)
    managerbool = multiprocessing.Value(c_bool, True)

    ps = initProcesses(dot, numPairs, workerbool, managerbool, outer_list)
    startProcesses(ps)
    manage(dot, workercond, managercond, workerbool, managerbool, outer_list, numPairs)
   