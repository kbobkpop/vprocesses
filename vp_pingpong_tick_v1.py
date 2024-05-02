
import multiprocessing.connection
import time
import multiprocessing
import select
import graphviz







class PatchManager():
    def __init__(self, processes, connections, edges) -> None:
        self.processes = processes
        self.connections = connections
        self.recv_from_worker_connections = []
        self.send_to_worker_connections = []
        self.recv_send_dict = {} #Normal connections returned from multiprocessing.Pipe() in PatchConnection.setup_manager_connection
        self.tickCounter = 0
        self.processNodes = []
        self.edges = edges
        self.printCounter = 0

        for process in self.processes:
            process.report_channels() #returns the process' connections
            self.processNodes.append([process.name, "black"])

        print("These are the process nodes:", self.processNodes)

        self.connection_process_lookup = {}

        
        """ for connection in self.connections:
            recv, send = connection.setup_manager_connection()
            self.recv_send_dict[recv] = send # Dictionary mapping receive to send connections
            self.recv_from_worker_connections.append(recv)
            self.send_to_worker_connections.append(send) """






        for connection in self.connections: #4 x connections
            connected_process = None
            for process in self.processes: #2 x processes
                print("bla:", process)
                if connection in process.report_channels(): #"in" checks all elements for equality in list.
                    connected_process = process
            if connected_process != None: #if connected_process was assigned
                #Maps the given PatchConnection's name to a connected process
                #self.connection_process_lookup[connection] = connected_process #adding key=connection.name, value=connected_process
                self.connection_process_lookup[connection.name] = connected_process #adding key=connection.name, value=connected_process




    def start(self):
        #setup all connections, possibly make an init-bool
        for connection in self.connections:
            recv, send = connection.setup_manager_connection()
            self.recv_send_dict[recv] = send # Dictionary mapping receive to send connections
            self.recv_from_worker_connections.append(recv)
            self.send_to_worker_connections.append(send) #Do I need this?

        for p in processes:
            p.start()

    #TODO, implementer så at et tick ikke er både receive og send.

    def run_all_to_tick(self, ticks):
        for i in range(ticks):
            send = []
            recv = []
            print(f"Starting tick {i}")
            time.sleep(2)
            (inputs,_,_) = select.select(self.recv_from_worker_connections, [], [])
            for from_worker_channel in self.recv_from_worker_connections:
                if from_worker_channel in inputs:
                    action, process1Name, otherEndsName, data = from_worker_channel.recv()
                    #action, process1Name, otherEnd, data = from_worker_channel.recv()
                    for connection in self.connections:
                        if otherEndsName == connection.name:
                            process2Name = self.connection_process_lookup[connection.name].name
                    
                    print(f"Tick {i}: {process1Name} {action} - {process2Name}")
                    if action == "recv":
                        print(f"recv: updating edge: {process2Name} - {process1Name} with {data}")
                        recv.append([process2Name, process1Name, data])
                        #self.updateEdges(process2Name, process1Name, data)
                    elif action == "send":
                        print(f"send: updating edge: {process1Name} - {process2Name} with {data}")
                        send.append([process1Name, process2Name, data])
                        #self.updateEdges(process1Name, process2Name, data)
                    conn = self.recv_send_dict[from_worker_channel]
                    conn.send(True)
            for s in send:
                self.updateEdges(s[0], s[1], s[2])
                self.drawGraph()
            for r in recv:
                self.updateEdges(r[0], r[1], r[2])
                self.drawGraph()
            print(f"Tick {i} completed")
    
    def init_graph(self):
        for p1 in self.processes:
            for conn1 in p1.connections:
                for p2 in self.processes:
                    for conn2 in p2.connections:
                        if conn1.otherEnd == conn2 and conn1.sender == True:
                        #if conn1.otherEndsName == conn2.name and conn1.sender == True:
                            self.edges.append([p1.name, p2.name, " "])
                            print(f"added edge: ({p1.name}, {p2.name})")

        print(f"Graph init ended, this is the current state: {self.edges}")


    #extend this with labels and titles, eg. tick number
    def drawGraph(self):
        dgraph = graphviz.Digraph()
        for i in range(len(self.processNodes)):
            dgraph.node(self.processNodes[i][0], color=self.processNodes[i][1])
        for i in range(len(edges)):
            dgraph.edge(self.edges[i][0], self.edges[i][1], self.edges[i][2])
        filename = 'output/test_' + str(self.printCounter)
        dgraph.render(filename)
        print(filename, "rendered")
        self.printCounter += 1

    def updateEdges(self, name1, name2, input):
        for i in range(len(self.edges)):
            if name1 == self.edges[i][0] and name2 == self.edges[i][1]:
                self.edges[i][2] = input
                print(f"updated edges[{i}][2] to '{input}'")
        print("State of edges after update:", self.edges)

