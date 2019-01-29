#!/usr/bin/env python

import sys
import simpy
import math
import random
from pathlib import Path
                
class Train(object,):
    '''Implements the simulation, all other processes are subprocesses of this class'''
    def __init__(self,env, poisson_time, total_hours, mode):
        self.env = env
        self.train_list = [[0,0,train_unloading_time()]]
        self.idle_time = 0
        self.hog_outs = 0
        self.event_list = []
        self.train = 0
        self.action = env.process(self.run())
        self.Q_line = 0
        self.crew = [[0,crew_work_time()]]
        self.crew_num = 0
        self.time_in = []
        self.hogged_out_perc = []
        self.poisson_time = poisson_time
        self.total_hours = total_hours
        self.conf_time_in = []
        self.mode = mode
        
    def run(self):            
        print("CURRENT MODE",self.mode)
        if self.mode == 0:
            schedule = open("schedule.txt","r")
            train_nums = []
            for trains in schedule:
                train_nums.append(trains)
            
            train_config = []
            
            for lines in train_nums:
                train_config.append(lines.strip("\n").split(" "))
                
            arr_times = []
            unloading_times = []
            working_times = []
            
            final_config_list = []
            for values in train_config:
                for sub_values in values:
                    final_config_list.append(float(sub_values))
                    
            index = 0
            for arrivals in final_config_list:
                if index <= len(final_config_list) - 1:
                    arr_times.append(final_config_list[index])
                index +=3
                
            index = 1
            for unloadings in final_config_list:
                if index <= len(final_config_list) - 1:
                    unloading_times.append(final_config_list[index])
                index +=3
                
            index = 2
            for working_hours in final_config_list:
                if index <= len(final_config_list) - 1:
                    working_times.append(final_config_list[index])
                index +=3
    
            schedule.close()  
            LIST_OF_CURRENT_AND_NEXT_TRAIN = []
            LIST_OF_CURRENT_AND_NEXT_TRAIN.append([self.train, round(arr_times[0],2), round(unloading_times[0],2)])
            LIST_OF_CURRENT_AND_NEXT_TRAIN.append([self.train + 1, round(arr_times[1],2), round(unloading_times[1],2)])
        
        elif self.mode == 1:
            arr_times = []
            unloading_times = []
            working_times = []
            LIST_OF_CURRENT_AND_NEXT_TRAIN = self.append_next_train(self.train_list, self.train)
            
        yield env.timeout(0)   
        while env.now < self.total_hours:   
            try:
                yield env.process(self.EVENT_CHECKER(env,LIST_OF_CURRENT_AND_NEXT_TRAIN, self.Q_line, self.crew, working_times))
                self.train +=1
                
                if self.mode == 0:
                    LIST_OF_CURRENT_AND_NEXT_TRAIN.pop(0)         
                    LIST_OF_CURRENT_AND_NEXT_TRAIN.append([self.train + 1, round(arr_times[self.train + 1],2), round(unloading_times[self.train + 1],2)])
                    
                elif self.mode == 1:
                    LIST_OF_CURRENT_AND_NEXT_TRAIN.pop(0)         
                    LIST_OF_CURRENT_AND_NEXT_TRAIN = self.append_next_train(LIST_OF_CURRENT_AND_NEXT_TRAIN, self.train)   

            except simpy.Interrupt:    
                pass
                
        self.conf_time_in.append(self.calculate_avg_time_in(LIST_OF_CURRENT_AND_NEXT_TRAIN))
            
        print("\n")
        print("Statistics")
        print("----------")
        print("Total number of trains served: ", LIST_OF_CURRENT_AND_NEXT_TRAIN[1][0])
        print("Average time-in-system per train: {}h".format(self.calculate_avg_time_in(LIST_OF_CURRENT_AND_NEXT_TRAIN)))
        print("Maximum time-in-system per train: {}h".format(self.max_time()))
        print("Dock idle percentage {}%".format(self.calculate_idle_percentage()))
        print("Dock busy percentage: {}%".format(self.calculate_busy_percentage()))
        print("Dock hogged-out percentage: {}%".format(self.calculate_hogged_out_percentage()))
        print("Average time-in queue over trains: {}h".format(self.Q_line))
        print("Maximum number of trains in queue: ",self.Q_line)
        print("Average idle time per train: {}h ".format(self.idle_time,2))
        
        mean = self.mean(self.conf_time_in)
        stdev = self.stddev(self.conf_time_in, 1)
        conf_int = self.calculate_conf_interval(self.conf_time_in, mean, stdev)
        
        print("a) The 99% Confidence interval for the mean time-in system is: +{} or -{}".format(conf_int, conf_int))
    
    def EVENT_CHECKER(self, env,current_next_train, Q, current_crew, working_times): 
        '''Checks for Events to perform and yields the updated time of the Simulation''' 
        
        if self.mode == 0:
            current_crew.append([current_next_train[0][0], working_times[current_next_train[0][0]]])
            
        elif self.mode == 1:
            current_crew = self.create_crew(current_next_train, Q, current_crew) 
        
        if current_next_train[0][0] == 0:
            print("Time {}: train {} arrival for {}h of unloading,".format(env.now,current_next_train[0][0],current_next_train[0][2]))
            print("         crew {} with {}h before hogout (Q={})".format(current_crew[0][0],current_crew[0][1],0))
            
            wait_time = 0
            
        elif current_next_train[0][0] >= 1 and self.Q_line == 0:
            print("Time {}: train {} arrival for {}h of unloading,".format(current_next_train[0][1], current_next_train[0][0],current_next_train[0][2]))
            print("         crew {} with {}h before hogout (Q={})".format(current_crew[0][0],current_crew[0][1],0))

            wait_time = env.now - current_next_train[0][1]
        
        elif current_next_train[0][0] >= 1 and self.Q_line == 1:
            wait_time = env.now - current_next_train[0][1]
            print("Time {}: train {} entering dock for {}h of unloading,".format(current_next_train[0][1] + wait_time , current_next_train[0][0],current_next_train[0][2]))
            print("         crew {} with {}h before hogout (Q={})".format(current_crew[0][0],round(current_crew[0][1],2), 0))
            
            if self.Q_line == 1:
                self.Q_line = 0
                
        elif current_next_train[0][0] >= 1 and self.Q_line >1:
            wait_time = env.now - current_next_train[0][1]
       
        if wait_time <= 0:
            crew_time_at_dock = current_crew[0][1]
            
        elif wait_time > 0:
            crew_time_at_dock = calculate_crew_time_at_dock(current_crew, wait_time)

    
        if crew_time_at_dock >= 0:
            G_decision = round(self.GATE_GUARDIAN(env, current_next_train, current_crew, crew_time_at_dock),2)

            decision = self.finish_time_vs_next_arrival_time(env, current_next_train, current_crew, G_decision, Q)
            
            if decision == "Next":
                update_clock_time = G_decision - env.now            
    
                if update_clock_time >= 0: 
                    self.time_in.append(round(update_clock_time,2))
                    yield env.timeout(update_clock_time)
                    
                else:
                    self.time_in.append(round(update_clock_time,2))
                    yield env.timeout(-1 * update_clock_time)
                    
            elif decision == "Wait":
                current_crew[1][1] = current_crew[1][1] - round(G_decision - current_next_train[1][1],2)

                self.Q_line += 1
                
                departure(env, G_decision, current_next_train, Q + 1)

                update_clock_time = G_decision - env.now    

                if update_clock_time >= 0: 
                    self.time_in.append(round(update_clock_time,2))
                    yield env.timeout(update_clock_time)
                
                else:
                    self.time_in.append(round(update_clock_time,2))
                    yield env.timeout(-1 * update_clock_time)

                
        elif crew_time_at_dock < 0:
            replacement_crew_time_to_arrive = replacement_crew_arrival_time()
            
            calculated_rep_crew_time_to_arrive = replacement_crew_time_to_arrive + round(crew_time_at_dock,2)

            self.idle_time += calculated_rep_crew_time_to_arrive
            self.crew_num +=1
            self.hog_outs += 1
            self.hogged_out_perc.append(calculated_rep_crew_time_to_arrive)
            

    def calculate_conf_interval(self, time_in, mean, stdev):
        t = 2.626
        conf_int= mean - (t*(stdev/math.sqrt(100)))
        
        return conf_int
        
    def mean(self,data):
        """Return the sample arithmetic mean of data."""
        n = len(data)
        if n < 1:
            raise ValueError('mean requires at least one data point')
        return sum(data)/n
    
    def _ss(self,data):
        """Return sum of square deviations of sequence data."""
        c = self.mean(data)
        ss = sum((x-c)**2 for x in data)
        return ss
    
    def stddev(self, data, ddof=0):
        """Calculates the population standard deviation
        by default; specify ddof=1 to compute the sample
        standard deviation."""
        n = len(data)
        if n < 2:
            raise ValueError('variance requires at least two data points')
        ss = self._ss(data)
        pvar = ss/(n-ddof)
        return pvar**0.5

    
    def finish_time_vs_next_arrival_time(self, env, current_next_train, current_crew,G_decision, Q):
        '''Calculates the finish time of the current train in dock vs the arrival time of the next train'''
        if  G_decision > current_next_train[1][1]:
            Q += 1
            print("Time {}: train {} arrival for {}h of unloading,".format(current_next_train[1][1], current_next_train[1][0],current_next_train[1][2]))
            print("         crew {} with {}h before hogout (Q={})".format(current_crew[1][0],current_crew[1][1],Q))
            
            return "Wait"
    
        elif G_decision < current_next_train[1][1]:
            departure(env, G_decision, current_next_train, Q)
            return "Next"
    
    def GATE_GUARDIAN(self, env,current_next_train, current_crew, crew_time_at_dock):
        '''CHECKS IF CREW_TIME_AT_DOCK IS THE SAME AS CURRENT CREW WORK TIME'''
        '''if CWT for crew == crew working time about to enter the dock(there was no waiting)'''
        
        if current_crew[0][1] == crew_time_at_dock:
            print("Time {}: train {} entering dock for {}h of unloading,".format(current_next_train[0][1], current_next_train[0][0],current_next_train[0][2]))
            print("         crew {} with {}h before hogout (Q={})".format(current_crew[0][0],current_crew[0][1],0))
            ideal_finish_time = calculate_dock_finish_time(env, current_next_train)
            return ideal_finish_time
        
        ideal_finish_time = calculate_dock_finish_time(env, current_next_train)
        return ideal_finish_time

    def create_crew(self, current_next_train, Q, crew_list):
        '''Method to create a crew'''
        
        self.crew_num +=1
        if int(current_next_train[0][0]) == 0: 
            crew_list.append([current_next_train[1][0], crew_work_time()])
            return crew_list  
    
        elif int(current_next_train[0][0]) >= 1:
            crew_list.pop(0)
            crew_list.append([self.crew_num, crew_work_time()])
            return crew_list 

    def train_arrival_time(self):
        '''Calculates the poisson arrival rate'''
        return round(-math.log(1.0 - random.random()) / (1/self.poisson_time),2)
    
    def append_next_train(self, train_list, train):
        '''Appends the next train'''
        train_list.append([train + 1, round(train_list[0][1] + self.train_arrival_time(),2), round(train_unloading_time(),2)])
        return train_list

    def calculate_hogged_out_percentage(self):
        total_sum = 0
        for times in self.hogged_out_perc:
            total_sum+=times
            
        return round(total_sum,2)
    
    def calculate_busy_percentage(self):
        return(round(100 - self.idle_time,2))
        
    def calculate_idle_percentage(self):
        return(round(self.idle_time,2))
        
    def max_time(self):
        max_num = max(self.time_in)
        return max_num
    
    def calculate_avg_time_in(self,current_next_train):
        total_sum = 0
        for times in self.time_in:
            total_sum+=times
        return round(total_sum/current_next_train[0][0],2)
    
