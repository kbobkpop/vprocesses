import multiprocessing.connection
import time
import multiprocessing
import graphviz

from multiprocessing.managers import SyncManager

from ctypes import c_bool
from ctypes import c_int     


manager = SyncManager(ctx=multiprocessing.get_context())
manager.start()

lock = multiprocessing.RLock()

workercond = multiprocessing.Condition(lock)

# printCounter controls the suffix of the drawn image file
printCounter = multiprocessing.Value(c_int, 0)
tmpCounter = multiprocessing.Value(c_int, 0)
edgesInitialized = multiprocessing.Value(c_bool, False)

# Shared state representing the graph for all processes
# nodes = pairs of names and colors of nodes
nodes = manager.list()
# edges = triple of two process names, connected by a channel, and a label describing what is being sent
edges = manager.list()


#maybe just representing graph entirely as a list of edges is sufficient.   

def drawGraph(nodes, edges, iter):
    dgraph = graphviz.Digraph()
    for i in range(len(nodes._getvalue())):
        dgraph.node(nodes[i][0], color=nodes[i][1])
    for i in range(len(edges._getvalue())):
        dgraph.edge(edges[i][0], edges[i][1], edges[i][2])
    dgraph.render('output/test_' + str(iter.value))


#updating and rendering the graph has to be atomic because:
# 1. One process could be updating the graph, then because of context switching another process could be updating/drawing the graph
# 2. One process could be about to draw the graph, but then another process updates the graph, thereby drawing the wrong state as a graph.

#Is it alright to call methods defined outside a class?
def getReceiver(thisProcess, edges):
    for i in range(len(edges._getvalue())):
        if thisProcess == edges[i][0]:
            print("found: ", edges[i][1])
            return edges[i][1]

def checkInitialized():
    print("checking initialized for the following states:")
    printEdges(edges)
    for i in range(len(edges._getvalue())):
        if edges[i][0] == None or edges[i][1] == None:
            return False
    return True

# Connection holds the receiving process, name, like a mailbox.
class VConnection():
    def __init__(self, conn, cbool, thisedge, receiverName=None):
        self.conn = conn
        self.cond = workercond
        self.cbool = cbool
        self.thisedge = thisedge
        self.edges = edges
        self.nodes = nodes
        self.printIteration = printCounter
        #self.receiverName = receiverName

        """ if not self.receiverName:
            receiver = getReceiver(multiprocessing.current_process().name, edges)
            self.receiverName = receiver """

    #requires temporary name to update edge. - Use shared state 'self.edge' between sender and receiver.

    def initRecv(self):
        lock.acquire()
        p = multiprocessing.current_process()
        self.thisedge[1] = p.name
        done = checkInitialized()
        if done and not edgesInitialized.value:
            print("edges are initialized, and this is their current state:")
            printEdges(edges)
            drawGraph(nodes, edges, printCounter)
            self.printIteration.value += 1
            edgesInitialized.value = True
            self.cond.notify_all()
            lock.release()
        else:
            self.cond.notify_all() 
            lock.release()
    
    def initSend(self):
        lock.acquire()
        p = multiprocessing.current_process()
        self.thisedge[0] = p.name
        done = checkInitialized()
        if done and not edgesInitialized.value:
            print("edges are initialized and this is their current state:")
            printEdges(edges)
            drawGraph(nodes, edges, printCounter)
            self.printIteration.value += 1
            edgesInitialized.value = True
            self.cond.notify_all()
            lock.release()
        else:
            self.cond.notify_all()
            lock.release()

    def send(self, to_send):
        if not edgesInitialized.value:
            self.initSend()
        with self.cond:
            while self.cbool.value or not edgesInitialized.value:
                print(multiprocessing.current_process(), "waiting .send")
                self.cond.wait()
            self.conn.send(to_send)
            updateEdges(self.edges, self.thisedge[0], self.thisedge[1], to_send)
            drawGraph(self.nodes, self.edges, self.printIteration)
            self.printIteration.value += 1
            self.cbool.value = True
            self.cond.notify_all()

    def recv(self):
        if not edgesInitialized.value:
            self.initRecv()
        with self.cond:
            while not self.cbool.value or not edgesInitialized.value: #add initialized
                print(multiprocessing.current_process(), "waiting .recv")
                self.cond.wait()
            data = self.conn.recv()
            updateEdges(self.edges, self.thisedge[0], self.thisedge[1], ' ')
            drawGraph(self.nodes, self.edges, self.printIteration)
            self.printIteration.value += 1
            self.cbool.value = False
            self.cond.notify_all()
        return data
    