class PatchProcess(multiprocessing.Process):
    def __init__(self, group = None, target = None, name = None, args = [], kwargs = {}, *, daemon = None) -> None:
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self.to_manager = None 
        self.from_patch_process = None 
        self.connections = [] # Connections received as parameters
        for arg in args:
            if type(arg) == PatchConnection:
                self.connections.append(arg)

    def report_channels(self):
        print(self.connections)
        return self.connections
        
    #What are connections used for on the process
    def setup_manager_connection(self):
        self.to_manager, self.from_patch_process = multiprocessing.Pipe()
        return self.from_patch_process

    # Maybe this one can be used to run the ticks by accessing the target method through BaseProcess, and control the ticks.
    def run_to_tick():
        pass
        
class PatchConnection():
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
        print(f"{self.name} recieving")
        self.send_to_manager.send(("recv", multiprocessing.current_process().name, self.otherEndsName, " "))
        #self.send_to_manager.send(("recv", multiprocessing.current_process().name, self.otherEnd, " "))
        good_to_go = self.recv_from_manager.recv() #good_to_go Used for?
        print(f"{self.name}: good_to_go, recv:", good_to_go)
        if good_to_go:
            return self.connection.recv()

    def send(self, data):
        print(f"{self.name} sending")
        #self.send_to_manager.send(("send", multiprocessing.current_process().name, self.otherEnd, " "))
        self.send_to_manager.send(("send", multiprocessing.current_process().name, self.otherEndsName, data))
        good_to_go = self.recv_from_manager.recv() #good_to_go Used for?
        print(f"{self.name}: good_to_go, send:", good_to_go)
        if good_to_go:
            self.connection.send(data)


#Do I really need the name, if I can compare the object? #Also I could just generate a name?
def PatchPipe(name=""):
    end1, end2 = multiprocessing.Pipe()
    patchConnection1 = PatchConnection(end1, f"{name}_in", f"{name}_out", sender=False)
    patchConnection2 = PatchConnection(end2, f"{name}_out", f"{name}_in", sender=True)
    patchConnection1.otherEnd = patchConnection2
    patchConnection2.otherEnd = patchConnection1

    return patchConnection1, patchConnection2

def pingpong(i, input, output, initial_data=""):
    if initial_data:
        output.send(initial_data)
    while True:
        data = input.recv()
        time.sleep(1)
        print(data)
        output.send(data)

pipe_1_in, pipe_1_out  = PatchPipe(name="first")
pipe_2_in, pipe_2_out  = PatchPipe(name="second")

processes = [
    PatchProcess(
        target=pingpong, 
        args=(0, pipe_1_in, pipe_2_out, "hello"),
        name="Albert"
    ),
    PatchProcess(
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

#edges = [["Albert", "Bertha", ""], ["Bertha", "Albert", ""]]

edges = []

patchManager = PatchManager(processes, channels, edges)
patchManager.init_graph()
patchManager.start()
#time.sleep(2)
patchManager.run_all_to_tick(5)

#print("After call to tick")

#for process in processes:
#    process.start()
#
#for process in processes:
#    process.join()
