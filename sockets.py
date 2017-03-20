#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle, Matthew Dekinder
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, redirect
from flask_sockets import Sockets
from flask_cors import CORS, cross_origin
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True
CORS(app)

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))
        print "updating listeners"
        print entity
        obj = {}
        #obj["entity"] = entity
        #obj["data"] = self.get(entity)
        print "here"
        obj[entity] = self.get(entity)

        msg = json.dumps(obj)
        print "message: "+msg
        sendall_ws(msg)

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()
clients = list()

#https://github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()

def set_listener( entity, data ):
    ''' do something with the update ! '''

myWorld.add_set_listener( set_listener )
        
@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return redirect('/static/index.html')

def read_ws(ws,client):
    '''A greenlet function that reads from the websocket and updates the world'''
    # XXX: TODO IMPLEMENT ME
    #Adapted from https://github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py 
    #By Abram Hindle under the Apache 2 Licence
    try:
        while True:
            msg = ws.receive()
            print "WS RECV: %s" % msg
            if (msg is not None):
                packet = json.loads(msg)
                
                for key in packet:
                    myWorld.set(key, packet[key])

                #This works but is not what the test expects
                #if (packet["method"] == "update"):
                #    #print packet["entity"], packet["data"]
                #    myWorld.set(packet["entity"],packet["data"] ) #update the world. This should now be sent to each listener
                #elif (packet["method"] == "init_world"): 
                #    for key in myWorld.world():
                #        myWorld.update_listeners(key)
                
            else:
                print "breaking (null message through ws)"
                break
    except:
        print "exception resulting while monitoring the websocket"
        '''Done'''

def sendall_ws(msg):
    #Adapted from https://github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py 
    #By Abram Hindle under the Apache 2 Licence
    for client in clients:
        client.put( msg )

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    # XXX: TODO IMPLEMENT ME
    #https://github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
    client = Client()
    clients.append(client) #shouldn't I be setting this as a listener?
    #add_set_listener(client)
    g = gevent.spawn( read_ws, ws, client )  
    print "Subscribing"
    try:
        #send initial state
        state = myWorld.world()
        init_world = json.dumps(state)
        ws.send(init_world)
        while True:
            # block here
            msg = client.get()
            #print "Got a message!"
            ws.send(msg)
    except Exception as e:# WebSocketError as e:
        print "WS Error %s" % e
    finally:
        clients.remove(client) #this needs to remove the listener
        gevent.kill(g)



def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data != ''):
        return json.loads(request.data)
    else:
        return json.loads(request.form.keys()[0])


#These routes are adapted from my assignemnt 4. 
@app.route("/entity/<entity>", methods=['POST','PUT'])
@cross_origin(origin='*',headers=['Content-Type','Authorization'])
def update(entity):
    '''update the entities via this interface'''
    myWorld.set(entity, flask_post_json()) #TODO: get the data for this method

    #http://stackoverflow.com/questions/26079754/flask-how-to-return-a-success-status-code-for-ajax-call
    return jsonify(myWorld.get(entity));

@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    return jsonify(myWorld.world())

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    return jsonify(myWorld.get(entity))

@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()
    return jsonify(myWorld.world())



if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
