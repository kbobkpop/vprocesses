import multiprocessing
import random
import graphviz

# VConnections no longer have separate connections but have the connections of their VProcess
# which are assigned upon initialization of the manager.
# No need for select objects.
# No need to instantiate multiple VLocks. The same object can be share across multiple processes.
# Nested release and acquire calls on different locks are resolved in the same tick.
# Same for nested select calls if something is being sent on a channel being listened on.

class VManager():
    """
    Parameters:
        - vprocesses: A list of VProcesses which will be part of the system.
        - vconnections: A list of VConnections which will be part of the system.
        - vlocks: A list of VLocks which will be part of the system.
        - various options for customizing how the system runs.

    VManager is the class responsible for coordinating the execution of the system processes.
    """
    def __init__(self, vprocesses, vconnections, vlocks=[], logging=False, output='output/', output_format='pdf', interactive_locks=False, log_file_name="log.txt", draw=True, tick_tock=True, incr_ticks=True) -> None:
        self.processes = vprocesses # List of VProcess passed as to the class constructor as argument
        self.connections = vconnections # List of VConnection classes passed to the class constructor as argument
        if isinstance(vlocks, VLock):
            vlocks = [vlocks]
        self.locks = vlocks # List of VLock objects
        self.from_to_connection_dict = {} # Dictionary of normal connections, where they key is the connection intended for the manager to receive messages from sync-objects and the value is connection used to send to sync-objects. Populated in __init__
        self.sync_object_process_lookup = {} # Dictionary mapping VConnections to process names
        self.process_to_manager_send_conn = {} # Dictionary mapping process name to that process' send connection to the manager
        self.process_to_manager_recv_conn = {} # Dictionary mapping process name to that process' receive connection from the manager
        self.process_to_worker_send_conn = {} # Dictionary mapping process name to that process' send connection to the worker
        self.process_to_worker_recv_conn = {} # Dictionary mapping process name to that process' receive connection from the worker
        self.tick_counter = 0 # Counter used for the number on the image file and showing which tick is run
        self.edges = [] # List of edges between processes for the graph used for drawing the image
        self.process_nodes = [] # List of process nodes for the graph used for drawing the image
        self.terminated_nodes = []
        self.lock_nodes = [] # List of lock nodes for the graph used for drawing the image - Could possibly be merged with processNodes
        self.lock_edges = [] # List of edges between processes and locks for the graph used for drawing the image
        self.locked_locks = [] # List of locks that are currently locked
        self.waiting_to_send = [] # List of processes waiting to send
        self.waiting_to_receive = [] # List of processes waiting to receive
        self.waiting_to_acquire = [] # List of processes waiting to acquire a lock
        self.waiting_to_release = [] # List of processes waiting to release a lock
        self.waiting_to_select = [] # List of processes waiting to select
        self.output_directory = output # Output directory
        self.output_format = output_format # Output format of the graph drawings
        self.logging = logging # Boolean controlling logging
        self.interactive = interactive_locks # Boolean controlling if lock acquisition is selected by the user
        self.draw = draw # Boolean controlling if images of the graph should be drawn
        self.tick_tock = tick_tock # Boolean controlling if 'tock' images should be drawn
        self.increment_ticks = incr_ticks # Boolean controlling if ticks should be incremented

        if logging:
            self.log = open(log_file_name, "w")

        locknamenum = 1
        for lock in self.locks:
            if isinstance(lock.name, int):
                lock.name = "lock" + str(locknamenum)
                locknamenum += 1
                self.lock_nodes.append(lock.name)

        # Setting up connections
        for process in self.processes:
            self.process_nodes.append([process.name, "green", "solid", process.name])
            recv, send = process.setup_manager_connection()
            self.from_to_connection_dict[recv] = send
            self.process_to_manager_send_conn[process.name] = process.send_to_manager
            self.process_to_manager_recv_conn[process.name] = process.recv_from_manager
            self.process_to_worker_recv_conn[process.name] = process.recv_from_worker
            for connection in process.connections:
                connection.send_to_manager = process.send_to_manager
                connection.recv_from_manager = process.recv_from_manager
                self.sync_object_process_lookup[connection.name] = process

        VSelect.set_dictionaries(self.process_to_manager_send_conn, self.process_to_manager_recv_conn)
        for lock in self.locks:
            lock.set_dictionaries(self.process_to_manager_send_conn, self.process_to_manager_recv_conn)

    def start(self):
        """
        Initialize the graph and start all processes.
        """
        self.init_graph()
        for process in self.processes:
            process.start()

    def stepwise_ticks(self, processes):
        """
        Parameters:
            - processes: A list of processes able to run.

        Run one tick at a time by continuously calling self.run_all_to_tick()
        but waiting for user input in between calls.
        """
        running = True
        while running:
            response = input("Press enter to run next tick or type 'q' to end execution:")
            if response in ('q', 'quit'):
                running = False
                if self.logging:
                    self.log.close()
            else:
                processes = self.run_all_to_tick(processes)
                if not self.processes:
                    running = False

    def run_ticks_to_end(self, processes):
        """
        Parameters:
            - processes: A list of processes able to run.

        Keeps calling self.run_all_to_tick() until all processes have finished or an error occur.

        Requires processes to be set up to terminate, else it will not stop.
        """
        while self.processes:
            processes = self.run_all_to_tick(processes)
            if processes is False:
                break

    def run_all_to_tick(self, processes):
        """
        Parameter:
            - processes: A list of processes able to run.

        The main method controlling the tick (and tock).
        Gets requests, handle requests, updates and draws the graph.

        Returns a list able processes which should be passed as argument for the next call to this method.
        """

        self.tick_counter += 1
        print(f"Tick {self.tick_counter} started")

        if len(processes) == 0:
            print("Exiting - System is not progressing! - Either because of a deadlock, a process is blocking or a bug.")
            return False

        releases, acquires, selects = self.get_requests(processes)

        acquires.extend(self.waiting_to_acquire)
        selects.extend(self.waiting_to_select)

        acquires, selects = self.handle_non_channels(releases, acquires, selects)

        self.waiting_to_acquire = acquires
        self.waiting_to_select = selects

        self.update_graph()
        if self.draw:
            self.draw_graph("Tick")

        self.handle_transmissions()

        self.update_graph()

        if self.tick_tock:
            if self.draw:
                self.draw_graph("Tock")

        #self.print_state()
        able_processes = self.get_able_processes()

        return able_processes

    def get_requests(self, able_processes):
        """
        Receive a request from each able process.
        - Requests to send or receive are put on internal lists of requests.
        - Requests to select, acquire or release locks are returned for resolvement this tick.

        Returns a list of release requests, a list of acquire requests and a list of select requests.
        """
        requests_sent_from_able_processes = [0 for _ in able_processes]
        loglist = []
        releases = []
        acquires = []
        selects = []
        for index, process in enumerate(able_processes):
            conn = self.process_to_worker_recv_conn[process.name]
            request = conn.recv()
            requests_sent_from_able_processes[index] += 1
            action, rest = request
            if action == "acquire":
                lock_name = rest
                acquires.append([lock_name, process.name, self.from_to_connection_dict[conn]])
                loglist.append(f"{process.name} requests to acquire {lock_name}")
            elif action == "release":
                lock_name = rest
                releases.append([lock_name, process.name, self.from_to_connection_dict[conn]])
                loglist.append(f"{process.name} requests to release {lock_name}")
            elif action == "select":
                selectlist = rest
                selects.append([process.name, self.from_to_connection_dict[conn], selectlist])
                loglist.append(f"{process.name} requests to selecting")
            elif action == "terminate":
                self.from_to_connection_dict[conn].send(True)
                self.processes.remove(process)
                self.update_node(process.name, "black", "bold", process.name + "☠️")
                self.terminated_nodes.append(process.name)
                process.join()
                loglist.append(f"{process.name} requests to terminate")
            else:
                vconn_name, other_ends_vconn_name, transfer = rest
                if action == "recv":
                    self.waiting_to_receive.append((other_ends_vconn_name, vconn_name, " ", self.from_to_connection_dict[conn]))
                    loglist.append(f"{process.name} requests to receive from {self.sync_object_process_lookup[other_ends_vconn_name].name}")
                elif action == "send":
                    self.waiting_to_send.append((vconn_name, other_ends_vconn_name, transfer, self.from_to_connection_dict[conn]))
                    loglist.append(f"{process.name} requests to send to {self.sync_object_process_lookup[other_ends_vconn_name].name}")

        if self.logging:
            self.log.write(f"Tick {self.tick_counter}" + '\n')
            for entry in loglist:
                self.log.write(entry + '\n')
                self.log.flush()

        for request in requests_sent_from_able_processes:
            if request != 1:
                print(f"ERROR: A PROCESS HAS EITHER SENT MORE THAN ONE MESSAGES OR NOT SENT A MESSAGE - {requests_sent_from_able_processes}")

        return releases, acquires, selects

    def handle_select(self, release_list, acquire_list, select_list):
        """
        For each select request, check if there is any data on any of the connections being polled.
        Sends a list of VConnections with data on the channels to the requesting process.

        Gets a new request from each process having received a permission to select.

        returns a list of release requests, acquire requests, select requests.
        """
        new_release_list = []
        new_acquire_list = []
        new_select_list = []

        selected = False

        temp_select_list = select_list[:]
        temp_send_list = self.waiting_to_send[:]

        for pslct in temp_select_list:  # self.waiting_to_select
            active_channels = []
            remove = False
            selectlist = pslct[2]
            for conn in selectlist:
                for wts in temp_send_list: #self.waiting_to_send
                    if conn.name == wts[1]:
                        remove = True
                        active_channels.append(conn.name)

            if remove is True:
                selected = True
                pslct[1].send(active_channels)
                process = self.get_process(pslct[0])
                releases, acquires, selects = self.get_requests([process])
                new_release_list.extend(releases)
                new_acquire_list.extend(acquires)
                new_select_list.extend(selects)
                select_list.remove(pslct)

        release_list.extend(new_release_list)
        acquire_list.extend(new_acquire_list)
        select_list.extend(new_select_list)

        return release_list, acquire_list, select_list, selected

    def handle_transmissions(self):
        """
        For each receive request, check if there is any matching send request.
        If that is the case send permissions to both processes and remove requests fron internal lists.
        """
        remove_recv = []
        for request in self.waiting_to_receive:
            for currentedge in self.edges:
                if currentedge[0] == request[0] and currentedge[1] == request[1]:
                    p1name = None
                    match = False
                    remove_list = []
                    for wts in self.waiting_to_send:
                        p1name, _, _, conn = wts
                        if p1name == request[0]:
                            conn.send(True)
                            remove_list.append(wts)
                            remove_recv.append(request)
                            request[3].send(True)

                    self.waiting_to_send[:] = [wts for wts in self.waiting_to_send if wts not in remove_list]

        self.waiting_to_receive[:] = [conn for conn in self.waiting_to_receive if conn not in remove_recv]

    def acquire_locks(self, release_list, acquire_list, select_list):
        """
        For each free lock, check if there are requests to acquire it. Among the requests to
        acquire a free lock, one random request will be selected and that process will be send
        a permission to acquire that lock. In case self.interactive_locks is True, the user will
        be prompted to select which process should acquire which lock.

        Gets a new request from each process having acquired a lock.

        returns a list of release requests, acquire requests, select requests.
        """
        processes_waiting_to_acquire = acquire_list[:]
        new_release_list = []
        new_acquire_list = []
        new_select_list = []

        acquired = False

        temp_locks = self.lock_nodes[:]
        for lock in temp_locks:
            if not self.check_locked(lock):
                temp_list = []
                for pwta in processes_waiting_to_acquire:
                    if lock == pwta[0]:
                        temp_list.append(pwta)
                if len(temp_list) > 0:
                    if self.interactive and len(temp_list) > 1:
                        for i, process in enumerate(temp_list):
                            print(f"Enter {i} to let {process[1]} acquire {lock}")
                        while True:
                            response = input("Make your choice: ")
                            try:
                                int(response)
                            except ValueError:
                                print(f"{response} is not an integer")
                            else:
                                choice = int(response)
                                if choice < 0 or choice >= len(temp_list):
                                    print(f"{choice} is not a valid valid choice")
                                else:
                                    temp_list[choice][2].send(True)
                                    process = self.get_process(temp_list[choice][1])
                                    releases, acquires, selects = self.get_requests([process])
                                    new_release_list.extend(releases)
                                    new_acquire_list.extend(acquires)
                                    new_select_list.extend(selects)
                                    self.locked_locks.append([temp_list[choice][0], temp_list[choice][1]])
                                    acquire_list.remove(temp_list[choice])
                                    break
                    else:
                        acquired = True
                        rand_index = random.randint(0, len(temp_list) - 1)
                        temp_list[rand_index][2].send(True)
                        process = self.get_process(temp_list[rand_index][1])
                        releases, acquires, selects = self.get_requests([process])
                        new_release_list.extend(releases)
                        new_acquire_list.extend(acquires)
                        new_select_list.extend(selects)
                        self.locked_locks.append([temp_list[rand_index][0], temp_list[rand_index][1]])
                        acquire_list.remove(temp_list[rand_index])

        release_list.extend(new_release_list)
        acquire_list.extend(new_acquire_list)
        select_list.extend(new_select_list)

        return release_list, acquire_list, select_list, acquired

    def handle_non_channels(self, release_list, acquire_list, select_list):
        """
        Resolves all requests not comming from VConnections.
        First locks are released, then acquired. This ensures that a process releasing a lock
        cannot acquire that same lock in the same tick, if another process was already waiting
        to acquire that lock.

        After this initial lock resolvement, all other lock requests and select requests are
        resolved until no more requests can be resolved. This means that nested calls to acquire
        locks, release locks and select will all be resolved within the tick.

        Returns a list of release requests, a list of acquire requests and a list of select requests
        which could not be resolved this tick.
        """

        # First all locks are released, potentiallly resulting in new non-channel requests.
        new_release_list, new_acquire_list, new_select_list = self.release_locks(release_list, [], select_list)
        # Second locks are being acquired but only by processes which requests did not follow from the just released locks.
        # This ensures that a process releasing a lock can not acquire it again, if another process is already waiting for that lock.
        release_list, acquire_list, select_list, acquired = self.acquire_locks(new_release_list, acquire_list, new_select_list)

        acquire_list.extend(new_acquire_list)

        acquired = True
        while (release_list or acquire_list or select_list) and acquired:
            acquired = False
            selected = True
            while (release_list or select_list) and selected:
                selected = False

                while release_list:
                    release_list, acquire_list, select_list = self.release_locks(release_list, acquire_list, select_list)

                if select_list:
                    release_list, acquire_list, select_list, selected = self.handle_select(release_list, acquire_list, select_list)

            if acquire_list:
                release_list, acquire_list, select_list, acquired = self.acquire_locks(release_list, acquire_list, select_list)
            else:
                break

        return acquire_list, select_list

    def release_locks(self, release_list, acquire_list, select_list):
        """
        For each request to release a lock send a permission to release that lock.
        Gets a new request from each process having released a lock.

        returns a list of release requests, acquire requests, select requests.
        """
        new_release_list = []
        new_acquire_list = []
        new_select_list = []
        remove_list = []

        temp_release_list = release_list[:]
        for wtr in temp_release_list:
            wtr[2].send(True)
            process = self.get_process(wtr[1])
            releases, acquires, selects = self.get_requests([process])
            new_release_list.extend(releases)
            new_acquire_list.extend(acquires)
            new_select_list.extend(selects)
            self.locked_locks.remove([wtr[0], wtr[1]])
            remove_list.append(wtr)

        for request in remove_list:
            release_list.remove(request)

        release_list.extend(new_release_list)
        acquire_list.extend(new_acquire_list)
        select_list.extend(new_select_list)

        return release_list, acquire_list, select_list

    def get_able_processes(self):
        """
        Infers which processes are able by taking all processes and removing the ones which are
        have pending requests waiting or are terminated.

        Returns a list of able processes.
        """
        able_processes = self.processes[:]

        for process in self.processes:
            for request in self.waiting_to_send:
                if process.name == self.sync_object_process_lookup[request[0]].name:
                    able_processes.remove(process)
            for request in self.waiting_to_receive:
                if process.name == self.sync_object_process_lookup[request[1]].name:
                    able_processes.remove(process)
            for request in self.waiting_to_acquire:
                if process.name == request[1]:
                    able_processes.remove(process)
            for request in self.waiting_to_select:
                if process.name == request[0]:
                    able_processes.remove(process)

        return able_processes

    def init_graph(self):
        """
        Initializes the graph.
        """

        for process1 in self.processes:
            for conn in process1.connections:
                if isinstance(conn, VConnection):
                    for process2 in self.processes:
                        for conn2 in process2.connections:
                            if isinstance(conn2, VConnection):
                                if conn.other_ends_name == conn2.name and conn.sender is True:
                                    self.edges.append([conn.name, conn2.name, " "])

            for lock in process1.locks:
                if isinstance(lock, VLock):
                    self.lock_edges.append([lock.name, process1.name, "black", "dashed"])

        if self.draw:
            self.draw_graph("Tock")

    def update_graph(self):
        """
        Updates the graph based on which requests are pending.
        """

        for node in self.process_nodes:
            color = "green"
            for request in self.waiting_to_send:
                if node[0] == self.sync_object_process_lookup[request[0]].name:
                    color = "red"
            for terminated_node in self.terminated_nodes:
                if node[0] == terminated_node:
                    color = "black"
            for request in self.waiting_to_receive:
                if node[0] == self.sync_object_process_lookup[request[1]].name:
                    color = "red"

            node[1] = color
            node[2] = 'solid'

        for edge in self.edges:
            new_edge = " "
            for req in self.waiting_to_send:
                if edge[0] == req[0]:
                    new_edge = req[2]
            edge[2] = new_edge

        for node in self.waiting_to_select:
            self.update_node(node[0], 'red', 'dashed', node[0])

        for edge in self.lock_edges:
            self.update_lock_edge(edge[0], edge[1], 'black', 'dashed')

        for request in self.waiting_to_acquire:
            self.update_node(request[1], 'purple', 'dashed', request[1])
            self.update_lock_edge(request[0], request[1], 'purple', 'dashed')

        for lock in self.locked_locks:
            self.update_lock_edge(lock[0], lock[1], 'blue', 'solid')

    def draw_graph(self, name):
        """
        Instantiates the graphviz graph, populates it with nodes and edges, and finally draws it.
        """

        dgraph = graphviz.Digraph(format=self.output_format)
        dgraph.attr(label=f"{name} {self.tick_counter}", labelloc="t")

        for node in self.process_nodes: # Format: [process name, color, style, label]
            dgraph.node(node[0], color=node[1], style=node[2], label=node[3])

        for edge in self.edges: # Format: [vconn1 name, vconn2 name, transfer data]
            process1 = self.sync_object_process_lookup[edge[0]].name
            process2 = self.sync_object_process_lookup[edge[1]].name
            dgraph.edge(process1, process2, str(edge[2]))

        for node in self.lock_nodes: # Format: [lock name]
            dgraph.node(node, shape="square")

        for edge in self.lock_edges: # Format: [lock name, process name, color, style]
            dgraph.edge(edge[0], edge[1], color=edge[2], style=edge[3], dir="none")

        if self.increment_ticks:
            file_name = self.output_directory + str(self.tick_counter) + '_'+ name
        else:
            file_name = self.output_directory + "State"

        dgraph.render(file_name)

    def update_edge(self, name1, name2, data):
        """
        Update an edge in the graph list.
        """
        for edge in self.edges:
            if name1 == edge[0] and name2 == edge[1]:
                edge[2] = str(data)

    def update_lock_edge(self, name1, name2, color, style):
        """
        Update a lock edge in the graph list.
        """
        for edge in self.lock_edges:
            if name1 == edge[0] and name2 == edge[1]:
                edge[2] = color
                edge[3] = style

    def update_node(self, node, color, style, label):
        """
        Update a node in the graph list.
        """
        for process_node in self.process_nodes:
            if node == process_node[0]:
                process_node[1] = color
                process_node[2] = style
                process_node[3] = label

    def print_state(self):
        """
        Prints the pending requests and locked locks.
        """
        print(f"self.waitingToSend: {self.waiting_to_send}")
        print(f"self.waitingToReceive: {self.waiting_to_receive}")
        print(f"self.waitingToSelect: {self.waiting_to_select}")
        print(f"self.waitingToAcquire {self.waiting_to_acquire}")
        print(f"self.waitingToRelease {self.waiting_to_release}")
        print(f"self.lockedLocks {self.locked_locks}")

    def check_locked(self, lock):
        """
        Check if a lock is locked.
        """
        for pair in self.locked_locks:
            if pair[0] == lock:
                return True
        return False

    def get_process(self, name):
        """
        Get a process object based on it's name.
        """
        for process in self.processes:
            if process.name == name:
                return process
        return []

