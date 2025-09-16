import numpy as np
import time
import random

from pythonosc.udp_client import SimpleUDPClient
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

from pyfirmata2 import Arduino

####################################################################################
####################################################################################


def rand_range(min, max):

    #random utility function that I need lol
    
    rand = float(np.random.random(1)[0])

    range = max - min
    shifted = rand * range + min
    return shifted

####################################################################################
####################################################################################

class Phonebook:

    #connect to max
    ip = "127.0.0.1"
    port = 8000

    plight_map = {
        0:2,
        1:3,
        2:4,
        3:8,
        4:9,
        5:10,
        6:11,
        7:12
    }
    hlight_map = {
        0:2,
        1:3,
        2:4,
        3:8,
        4:9,
        5:10,
        6:11,
        7:12
    }

    @staticmethod
    def list_to_string(l):
        s = ""
        for i in range(len(l)):
            e = l[i]
            s+= " " + str(e)
    
        return s

    def __init__(self, n, hl=None, pl=None): 

        #hl: Arduino object connected to home lights
        #pl: Arduino object conected to phone lights 

        self.lines = [] #list of all Telephones 
        self.num_lines = n
        self.not_busy = [x for x in range(n)] #list of non-busy Telephones
        self.busy = [] #list of busy Telephones (corresponding to phonelights on)
        self.waiting = [] #list of Telephones waiting to call
        self.sleepy = []
        self.awake = [] #list of Telephones awake (corresponding to homelights on)

        self.hl = hl
        self.pl = pl
        
        self.client = SimpleUDPClient(Phonebook.ip, Phonebook.port)

        for i in range(n):
            self.lines.append(self.Telephone(self, i))

        self.reset()

        return


    def reset(self):

        #turn everything off

        for i in range(self.num_lines): #send 0 to /1-home, /1-phone, etc. 
            flag1 = "/" + str(i) + "-" + "home"
            flag2 = "/" + str(i) + "-" + "phone"
            flag3 = "/" + str(i) + "-" + "msg"
            flag4 = "/" + str(i) + "-" + "wait"
            flag5 = "/" + str(i) + "-" + "dial"
            flag6 = "/" + str(i) + "-" + "receive"
            flag7 = "/" + str(i) + "-" + "talk"
            self.client.send_message(flag1, 0) #home off
            self.client.send_message(flag2, 0) #phone off
            self.client.send_message(flag3, " ") #blank message
            self.client.send_message(flag4, 0) #wait off
            self.client.send_message(flag5, 0) #dial off
            self.client.send_message(flag6, 0) #receive off
            self.client.send_message(flag7, 0) #talk off


            self.not_busy = [x for x in range(self.num_lines)] #list of non-busy Telephones
            self.busy = [] #list of busy Telephones
            self.waiting = [] #list of Telephones waiting to call
            self.sleepy = []
            self.awake = []

            self.lines[i].reset()

            #turn off homelights
            if self.hl is not None:
                for i in range(self.num_lines): #homelights through 2 - 11
                    self.hl.digital[Phonebook.hlight_map[i]].write(False)

            #turn off phonelights 
            if self.pl is not None:
                #phonelights 2-10, 12
                for i in range(self.num_lines):
                    self.pl.digital[Phonebook.plight_map[i]].write(False)
                
            
        return


    def report(self, num, loc, msg): 

        #max flagging stuff 
        flag = "/" + str(num) + "-" + loc
        self.client.send_message(flag, msg)

        #push message to home/phone lights through arduino
        if loc == "home":
            if self.hl is not None:
                if msg == 1:
                    self.hl.digital[Phonebook.hlight_map[num]].write(True)
                elif msg == 0:
                    self.hl.digital[Phonebook.hlight_map[num]].write(False)

        elif loc == "phone":
            if self.pl is not None:
                if msg == 1:
                    self.pl.digital[Phonebook.plight_map[num]].write(True)
                elif msg == 0:
                    self.pl.digital[Phonebook.plight_map[num]].write(False)
        

        return

    def __repr__(self):

        string = ""

        for i in range(self.num_lines):
            string += str(self.lines[i]) + "\n"

        return string

    def __str__(self):

        string = ""

        for i in range(self.num_lines):
            string += str(self.lines[i]) + "\n"

        return string

