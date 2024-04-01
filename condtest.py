import time
import multiprocessing

lock = multiprocessing.Lock()
workercond = multiprocessing.Condition(lock)
managercond = multiprocessing.Condition()
#print(workercond)

#booleans to control whether workers and managers are free to "go"
wgo = False
mgo = True

def producer(consumer_producer_connection, wcond, mcond):
    for i in range(5):
        with wcond:
            while not wgo: #possibly (likely) more conditions
                print("producer is waiting")
                wcond.wait()
            consumer_producer_connection.send(f"hello {i}")
            print(f"{i}. iteration of producer.")
            mgo = True
            wgo = False
            mcond.notify()

def consumer(consumer_producer_connection, wcond, mcond):
    for i in range(5):
        with wcond:
            while not wgo:
                print("consumer is waiting")
                wcond.wait()
            data = consumer_producer_connection.recv()
            print(f"{i}. iteration of consumer - {data} received")
            mgo = True
            wgo = False
            mcond.notify()

def manage(wcond, mcond, wgo):
    while True:
        with mcond:
            while not mgo:
                print("manager is waiting")
                mcond.wait()
            mgo = False
            wgo = True
            wcond.notify_all()

cp1, cp2 = multiprocessing.Pipe()

p1 = multiprocessing.Process(target=producer, args=(cp1, workercond, managercond))
p2 = multiprocessing.Process(target=consumer, args=(cp2, workercond, managercond))

p1.start()
p2.start()

manage(workercond, managercond)
            
        