class VProcess(multiprocessing.Process):
    """
    Sub-class of the multiprocessing.Process class.
    Works similarly to it's super class but with a bit with a few extra properties
    used to facilitate the communication with the VManager.
    It has two channels, one ingoing and one outgoing, which are used by the other synchronization
    methods to communicate with the VManager.

    Sorts out relevant synchronizataion objects from it's target method's args and puts
    those on internal lists which used by the VManager.
    """
    num = 0
    def __init__(self, group = None, target = None, name = None, args = [], kwargs = {}, *, daemon = None) -> None:
        if not name:
            name = 'p' + str(VProcess.num)
            VProcess.num += 1
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self.connections = [] # All synchronization objects given as parameters to target
        self.locks = []
        self.send_to_manager = None
        self.recv_from_worker = None
        self.send_to_worker = None
        self.recv_from_manager = None

        for arg in args:
            if isinstance(arg, VConnection):
                self.connections.append(arg)
            if isinstance(arg, VLock):
                self.locks.append(arg)
            if isinstance(arg, list):
                for elm in arg:
                    if isinstance(elm, VConnection):
                        self.connections.append(elm)
                    if isinstance(elm, VLock):
                        self.locks.append(elm)

    def setup_manager_connection(self):
        self.send_to_manager, self.recv_from_worker = multiprocessing.Pipe()
        self.send_to_worker, self.recv_from_manager = multiprocessing.Pipe()
        return self.recv_from_worker, self.send_to_worker

    def run(self):
        super().run()
        self.send_to_manager.send(("terminate", self.name))
        self.recv_from_manager.recv()