#####################################################
#####################################################
#####################################################
    
    class Telephone: 

        default_params = {
            "dialtime_low": 8,
            "dialtime_high": 12,
            "hangup_prob": 0.2,
            "pickup_prob": 0.8, 
            "pickuptime_low": 4,
            "pickuptime_high": 9,
            "hanguptime_low": 4,
            "hanguptime_high": 9,
            "talktime_low": 5,
            "talktime_high": 15,
            "norecall": 0.5,
            "recall": 0.5,
            "waittime_low": 3,
            "waittime_high": 7
            
        }

        def __init__(self, phonebook, num, note_range=None, params=None): 

            self.number = num
            self.phonebook = phonebook
            self.busy = False
            self.calling = False
            self.receiving = False
            self.talking = False
            self.waiting = False #waiting to place call
            self.awake = False #awake means home light on 
            self.sleepy = False #waiting to sleep in 2 sec
            
            self.friend = None

            #time in seconds
            self.dial_time = np.inf #how long for caller to wait before hangup 
            self.pickup_time = np.inf #how long for receiver to wait before pickup
            self.hangup_time = np.inf #how long for receiver to wait before hangup
            self.talk_time = np.inf #how long to talk before hangup 
            self.wait_time = np.inf #how long to wait before calling someone else
            
            self.zero_time = None #global time at which to start counting

            self.will_pickup = False #whether or not receiver will pick up 

            self.will_call = False #whether or not phone will call someone else

            self.note_range = note_range #midi notes covered, inclusive

            #convo information
            self.convo = self.Convo(self.phonebook) #instantiate blank 

            #parameters
            if params is None: #defaults
                self.params = Phonebook.Telephone.default_params

            else:
                self.params = params
                
            return
                

        def set_note_range(self, note_range):
            self.note_range = note_range
            return
        

        def reset(self):

            self.busy = False
            self.calling = False
            self.receiving = False
            self.talking = False
            self.waiting = False #waiting to pick up / place call
            self.awake = False #awake means home light on 
            self.sleepy = False #waiting to sleep in 2 sec
            
            self.friend = None

            #time in seconds
            self.dial_time = np.inf #how long for caller to wait before hangup 
            self.pickup_time = np.inf #how long for receiver to wait before pickup
            self.hangup_time = np.inf #how long for receiver to wait before hangup
            self.talk_time = np.inf #how long to talk before hangup 
            self.wait_time = np.inf #how long to wait before calling someone else
            
            self.zero_time = None #global time at which to start counting

            self.will_pickup = False #whether or not receiver will pick up 

            self.will_call = False #whether or not phone will call someone else

            self.convo.clear()

            return
            

        def wakeup(self): #turn homelight on
            self.awake = True
            self.phonebook.report(self.number, "home", 1)
            self.phonebook.awake.append(self.number)
            print(self.number, "waking up")
            return

        def sleep(self): #turn homelight off
            self.awake = False
            self.phonebook.report(self.number, "home", 0)
            self.phonebook.sleepy.remove(self.number)
            
            self.phonebook.awake.remove(self.number)
            #print(self.number, "asleep") 
            return

        def set_dialtime(self):
            self.dial_time = rand_range(self.params["dialtime_low"], self.params["dialtime_high"])
            print(self.number, "dialtime", self.dial_time)
            return

        def choose_pickup(self):

            self.will_pickup = np.random.choice([0, 1], p=[self.params["hangup_prob"], self.params["pickup_prob"]])
            print(self.number, "will pickup?", self.will_pickup)
            if self.will_pickup:
                self.set_pickuptime()
            else:
                self.set_hanguptime()
            return

        def set_pickuptime(self):
            self.pickup_time = rand_range(self.params["pickuptime_low"], self.params["pickuptime_high"])
            print(self.number, "pickuptime", self.pickup_time)
            return

        def set_hanguptime(self):
            self.hangup_time = rand_range(self.params["hanguptime_low"], self.params["hanguptime_high"])
            print(self.number, "hanguptime", self.hangup_time)
            return

        def set_talktime(self, ttime=None):
            if ttime is None:
                self.talk_time = np.random.randint(self.params["talktime_low"], self.params["talktime_high"])
            else:
                self.talk_time = ttime
            print(self.number, "talktime", self.talk_time)
            return

        def set_willcall(self, global_time):
            self.will_call = np.random.choice([0, 1], p=[self.params["norecall"], self.params["recall"]])
            print(self.number, "will recall?", self.will_call)
            if self.will_call:
                self.set_waittime(global_time)
            else:
                if self.awake:
                    self.sleepy = True
                    self.phonebook.sleepy.append(self.number)
                self.zero_time = global_time
            return

        def set_waittime(self, global_time):
            
            self.wait_time = rand_range(self.params["waittime_low"], self.params["waittime_high"])
            self.zero_time = global_time
            self.waiting = True
            self.sleepy = False
            if self.number in self.phonebook.sleepy:
                self.phonebook.sleepy.remove(self.number) #
            self.phonebook.waiting.append(self.number)

            self.phonebook.report(self.number, "wait", 1)
            self.phonebook.report(self.number, "msg", "waiting")
            print(self.number, "waittime", self.wait_time, "zero time", self.zero_time)
            return
        
    
        def call(self, num, global_dt):

            if not self.busy:

                print(str(self.number), "calling", str(num)) 
    
                #flag self + define time
                self.calling = True
                self.busy = True
                self.waiting = False #no longer waiting!
                self.wait_time = np.inf
                if self.number in self.phonebook.waiting:
                    self.phonebook.waiting.remove(self.number)
                self.phonebook.report(self.number, "wait", 0)
                self.friend = num
                self.set_dialtime()
                self.zero_time = global_dt
    
                #flag friend 
                self.phonebook.lines[num].receiving = True
                self.phonebook.lines[num].busy = True
                self.phonebook.lines[num].waiting = False #don't wait to call if ur being called!
                self.phonebook.lines[num].wait_time = np.inf
                if num in self.phonebook.waiting:
                    self.phonebook.waiting.remove(num)
                self.phonebook.lines[num].sleepy = False #can't be sleepy if ur being called
                if num in self.phonebook.sleepy:
                    self.phonebook.sleepy.remove(num)
                self.phonebook.report(num, "wait", 0)
                self.phonebook.lines[num].friend = self.number
                self.phonebook.lines[num].choose_pickup()
                self.phonebook.lines[num].zero_time = global_dt
    
                #flag in phonebook
                self.phonebook.not_busy.remove(num)
                self.phonebook.not_busy.remove(self.number)
                self.phonebook.busy.append(num)
                self.phonebook.busy.append(self.number)
    
                #report to client
                self.phonebook.report(self.number, "pickup", 1)
                self.phonebook.report(self.number, "phone", 1)
                self.phonebook.report(self.number, "dial", 1)
                self.phonebook.report(self.number, "msg", "calling " + str(self.friend))
                self.phonebook.report(self.friend, "phone", 1)
                self.phonebook.report(self.friend, "receive", 1)
                self.phonebook.report(self.friend, "msg", "receiving " + str(self.number))
            
            return

        def pickup(self, global_time):

            if self.receiving:

                print(str(self.number), "picked up call from ", str(self.friend))

                #set talk time
                self.set_talktime()
                self.phonebook.lines[self.friend].set_talktime(self.talk_time)

                #generate conversation
                self.generate(self.talk_time, self.phonebook, self.friend)
                
                #flag self 
                self.receiving = False
                self.talking = True
                self.zero_time = global_time

                #flag friend
                self.phonebook.lines[self.friend].calling = False
                self.phonebook.lines[self.friend].talking = True
                self.phonebook.lines[self.friend].zero_time = global_time

                #report to client (max flags and lights)
                self.phonebook.report(self.number, "pickup", 1)
                self.phonebook.report(self.number, "receive", 0)
                self.phonebook.report(self.number, "talk", 1)
                self.phonebook.report(self.number, "msg", "talking " + str(self.friend)) 
                self.phonebook.report(self.friend, "dial", 0)
                self.phonebook.report(self.friend, "talk", 1)
                self.phonebook.report(self.friend, "msg", "talking " + str(self.number))

                #start audio for convo
                print("receiver", self.convo.receiver.number, self.convo.caller.number)
                print("caller", self.phonebook.lines[self.friend].convo.receiver.number, self.phonebook.lines[self.friend].convo.caller.number) 
                self.convo.report()
                self.convo.start()

            else:

                if not self.busy:
                    print(str(self.number), "not called, nothing to pickup") 
                else:
                    print("ERROR:", str(self.number), "tried to pick up when busy")

            return 


        def hangup(self, global_time):

            if self.calling:

                #no response
                print(str(self.number), "hanging up on", str(self.friend), ", no response")

                #report to client
                self.phonebook.report(self.number, "msg", " ")
                self.phonebook.report(self.friend, "msg", " ")
                self.phonebook.report(self.number, "phone", 0)
                self.phonebook.report(self.friend, "phone", 0)
                self.phonebook.report(self.number, "dial", 0)
                self.phonebook.report(self.friend, "receive", 0)
                self.phonebook.report(self.number, "hangup", 1)

                #flag friend
                self.phonebook.lines[self.friend].receiving = False
                self.phonebook.lines[self.friend].busy = False
                self.phonebook.lines[self.friend].friend = None
                self.phonebook.lines[self.friend].set_willcall(global_time)

                #flag phonebook
                self.phonebook.not_busy.append(self.friend)
                self.phonebook.not_busy.append(self.number)
                self.phonebook.busy.remove(self.friend)
                self.phonebook.busy.remove(self.number)

                #flag self 
                self.calling = False
                self.busy = False
                self.friend = None
                self.set_willcall(global_time)


            elif self.receiving:

                #don't want to pick up 
                print(str(self.number), "hanging up on", str(self.friend), ", don't want to talk")

                #report to client
                self.phonebook.report(self.number, "msg", " ")
                self.phonebook.report(self.friend, "msg", " ")
                self.phonebook.report(self.number, "phone", 0)
                self.phonebook.report(self.friend, "phone", 0)
                self.phonebook.report(self.number, "receive", 0)
                self.phonebook.report(self.friend, "dial", 0)
                self.phonebook.report(self.number, "hangup", 1)
                
                #flag friend
                self.phonebook.lines[self.friend].calling = False
                self.phonebook.lines[self.friend].busy = False
                self.phonebook.lines[self.friend].friend = None
                self.phonebook.lines[self.friend].set_willcall(global_time)

                #flag phonebook
                self.phonebook.not_busy.append(self.friend)
                self.phonebook.not_busy.append(self.number)
                self.phonebook.busy.remove(self.friend)
                self.phonebook.busy.remove(self.number)

                #flag self 
                self.receiving = False
                self.busy = False
                self.friend = None
                self.set_willcall(global_time)

            elif self.talking:

                #done talking
                print(str(self.number), "hanging up on", str(self.friend), ", done talking")

                #report to client
                self.phonebook.report(self.number, "msg", " ")
                self.phonebook.report(self.friend, "msg", " ")
                self.phonebook.report(self.number, "phone", 0)
                self.phonebook.report(self.friend, "phone", 0)
                self.phonebook.report(self.number, "talk", 0)
                self.phonebook.report(self.friend, "talk", 0)
                self.phonebook.report(self.number, "hangup", 1)
                self.phonebook.report(self.friend, "hangup", 1)

                #clear convos
                self.convo.clear()
                self.phonebook.lines[self.friend].convo.clear()

                #flag friend
                self.phonebook.lines[self.friend].talking = False
                self.phonebook.lines[self.friend].busy = False
                self.phonebook.lines[self.friend].friend = None 
                self.phonebook.lines[self.friend].set_willcall(global_time)

                #flag phonebook
                self.phonebook.not_busy.append(self.friend)
                self.phonebook.not_busy.append(self.number)
                self.phonebook.busy.remove(self.friend)
                self.phonebook.busy.remove(self.number)

                #flag self 
                self.talking = False
                self.busy = False
                self.friend = None
                self.set_willcall(global_time)

            else:

                print("ERROR:", str(self.number), "tried to hang up without calling")

            return



            

        def __repr__(self):
            
            string = "\nPhone number: " + str(self.number)

            if self.busy:
                string += ", BUSY"

            if self.calling:
                string += ", calling " + str(self.friend) + ", dialtime " + str(self.dial_time) + ", talktime " + str(self.talk_time)

            if self.receiving:
                string += ", receiving " + str(self.friend)
                if self.will_pickup:
                    string += ", pickuptime " + str(self.pickup_time) + ", talktime " + str(self.talk_time)
                else:
                    string += ", hanguptime " + str(self.hangup_time)

            if self.talking:
                string += ", talking to " + str(self.friend) + ", talktime " + str(self.talk_time)
            
            return string

        def __str__(self):

            string = "\nPhone number: " + str(self.number)

            if self.busy:
                string += ", BUSY"

            if self.calling:
                string += ", calling " + str(self.friend) + ", dialtime " + str(self.dial_time) + ", talktime " + str(self.talk_time)

            if self.receiving:
                string += ", receiving " + str(self.friend)
                if self.will_pickup:
                    string += ", pickuptime " + str(self.pickup_time) + ", talktime " + str(self.talk_time)
                else:
                    string += ", hanguptime " + str(self.hangup_time)

            if self.talking:
                string += ", talking to " + str(self.friend) + ", talktime " + str(self.talk_time)
            
            return string


        def generate(self, time, pb, t2_num):

            t2 = pb.lines[t2_num]

            print("generating", self.number, t2.number)

            self.convo = Phonebook.Telephone.Convo(pb, receiver=self, caller=t2)
            print(self.convo.receiver.number)
            
            #generate convo within timeframe
            #attach to rec and call telephone objs 
            
            convo_info = Phonebook.Telephone.Convo.new_info()

            #first, set hellos and goodbyes 
            hello_info, hello_time = Phonebook.Telephone.Convo.hello_goodbye(self, t2, type="hello")
            goodbye_info, goodbye_time = Phonebook.Telephone.Convo.hello_goodbye(self, t2, type="goodbye") 

            #time left for talking 
            talk_time = time*1000 - hello_time - goodbye_time - 100
            
            turn_times, pause_times = Phonebook.Telephone.Convo.get_turn_times(talk_time) #list of turn times and turn pauses

            talker = "rec" #always start with receiver talking
            turn_infos = []
            
            for i in range(len(pause_times)):
                turn_length = turn_times[i]
                turn_info = Phonebook.Telephone.Convo.one_turn(talker, turn_length, center=None)
                
                pause_length = pause_times[i]
                Phonebook.Telephone.Convo.add_pause(turn_info, length=pause_length)
                
                turn_infos.append(turn_info)

                #then switch talker
                if talker == "rec":
                    talker = "call"
                elif talker == "call":
                    talker = "rec" 

            if len(pause_times) == 0:
                i = -1
            #then, do last turn
            turn_length = turn_times[i+1]
            turn_info = Phonebook.Telephone.Convo.one_turn(talker, turn_length, center=None)
            Phonebook.Telephone.Convo.add_pause(turn_info, length=100)
            turn_infos.append(turn_info)
            

            if talker == "rec":
                talker = "call"
            elif talker == "call":
                talker = "rec"

            #consolidate turn_infos
            turn_info_consolidated = Phonebook.Telephone.Convo.consolidate_info(turn_infos)

            #consolidate all info from hello_info, goodbye_info, turn_infos, turn_pauses 
            convo_info = Phonebook.Telephone.Convo.consolidate_info([hello_info, turn_info_consolidated, goodbye_info])

            #shift notes by noterange 
            convo_info["notes_rec"] = [x + self.note_range[0] for x in convo_info["notes_rec"]]
            convo_info["notes_call"] = [x + t2.note_range[0] for x in convo_info["notes_call"]]

            #turn lists into strings 
            durs = Phonebook.list_to_string(convo_info["durs"])
            notes_rec = Phonebook.list_to_string(convo_info["notes_rec"])
            notes_call = Phonebook.list_to_string(convo_info["notes_call"])
            envs_rec = Phonebook.list_to_string(convo_info["envs_rec"])
            envs_call = Phonebook.list_to_string(convo_info["envs_call"])

            
            #put info into convo of t1
            #copy into t2

            #self.convo.receiver = self
            #self.convo.caller = t2

            self.convo.durations = durs
            self.convo.notes_rec = notes_rec
            self.convo.envs_rec = envs_rec
            self.convo.notes_call = notes_call
            self.convo.envs_call = envs_call
            
            t2.convo = self.convo

            return

    #####################################################
    #####################################################
    #####################################################

        class Convo:

            @staticmethod
            def add_pause(inf, length=None, min=300, max=501):

                if length == "rand":
                    length = np.random.randint(min, max)

                if len(inf["durs"]) == 0:
                    Phonebook.Telephone.Convo.add_to_info(inf, length, -2, -2, 0, 0)
                else:
                    Phonebook.Telephone.Convo.add_to_info(inf, length, inf["notes_rec"][-1], inf["notes_call"][-1], 0, 0)

                return

            @staticmethod
            def new_info():

                inf = {
                    "durs": [],
                    "notes_rec": [],
                    "notes_call": [],
                    "envs_rec": [],
                    "envs_call": []
                }

                return inf

            @staticmethod
            def consolidate_info(inf_list):

                cons_inf = inf_list[0]

                for i in range(1, len(inf_list)):
                    inf = inf_list[i]
                    cons_inf["durs"] += inf["durs"]
                    cons_inf["notes_rec"] += inf["notes_rec"]
                    cons_inf["notes_call"] += inf["notes_call"]
                    cons_inf["envs_rec"] += inf["envs_rec"]
                    cons_inf["envs_call"] += inf["envs_call"]

                return cons_inf
                    
    
            def __init__(self, phonebook, receiver=None, caller=None):

                #receiver and caller are Telephone objects 
                
                self.durations = " zlclear"
                self.notes_rec = " zlclear"
                self.envs_rec = " zlclear"
                self.notes_call = " zlclear"
                self.envs_call = " zlclear"

                self.pb = phonebook
                self.receiver = receiver
                self.caller = caller

                return

            @staticmethod
            def hello_goodbye(t1, t2, type="hello"):

                info = Phonebook.Telephone.Convo.new_info()

                #first, pause
                if type == "hello":
                    Phonebook.Telephone.Convo.add_pause(info, length=500) 
                else:
                    Phonebook.Telephone.Convo.add_pause(info, length=100) 
                #then first greeting
                Phonebook.Telephone.Convo.add_greeting(info, 'rec', type=type, word="long")
                #then pause
                Phonebook.Telephone.Convo.add_pause(info, length=300)
                #then second hello
                Phonebook.Telephone.Convo.add_greeting(info, 'call', type=type, word="rand")
                #then pause 
                Phonebook.Telephone.Convo.add_pause(info, length=300) #change so goodbye ends on 300/100 pause...urgh

                #add final 0 to envs_call for goodbye
                if type == "goodbye":
                    info["envs_call"].append(0)

                return info, sum(info["durs"])

            @staticmethod
            def add_greeting(inf, speaker, type="hello", word="rand"):

                if word == "rand":
                    word = np.random.choice(["long", "short"], p=[0.5, 0.5])

                
                if word == "long":
                    if type == "hello":
                        #pick two random notes
                        first = np.random.choice(8) #for hello, at least have buffer of one above
                        sec_diff = np.random.choice(np.arange(1,4))
                        sec = first + sec_diff
                        if sec > 8 or sec < 0:
                            sec = first + 1

                    elif type == "goodbye":
                        first = np.random.choice(np.arange(1, 9)) #for goodbye, at least have buffer of one below
                        sec_diff = np.random.choice(np.arange(-3, 0))
                        sec = first + sec_diff
                        if sec > 8 or sec < 0:
                            sec = first - 1

                    #pick two durations
                    first_dur = np.random.randint(100, 151)
                    sec_dur = np.random.randint(50, 71)

                    #add to info
                    if speaker == "rec":
                        Phonebook.Telephone.Convo.add_to_info(inf, first_dur, first, -1, 1, 0)
                        Phonebook.Telephone.Convo.add_to_info(inf, sec_dur, sec, -1, 1, 0)
                    elif speaker == "call":
                        Phonebook.Telephone.Convo.add_to_info(inf, first_dur, -1, first, 0, 1)
                        Phonebook.Telephone.Convo.add_to_info(inf, sec_dur, -1, sec, 0, 1)
                    
                elif word == "short":
                    #pick one random note, one random dur
                    note = np.random.choice(9)
                    dur = np.random.randint(50, 71)

                    #add to info
                    if speaker == "rec":
                        Phonebook.Telephone.Convo.add_to_info(inf, dur, note, -1, 1, 0) 
                    elif speaker == "call":
                        Phonebook.Telephone.Convo.add_to_info(inf, dur, -1, note, 0, 1)
                    
                return

            @staticmethod
            def get_turn_times(talk_time):
            
                #turns can be between 300 - 1000 ms long
                #pauses between 300-400 long
            
                turn_times = []
                pause_times = []
                time_left = talk_time
            
                #make first turn first....
                first_turn_time = np.random.randint(600, 801)
                turn_times.append(first_turn_time)
                time_left = talk_time - first_turn_time
            
                #then, keep adding pauses and turns until there's not enough time
                while time_left > 0:
                    pause_time = np.random.randint(70, 101)
                    turn_time = np.random.randint(400, 1501)
            
                    turn_times.append(turn_time)
                    pause_times.append(pause_time)
                    
                    time_left -= pause_time
                    time_left -= turn_time
                    #print(turn_time, pause_time, time_left)
            
                #take care of the overlap...
                turn_times.remove(turn_times[-1])
                pause_times.remove(pause_times[-1])
            
                turn_times[-1] += talk_time - (sum(turn_times) + sum(pause_times)) #can play with this... maybe spread amongst other turns
            
                #shuffle for shuffle's sake
                random.shuffle(turn_times)
                random.shuffle(pause_times)

                #print(sum(turn_times) + sum(pause_times), talk_time)
                return turn_times, pause_times

            @staticmethod
            def one_turn(talker, time, center=None): 

                if talker == "rec":
                    listener = "call"
                elif talker == "call":
                    listener = "rec"

                turn_info = Phonebook.Telephone.Convo.new_info()

                if center == None:
                    center = np.random.randint(9)

                #word lengths vary between 50-70ms
                time_left = time

                durs = []
                notes = []
                envs = []

                curr_note = center
                num_repeats = 0

                while time_left > 0:
                    word_length = np.random.randint(80, 121)
                    durs.append(word_length)

                    #figure out if we wanna move from the previous note
                    prob_move = num_repeats * 0.1
                    prob_not_move = 1 - prob_move
                    move = np.random.choice(["not", "move"], p=[prob_not_move, prob_move])

                    if move == "move":
                        # diff = (center - curr_note) / np.abs(center - curr_note)
                        p_down = curr_note/8
                        p_up = 1 - p_down
                        diff = np.random.choice([-1, 1], p=[p_down, p_up])
                        curr_note += diff
                        num_repeats = 0

                    elif move == "not":
                        num_repeats += 1
                    
                    notes.append(curr_note)
                    envs.append(1)

                    pause_length = np.random.randint(50, 71)
                    durs.append(pause_length)
                    notes.append(curr_note)
                    envs.append(0)
                    time_left -= word_length
                    time_left -= pause_length

                #consolidate last word, remove last pause-word-pause
                durs.remove(durs[-1])
                notes.remove(notes[-1])
                envs.remove(envs[-1])

                durs.remove(durs[-1])
                notes.remove(notes[-1])
                envs.remove(envs[-1])

                durs.remove(durs[-1])
                notes.remove(notes[-1])
                envs.remove(envs[-1])

                durs[-1] += time - sum(durs)

                turn_info["durs"] = durs
                turn_info["notes_" + talker] = notes
                turn_info["notes_" + listener] = [0]*len(durs)
                turn_info["envs_" + talker] = envs
                turn_info["envs_" + listener] = [0]*len(durs)

                return turn_info

            @staticmethod
            def add_to_info(inf, dur, note_rec, note_call, envs_rec, envs_call):
                
                inf["durs"].append(dur)
                inf["notes_rec"].append(note_rec)
                inf["notes_call"].append(note_call)
                inf["envs_rec"].append(envs_rec)
                inf["envs_call"].append(envs_call)

                return
            
            def clear(self):

                
                self.durations = " zlclear"
                self.notes_rec = " zlclear"
                self.envs_rec = " zlclear"
                self.notes_call = " zlclear"
                self.envs_call = " zlclear"

                if self.receiver is not None and self.caller is not None:
                    print("clearing", self.receiver.number, self.caller.number)
                    self.report()

                self.receiver = None
                self.caller = None

                return

            def report(self):
                #sends to both receiver and caller
                self.pb.report(self.receiver.number, "convo", "/durations" + self.durations)
                self.pb.report(self.receiver.number, "convo", "/notes" + self.notes_rec)
                self.pb.report(self.receiver.number, "convo", "/envelope" + self.envs_rec)

                self.pb.report(self.caller.number, "convo", "/durations" + self.durations)
                self.pb.report(self.caller.number, "convo", "/notes" + self.notes_call)
                self.pb.report(self.caller.number, "convo", "/envelope" + self.envs_call)

                return

            def start(self):
                #starts both receiver and caller
                self.pb.report(self.receiver.number, "convo", "/start")
                self.pb.report(self.caller.number, "convo", "/start")

                return

            def stop(self):
                #stops both receiver and caller
                self.pb.report(self.reciever.number, "convo", "/stop")
                self.pb.report(self.caller.number, "convo", "/stop")

                return

