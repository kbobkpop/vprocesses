import multiprocessing
import graphviz

#Notes:
#1. Initialize VDigraph with a path.
#2. Consider how to visualize. Are edges or nodes more important.
#3. Consider general structure in a UML-kinda-way. What has what and what is responsible for what for updating the graph/visulization.
#4. There are race conditions if not using time.sleep() in between calls to draw.
#5. Create logging system

class VDigraph(graphviz.Digraph):
    iterator = 0

    def draw(self, path):
        iteratedpath = path + str(self.iterator) + '.gv'
        super().render(iteratedpath)
        self.iterator = self.iterator + 1


class VProcess(multiprocessing.Process):
    def __init__(self, dgraph : VDigraph, vname: str, group=None, target=None, name=None, args=(), kwargs={},
                 *, daemon=None):
        self.dgraph = dgraph
        self.name = vname
        self.dgraph.node(self.name)
        super().__init__(group=group, target=target, name=name, args=args, kwargs=kwargs, daemon=daemon)

# Methods that I thought would be relevant, but are not currently used.
"""
    def set_ready(self):
        self.dgraph.node(self.name, color='red')

    def set_waiting(self):
        self.dgraph.node(self.name, color='black')

    def connect(self, vpnode):
        self.dgraph.edge(self.name, vpnode.name)
"""

class VConn():
    def __init__(self, dgraph : VDigraph, conn):
        self.conn = conn
        self.dgraph = dgraph
    
    def set_ready(self, name):
        self.dgraph.node(name, color='red')
        self.dgraph.draw('doctest-output/test_vpgraph_step')

    def set_waiting(self, name):
        self.dgraph.node(name, color='black')
        self.dgraph.draw('doctest-output/test_vpgraph_step')

    def connect(self, sendername, receivername):
        self.dgraph.edge(sendername, receivername)

#Two ideas for multiprocessing.Pipe() wrappers

# 1.
class VPipe():
    def __init__(self, duplex: bool = True):
        self.pipe = multiprocessing.Pipe(duplex) 

# 2.
def VPipef(duplex: bool = True):
    return multiprocessing.Pipe(duplex)