def calculate_dock_finish_time(env, current_next_train):
    '''Returns the dock finish time'''
    return current_next_train[0][1] + current_next_train[0][2]
    
def calculate_crew_time_at_dock(current_crew, wait_time):
    '''Work time - Finish_time'''
    return current_crew[0][1] - wait_time

def arrival(env, current_next_train, current_crew, Q):
    '''Prints arrivals'''
    print("Time {}: train {} arrival for {}h of unloading,".format(current_next_train[0][1], current_next_train[0][0], current_next_train[0][2]))
    print("         crew {} with {}h before hogout (Q={})".format(current_crew[0][0], current_crew[0][1], Q))
    
def departure(env, G_decision, current_next_train, Q):
    '''Prints departures'''
    print("Time {}: train {} departing (Q={})".format(G_decision, current_next_train[0][0],Q))
        
def current_crew_number(current_next_train):
    '''returns the current crew number'''
    return current_next_train[1][0]
    
def train_unloading_time():
    '''Returns a random unloading time for train'''
    return round(random.uniform(3.5, 4.5),2)

def crew_work_time():
    '''Returns a random work time for crew'''
    return round(random.uniform(6.0, 11.0),2)

def replacement_crew_arrival_time():
    '''Returns a random replacement crew arrival time'''
    return round(random.uniform(2.5, 3.5),2)

def replacement_crew_work_time()->float:
    '''Returns a random replacement work time'''
    return round(12 - replacement_crew_arrival_time(),2)

if __name__ == "__main__":
    if len(sys.argv) == 4:
        schedule = open("schedule.txt","r")
        train_nums = []
        for trains in schedule:
            train_nums.append(trains)
            
        last_train_hour = []      
        last_train_hour = train_nums[-1].split(" ")
        schedule.close()
        env = simpy.Environment()
        Train = Train(env,len(train_nums), float(last_train_hour[0]),0)
        env.run()
        
    elif len(sys.argv) == 3:
        env = simpy.Environment()
        Train = Train(env, float(sys.argv[1]), float(sys.argv[2]), 1)
        env.run()
