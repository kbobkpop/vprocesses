
import multiprocessing.connection
import time
import multiprocessing
import select
import graphviz

class PatchManager():
    def __init__(self, processes, connections, edges) -> None:
        self.processes = processes
        self.connections = connections
        self.requests_from_worker_connections = []
        self.signal_to_worker_connections = []
        self.recv_send_dict = {} #Normal connections returned from multiprocessing.Pipe() in PatchConnection.setup_manager_connection
        self.tickCounter = 1
        self.processNodes = [] 
        self.edges = edges
        self.printCounter = 0
        self.uncompletedSends = []
        self.uncompletedRecvs = []
        self.waiting_to_send_connection = []
        self.waiting_to_receive_connection = []


        for process in self.processes:
            process.report_channels() #returns the process' connections
            self.processNodes.append([process.name, "black"])

        self.connection_process_lookup = {}

        for connection in self.connections: #4 x connections
            connected_process = None
            for process in self.processes: #2 x processes
                if connection in process.report_channels(): #"in" checks all elements for equality in list.
                    connected_process = process
            if connected_process != None: #if connected_process was assigned
                #Maps the given PatchConnection's name to a connected process
                self.connection_process_lookup[connection.name] = connected_process #adding key=connection.name, value=connected_process




    def start(self):
        #setup all connections, possibly make an init-bool
        for connection in self.connections:
            recv, send = connection.setup_manager_connection()
            self.recv_send_dict[recv] = send # Dictionary mapping receive to send connections
            self.requests_from_worker_connections.append(recv)
            self.signal_to_worker_connections.append(send) #Do I need this?

        for process in processes:
            for connection in process.connections:
                process.from_worker_connections.append(connection.recv_from_worker)
                process.to_worker_connections.append(connection.send_to_worker) 

        for p in processes:
            p.start()

    #Make an edge class?
    def run_all_to_tick(self, processes):
        print(f"Tick {self.tickCounter} started")
        self.tickCounter += 1
        sendEdges = []
        recvEdges = []
        woke = [False for _ in processes]

        while False in woke:
            for index, process in enumerate(processes):
                (inputs, _, _) = select.select(process.from_worker_connections, [], [])
                for conn in process.from_worker_connections:
                    if conn in inputs:
                        action, process1Name, VConnName, otherEndsVConnName, data = conn.recv()
                        woke[index] = True
                        for connection in self.connections:
                            if otherEndsVConnName == connection.name:
                                process2Name = self.connection_process_lookup[connection.name].name
                        if action == "recv":
                            self.waiting_to_receive_connection.append((process1Name, self.recv_send_dict[conn]))
                            recvEdges.append([process2Name, process1Name, data])
                        elif action == "send":
                            self.waiting_to_send_connection.append((process1Name, self.recv_send_dict[conn]))
                            sendEdges.append([process1Name, process2Name, data])

        updateNowList = []
        self.uncompletedSends.extend(sendEdges)
        self.uncompletedRecvs.extend(recvEdges)

        #Check send:
        for currentedge in self.edges:
            for newedge in self.uncompletedSends:
                if currentedge[0] == newedge[0] and currentedge[1] == newedge[1]:
                    if currentedge[2] == ' ':
                        updateNowList.append(newedge)
        
        # Check recv:
        # for each edge in edges, compare if the same edge is in uncompletedRecvs:
        # If that is the case, check if that edge is currently transfering data add that uncompletedRecvs to the updatelist with empty " " and send messages to the two connections so that they can continue  
        for currentedge in self.edges:
            for newedge in self.uncompletedRecvs:
                if currentedge[0] == newedge[0] and currentedge[1] == newedge[1]:
                    if currentedge[2] != ' ':
                        p1name = None
                        p2name = None
                        #We are now adding the edge to be updated below for the visual graph and completing the logical sending and receiving, by sending a message to the two connections
                        updateNowList.append(newedge)
                        for conn in self.waiting_to_send_connection:
                            p1name, c = conn
                            if p1name == newedge[0]:
                                c.send(True)
                                self.waiting_to_send_connection.remove(conn)
                        for conn in self.waiting_to_receive_connection: #Could there be a problem if a process was waiting on two connections? I don't think so, as two connections should never be waiting on two connections.
                            p2name, c = conn
                            if p2name == newedge[1]:
                                c.send(True)
                                self.waiting_to_receive_connection.remove(conn)
                                self.uncompletedRecvs.remove(newedge)
                                for edge in self.uncompletedSends:
                                    if edge[0] == newedge[0] and edge[1] == newedge[1]:
                                        self.uncompletedSends.remove(edge)
        for edge in updateNowList:                
            self.updateEdges(edge[0], edge[1], edge[2])
        self.drawGraph()

        ableProcesses = self.processes[:]
        for process in self.processes:
            for p in self.uncompletedSends:
                if process.name == p[0]:
                    ableProcesses.remove(process)
            for p in self.uncompletedRecvs:
                if process.name == p[1]:
                    ableProcesses.remove(process)

        #print(f"ableProcesses: {ableProcesses}")
        
        return ableProcesses
    
    def init_graph(self):
        for p1 in self.processes:
            for conn1 in p1.connections:
                for p2 in self.processes:
                    for conn2 in p2.connections:
                        if conn1.otherEnd == conn2 and conn1.sender == True:
                            self.edges.append([p1.name, p2.name, " "])
                            #print(f"added edge: ({p1.name}, {p2.name})")
        self.drawGraph()
        print(f"Graph init ended, this is the current state: {self.edges}")


    #extend this with labels and titles, eg. tick number
    def drawGraph(self):
        dgraph = graphviz.Digraph()
        for i in range(len(self.processNodes)):
            dgraph.node(self.processNodes[i][0], color=self.processNodes[i][1])
        for i in range(len(edges)):
            dgraph.edge(self.edges[i][0], self.edges[i][1], self.edges[i][2])
        filename = 'output/Tick_' + str(self.printCounter)
        dgraph.render(filename)
        print(filename, "rendered")
        self.printCounter += 1

    def updateEdges(self, name1, name2, input):
        for i in range(len(self.edges)):
            if name1 == self.edges[i][0] and name2 == self.edges[i][1]:
                self.edges[i][2] = str(input)
                #print(f"updated edges[{i}][2] to '{input}'")
        #print("State of edges after update:", self.edges)

    def getProcess(self, processName):
        for process in self.processes:
            if process.name == processName:
                return process
            
    def getRecvProcess(self, conn, processName):
        for process in self.processes:
            if process.name == processName:
                for connection in process.connections:
                    if connection.recv_from_worker == conn:
                        return process