def initializeEdge(tmpname, name):
    for i in range(len(edges._getvalue())):
        if edges[i][0] == tmpname:
            edges[i][0] = name
        if edges[i][1] == tmpname:
            edges[i][1] = name

def updateEdges(edges, name1, name2, input):
    e = len(edges._getvalue())
    for i in range(e):
        if name1 == edges[i][0] and name2 == edges[i][1]:
            edges[i][2] = input
    return edges

# Currently not used. Can be used to change color of nodes, or add nodes dynamically.
def updateNodes(nodes, name, color='black'):
    n = len(nodes._getvalue())
    for i in range(n):
        if name == nodes[i][0]:
            nodes[i][1] = color

# ---- Worker Roles ---- !

def producer(producer_connection : VConnection):
#def producer(consumer_producer_connection : VConn):
    print("producer:", producer_connection.conn)
    for i in range(5):
        producer_connection.send(str(i))
        print("producer:", multiprocessing.current_process(), "sent: ", i)
        
def transmitter(consumer_connection : VConnection, producer_connection : VConnection):
    print("transmitter:", producer_connection.conn, " and ", consumer_connection.conn)
    for i in range(5):
        data = consumer_connection.recv()
        producer_connection.send(data)


def consumer(consumer_connection : VConnection):
#def consumer(consumer_producer_connection : VConn):
    print("consumer:", consumer_connection.conn)
    for i in range(5):
        data = consumer_connection.recv()
        print("consumer:", multiprocessing.current_process(), "received: ", data)


def pingpong(i, input : VConnection, output : VConnection, initial_data=""):
    if initial_data:
        output.send(initial_data)
    while True:
        data = input.recv()
        time.sleep(1)
        print(f'{i}: {data}')
        output.send(data)

def Pipe(name=None):
    c1, c2 = multiprocessing.Pipe()
    
    #workerbool is used to prevent blocking when calling .recv(). 
    #This is needed because the if .recv acquires the lock before something has been sent it would block. 
    workerbool = multiprocessing.Value(c_int, False)

    tmpname1 = None
    tmpname2 = None
    edge = manager.list([tmpname1, tmpname2, " "])
    print("State of edge:", edge)
    edges.extend([edge])

    print("State of edges:")
    printEdges(edges)

    #Give VConnection the other end of the pipe as an accesible property?
    vc1 = VConnection(c1, workerbool, edge, tmpname2)
    vc2 = VConnection(c2, workerbool, edge, tmpname2)
    
    return vc1, vc2

class VProcess(multiprocessing.Process):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=(), *, daemon=None):
        nodes.extend([manager.list([name, "black"])])
        super().__init__(group, target, name, args, kwargs, daemon=daemon)


# nodes = pairs of names and colors of nodes
# edges = triple of two process names, connected by a channel, and a label describing what is being sent
def printNodes(nodes):
    n = len(nodes._getvalue())
    print([nodes[i]._getvalue() for i in range(n)])

def printEdges(edges):
    n = len(edges._getvalue())
    print([edges[i]._getvalue() for i in range(n)])

# ---- Tests ---- !

def testProducerConsumer():
    pipe_1_in, pipe_1_out = Pipe("p2")
    pipe_2_in, pipe_2_out = Pipe("p2")
    
    processes = [VProcess(name="p1", target=producer, args=(pipe_1_out,)),
                VProcess(name="p2", target=consumer, args=(pipe_1_in,)),
                VProcess(name="p3", target=producer, args=(pipe_2_out,)),
                VProcess(name="p4", target=consumer, args=(pipe_2_in,))]

    return processes  


def testTransmit():
    vc1, vc2 = Pipe("t0")
    vc3, vc4 = Pipe("c0")

    processes =  [multiprocessing.Process(name="p0", target=producer, args=(vc1,)),
                    multiprocessing.Process(name="t0", target=transmitter, args=(vc2, vc3,)),
                    multiprocessing.Process(name="c0", target=consumer, args=(vc4,))]

    return processes

def testPingPong():
    pipe_1_in, pipe_1_out = Pipe("p1")
    pipe_2_in, pipe_2_out = Pipe("p2")

    processes = [VProcess(name="p1", target=pingpong, args=(0, pipe_1_in, pipe_2_out, "hello")),
                VProcess(name="p2", target=pingpong, args=(1, pipe_2_in, pipe_1_out))]#,
                
    return processes    


if __name__ == '__main__':
    processes = testProducerConsumer() # Works
    #processes = testPingPong() # Blocks, because the process will never do the second .recv() / .send() call respectively
    #processes = testTransmit() # Blocks, because the process with target=transmit will never call .recv()

    for p in processes:
        p.start()

    for p in processes:
        p.join()