class VLock():
    """
    Wrapper to the multiprocessing.Lock class.
    Works similarly to the underlying Lock object except when .acquire or .release is called
    it sends request to the VManager which will return a permission when the state of the
    system allows it at which point the underlying lock will be released or acquired.
    """
    def __init__(self, name=None):
        self.lock = multiprocessing.Lock()
        if name:
            self.name = name
        else:
            self.name = id(self)

        self.process_to_manager_send_conn = None
        self.process_to_manager_recv_conn = None

    def set_dictionaries(self, send_dict, recv_dict):
        self.process_to_manager_send_conn = send_dict
        self.process_to_manager_recv_conn = recv_dict

    def acquire(self):
        process_name = multiprocessing.current_process().name
        send_conn = self.process_to_manager_send_conn[process_name]
        recv_conn = self.process_to_manager_recv_conn[process_name]
        send_conn.send(("acquire", self.name))
        recv_conn.recv()
        self.lock.acquire()

    def release(self):
        process_name = multiprocessing.current_process().name
        send_conn = self.process_to_manager_send_conn[process_name]
        recv_conn = self.process_to_manager_recv_conn[process_name]
        send_conn.send(("release", self.name))
        recv_conn.recv()
        self.lock.release()


class VSelect():
    """
    The vprocesses module's implementation of the select.select() function.
    VSelect.select can be used similarly to that function, but takes a list of VConnections as first argument.
    When VSelect.select is called, the list of VConnections is passed to the VManager
    which checks if there is any data on any of those channels. If that is the case,
    a list VConnections with data on their channels is returned.
    If there is no data on any channels, the call will block until there is.

    Returns a list of VConnections with data on each channel.
    """

    @classmethod
    def set_dictionaries(cls, send_dict, recv_dict):
        cls.process_to_manager_send_conn = send_dict
        cls.process_to_manager_recv_conn = recv_dict

    @classmethod
    def select(cls, rlist, wlist=[], xlist=[]):
        process_name = multiprocessing.current_process().name
        send_conn = cls.process_to_manager_send_conn[process_name]
        recv_conn = cls.process_to_manager_recv_conn[process_name]
        send_conn.send(("select", rlist)) # For now just sending selectlist1
        active_channels = recv_conn.recv() # active_channels is list of names of VConnections where something is being sent
        inputs = []
        for vconn_name in active_channels:
            for vconnection in rlist:
                if vconn_name == vconnection.name:
                    inputs.append(vconnection)
        return inputs, [], []