class VProcess(multiprocessing.Process):
    def __init__(self, group = None, target = None, name = None, args = [], kwargs = {}, *, daemon = None) -> None:
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self.to_worker_connections = []
        self.from_worker_connections = [] 
        self.connections = [] # Connections received as parameters
        
        for arg in args:
            if type(arg) == VConnection:
                self.connections.append(arg)
    
    def report_channels(self):
        #print(self.connections)
        return self.connections
    
    # Maybe this one can be used to run the ticks by accessing the target method through BaseProcess, and control the ticks.
    def run_to_tick():
        pass
        
class VConnection():
    def __init__(self, connection, name, otherEndsName, sender=True) -> None:
        self.name = name
        self.otherEndsName = otherEndsName
        self.otherEnd = None
        self.connection = connection
        self.send_to_manager = None
        self.recv_from_worker = None
        self.send_to_worker = None 
        self.recv_from_manager = None 
        self.sender = sender

    def setup_manager_connection(self):
        self.send_to_manager, self.recv_from_worker = multiprocessing.Pipe()
        self.send_to_worker, self.recv_from_manager = multiprocessing.Pipe()
        return self.recv_from_worker, self.send_to_worker

    def recv(self):
        self.send_to_manager.send(("recv", multiprocessing.current_process().name, self.name, self.otherEndsName, " "))
        good_to_go = self.recv_from_manager.recv()
        data = self.connection.recv()
        if good_to_go:
            return data

    def send(self, data):
        self.send_to_manager.send(("send", multiprocessing.current_process().name, self.name, self.otherEndsName, data))
        good_to_go = self.recv_from_manager.recv()
        self.connection.send(data)
        
def VPipe(name=""):
    end1, end2 = multiprocessing.Pipe()
    if name == "":
        name = id(end1)
    patchConnection1 = VConnection(end1, f"{name}_in", f"{name}_out", sender=True)
    patchConnection2 = VConnection(end2, f"{name}_out", f"{name}_in", sender=False)
    patchConnection1.otherEnd = patchConnection2
    patchConnection2.otherEnd = patchConnection1

    return patchConnection1, patchConnection2

def pingpong(i, input, output, initial_data=""):
    if initial_data:
        output.send(initial_data)
    while True:
        data = input.recv()
        time.sleep(1)
        #print(f"{multiprocessing.current_process().name}: {data}")
        output.send(data)

def producer(queue):
    for i in range(5):
        queue.send(i)
        queue.send("hello")