###############################################################

def main_telephone(phonebook, starters, dt, num_new_starters, num_lines):

    phones = phonebook.lines
    curr_time = 0
    downtime = 0
    phonebook.reset()

    #first, add starting phones to waiting list 
    for i in range(len(starters)):
        phone = phones[starters[i]]
        phone.set_waittime(curr_time)

    #then, do loop
    t=0
    done = False
    while not done:

        if t%10 == 0:
            print("t=", round(curr_time, 0))
           # print("downtime=", downtime)
            # print("busy lines", phonebook.busy)
            # print("not busy", phonebook.not_busy)
            # print("waiting", phonebook.waiting)
            # print("awake", phonebook.awake)    
    
        #check busy phones to take action
        busy_phones = []
        for i in range(len(phonebook.busy)):
    
            phone = phones[phonebook.busy[i]]
            busy_phones.append(phone)
    
        for phone in busy_phones:
            phonetime = curr_time - phone.zero_time
    
            if phone.calling and phonetime > phone.dial_time:
                phone.hangup(curr_time)
                
    
            elif phone.receiving and not phone.will_pickup and not phone.awake and phonetime > phone.hangup_time - 2:
                phone.wakeup()
                
            elif phone.receiving and not phone.will_pickup and phone.awake and phonetime > phone.hangup_time:
                phone.hangup(curr_time)
    
    
            elif phone.receiving and phone.will_pickup and not phone.awake and phonetime > phone.pickup_time - 2:
                phone.wakeup()
    
            elif phone.receiving and phone.will_pickup and phone.awake and phonetime > phone.pickup_time:
                phone.pickup(curr_time)
    
            elif phone.talking and phonetime > phone.talk_time: #whichever has shorter talktime will win basically
                phone.hangup(curr_time)
    
        waiting_phones = []
        for i in range(len(phonebook.waiting)):
            phone = phones[phonebook.waiting[i]]
            waiting_phones.append(phone)
    
        for phone in waiting_phones:
            phonetime = curr_time - phone.zero_time
    
            if phone.waiting and not phone.awake and phonetime > phone.wait_time - 2: 
                phone.wakeup()
    
            if phone.waiting and phonetime > phone.wait_time:
                not_busy = [x for x in phonebook.not_busy]
                if phone.number in not_busy:
                    not_busy.remove(phone.number)
    
                if len(not_busy) != 0:
                    phone.call(np.random.choice(not_busy), curr_time)
                else:
                    phone.set_waittime(curr_time)
    
        sleepy_phones = []
        
        for i in range(len(phonebook.sleepy)):
            phone = phones[phonebook.sleepy[i]]
            sleepy_phones.append(phone)
    
        for phone in sleepy_phones:
            phonetime = curr_time - phone.zero_time
    
            if phone.sleepy and phonetime > 2:
                print(phone.number, " going to sleep")
                phone.sleep()
    
        
        curr_time += dt
        time.sleep(dt)
        t += 1
    
    
        
        #check for nothing happening to reset 
        if len(phonebook.awake)==0 and len(phonebook.waiting)==0:
            if downtime == 0:
                print("ENDING")
            downtime += 1
    
        if downtime > 100: #reset
    
            print()
            print("RESTARTING")
    
            #pick 1-4 new starters
            if num_new_starters == 1:
                num_starters = 1
            else:
                num_starters = np.random.randint(1, num_new_starters + 1)
            starters = np.random.choice(num_lines, size=num_starters, replace=False)
    
            #reset timers 
            curr_time = 0
            downtime = 0
            t = 0
    
            #reset phonebook
            phonebook.reset()
    
            #set wait times for starters 
            for i in range(len(starters)):
                phone = phones[starters[i]]
                phone.set_waittime(curr_time)
    
            
    
                
    
        #CHECK HERE for killswitch from arduino...
        ##########################################
        #if killswitch then done = True

    return