class VConnection():
    """
    Wrapper to the multiprocessing.Connection class.
    Works similarly to the underlying connection object except of sending or receiving directly
    it first sends a request to a VManager instance, which grants permission both sides of the channel are ready to transmit.

    Should be instantiated through a call to the VPipe() function.
    """
    def __init__(self, connection, name, other_ends_name, sender=True) -> None:
        self.name = name
        self.other_ends_name = other_ends_name
        self.connection = connection
        self.send_to_manager = None
        self.recv_from_manager = None
        self.sender = sender

    def send(self, data):
        self.send_to_manager.send(("send", [self.name, self.other_ends_name, data]))
        good_to_go = self.recv_from_manager.recv()
        if good_to_go:
            self.connection.send(data)
            print(multiprocessing.current_process().name, "sent", data)

    def recv(self):
        self.send_to_manager.send(("recv", [self.name, self.other_ends_name, " "]))
        good_to_go = self.recv_from_manager.recv()
        if good_to_go:
            data = self.connection.recv()
            return data
        return None


def VPipe(name=""):
    """
    Wrapper to the multiprocessing.Pipe() function.
    Works similarly to the underlying function except two VConnection objects are returned.

    Importantly the first returned VConnection object must only be used to send on,
    while the second one must only be used to receive on.

    Returns two VConnection objects.
    """
    end1, end2 = multiprocessing.Pipe(False)
    if name == "":
        name = id(end1)
    vconn1 = VConnection(end2, f"{name}_w", f"{name}_r", sender=True)
    vconn2 = VConnection(end1, f"{name}_r", f"{name}_w", sender=False)

    return vconn1, vconn2

# Aliases

Pipe = VPipe
Process = VProcess
Lock = VLock
current_process = multiprocessing.current_process