def transmitter(conn1, conn2):
    for i in range(5):
        data = conn1.recv()
        conn2.send(data)

def consumer(queue):
    while True:
        data = queue.recv()
        print(f"{data}")


def doubleConsumer(queue1, queue2):
    while True:
        data1 = queue1.recv()
        data2 = queue2.recv()
        data3 = queue1.recv()
        data4 = queue2.recv()

        if data3 == "hello" and data4 == "hello":
            print(f"{data1}-{data2}")

def doubleInTransmitter(conn1, conn2, conn3):
    for i in range(5):
        data1 = conn1.recv()
        data2 = conn2.recv()

        dataout = str(data1) + " + " + str(data2) 

        conn3.send(dataout)

def doubleOutTransmitter(conn1, conn2, conn3):
    for i in range(5):
        data = conn1.recv()
        conn2.send(data)
        conn3.send(data)

def transmitterTest():
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(pipe_1_in,),
            name="p1"
        ),
        VProcess(
            target=transmitter, 
            args=(pipe_1_out, pipe_2_in),
            name="t1"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_2_out,),
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

def doubleInTransmitterTest():
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    pipe_3_in, pipe_3_out  = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(pipe_1_in,),
            name="p2"
        ),
        VProcess(
            target=producer, 
            args=(pipe_2_in,),
            name="p3"
        ),
        VProcess(
            target=doubleInTransmitter, 
            args=(pipe_1_out, pipe_2_out, pipe_3_in),
            name="t2"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_3_out,),
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

def doubleOutTransmitterTest():
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    pipe_3_in, pipe_3_out  = VPipe()

    processes = [
        VProcess(
            target=producer, 
            args=(pipe_1_in,),
            name="p4"
        ),
        VProcess(
            target=doubleOutTransmitter, 
            args=(pipe_1_out, pipe_2_in, pipe_3_in),
            name="t3"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_2_out,),
            name="c3"
        ),
        VProcess(
            target=consumer, 
            args=(pipe_3_out,),
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

def pingPongTest():
    pipe_1_in, pipe_1_out  = VPipe()
    pipe_2_in, pipe_2_out  = VPipe()
    processes = [
        VProcess(
            target=pingpong, 
            args=(0, pipe_1_in, pipe_2_out, "hello"),
            name="Albert"
        ),
        VProcess(
            target=pingpong, 
            args=(1, pipe_2_in, pipe_1_out),
            name="Bertha"
        )
    ]
    channels = [
        pipe_1_in,
        pipe_1_out,
        pipe_2_in,
        pipe_2_out
    ]
    return processes, channels

def producerDoubleConsumerTest():
    q11, q12 = VPipe()
    q21, q22 = VPipe()


    processes = [
        VProcess(
            target=producer, 
            args=(q11, ),
            name="p5"
        ),
        VProcess(
            target=producer, 
            args=(q21,),
            name="p6"
        ),
        VProcess(
            target=doubleConsumer, 
            args=(q12, q22),
            name="c5"
        )
    ]
    channels = [q11, q12, q21, q22]
    return processes, channels

def producerConsumerTest():
    q11, q12 = VPipe()
    q21, q22 = VPipe()


    processes = [
        VProcess(
            target=producer, 
            args=(q11, ),
            name="p7"
        ),
        VProcess(
            target=producer, 
            args=(q21,),
            name="p8"
        ),
        VProcess(
            target=consumer, 
            args=(q12,),
            name="c7"
        ),
        VProcess(
            target=consumer, 
            args=(q22,),
            name="c8"
        )
    ]
    channels = [q11, q12, q21, q22]
    return processes, channels


p = []
c = []

processes, channels = pingPongTest()
p.extend(processes)
c.extend(channels)
processes, channels = producerDoubleConsumerTest()
p.extend(processes)
c.extend(channels)
processes, channels = producerConsumerTest()
p.extend(processes)
c.extend(channels)
processes, channels = transmitterTest()
p.extend(processes)
c.extend(channels)
processes, channels = doubleInTransmitterTest()
p.extend(processes)
c.extend(channels)
processes, channels = doubleOutTransmitterTest()
p.extend(processes)
c.extend(channels)

processes, channels = p, c
edges = []

patchManager = PatchManager(processes, channels, edges)
patchManager.init_graph()
patchManager.start()

ableProcesses = patchManager.run_all_to_tick(processes)

running = True
while running:
    response = input("Press enter to run next tick:")
    if response == "q" or response == "quit":
        running = False
    ableProcesses = patchManager.run_all_to_tick(ableProcesses)