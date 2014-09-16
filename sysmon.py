#!/usr/bin/python
"""
SysMon.pyw
Initial application development 03Sep14 by S. Miller
The application utilizes the psutil and platform python modules to provide system information
for display via text fields, a table and Matplotlib plots.

The application utilizes a timer with user selectable timer intervals to update information 
provided to the application.

"""

import sys, os, time
import re

import psutil
#check psutil version as command syntax changes between version 1 and version 2
ver=psutil.__version__
verChk1=re.match('1.[0-9].[0-9]',ver) #latest psutil version 1 is 1.2.1 - using positional numeric wildcards to check sub versions
#thus the check is for version 1 as version 2 and following versions are still evolving
#match returns a string if a match is found else returns NoneType 
if verChk1 != None:
    psutilVer=1
else:
    psutilVer=2


from PyQt4 import Qt, QtCore, QtGui
from SysMon import *

import platform


import matplotlib
if matplotlib.get_backend() != 'QT4Agg':
    matplotlib.use('QT4Agg')
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4 import NavigationToolbar2QT as NavigationToolbar

import matplotlib.pyplot as plt
import numpy as np

import datetime
import commands

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    _fromUtf8 = lambda s: s
    
class SysMon(QtGui.QMainWindow):

    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        self.setWindowTitle("System Status")
        self.ui = Ui_MainWindow() #defined within SysMon.py
        self.ui.setupUi(self)
        self.ui.progressBarStatusMemory.setStyleSheet("QProgressBar {width: 25px;border: 1px solid black; border-radius: 3px; background: white;text-align: center;padding: 0px;}" 
                               +"QProgressBar::chunk:horizontal {background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00CCEE, stop: 0.3 #00DDEE, stop: 0.6 #00EEEE, stop:1 #00FFEE);}")
        self.ui.progressBarStatusCPU.setStyleSheet("QProgressBar {width: 25px;border: 1px solid black; border-radius: 3px; background: white;text-align: center;padding: 0px;}" 
                               +"QProgressBar::chunk:horizontal {background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00CCEE, stop: 0.3 #00DDEE, stop: 0.6 #00EEEE, stop:1 #00FFEE);}")

        #setup timer to enable periodic events such as status update checks
        self.ctimer = QtCore.QTimer()
        self.ctimer.start(2000)  #time in mSec - set repetitive timer of 1 second
        QtCore.QObject.connect(self.ctimer, QtCore.SIGNAL("timeout()"), self.constantUpdate)                               
        self.connect(self.ui.actionExit, QtCore.SIGNAL('triggered()'), self.confirmExit) #define function to confirm and perform exit
        
        #update rate actions
        self.connect(self.ui.action1_Second, QtCore.SIGNAL('triggered()'), self.update1Sec)
        self.connect(self.ui.action2_Seconds, QtCore.SIGNAL('triggered()'), self.update2Sec)
        self.connect(self.ui.action5_Seconds, QtCore.SIGNAL('triggered()'), self.update5Sec)
        self.connect(self.ui.action10_Seconds, QtCore.SIGNAL('triggered()'), self.update10Sec)
        self.update=2 #set default to 2 seconds update rate
        
        #duration actions
        self.connect(self.ui.action60Seconds, QtCore.SIGNAL('triggered()'), self.update60Duration)
        self.connect(self.ui.action300Seconds, QtCore.SIGNAL('triggered()'), self.update300Duration)
        self.connect(self.ui.action600Seconds, QtCore.SIGNAL('triggered()'), self.update600Duration)
        self.connect(self.ui.action3600Seconds, QtCore.SIGNAL('triggered()'), self.update3600Duration)
        self.duration=60 #set default plot duration to 60 seconds
        
        self.connect(self.ui.actionCheck_Matlab_Licenses, QtCore.SIGNAL('triggered()'), self.updateMatlab)
        
        self.connect(self.ui.actionAbout, QtCore.SIGNAL('triggered()'), self.About)

        QtCore.QObject.connect(self.ui.pushButtonUpdate, QtCore.SIGNAL('clicked(bool)'), self.updateProcesses)
        
        #Initialize System Tab
        self.ui.tabWidget.setCurrentIndex(0)
        self.ui.labelComputerName.setText("Computer Name: "+platform.node())
        if platform.os.name == 'nt':
            info=platform.win32_ver()
            oslabel="Windows "+info[0]+"  Version: "+info[1]
        elif platform.os.name == 'posix':
            info=platform.linux_distribution()
            oslabel=info[0]+" Version: "+info[1]
        elif platform.os.name == 'mac':
            info=platform.mac_ver()
            oslabel=info[0]+"  Version: "+info[1]
        else:
            oslabel=" "
        
        self.ui.labelOS.setText("Operating System: "+oslabel)
        info=platform.uname()
        self.ui.labelProcFam.setText("Processor Family: "+info[5])
        
        #determine the number of users on the computer
        userInfo=psutil.get_users() if psutilVer==1 else psutil.users()
        lst=[]
        for item in userInfo:
            lst.append(item.name)
        uusers=set(lst)
        Nuusers=len(uusers)
        self.ui.labelNUsers.setText("Number of Users Logged On: "+str(Nuusers))
        
        #determine the computer uptime
        if psutilVer == 1:
            uptime = str(datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.BOOT_TIME))
        else:
            uptime = str(datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time()))
        self.ui.labelUptime.setText("System Uptime: "+uptime)
        
        #Initialize History Tab
        self.ui.tabWidget.setCurrentIndex(1)
        #Place Matplotlib figure within the GUI frame
        #create drawing canvas
        # a figure instance to plot on
        
        matplotlib.rc_context({'toolbar':False})
        #initialize figure 1 and its canvas for cpu and memory history plots
        self.ui.figure = plt.figure(1)
        # the Canvas Widget displays the `figure`
        # it takes the `figure` instance as a parameter to __init__
        self.ui.canvas = FigureCanvas(self.ui.figure)
        layout=QtGui.QVBoxLayout(self.ui.framePlot)
        layout.addWidget(self.ui.canvas)
        self.ui.layout=layout
        
        #initialize figure 2 and its canvas for user usage bar chart 
        self.ui.figure2 = plt.figure(2)
        self.ui.canvas2 = FigureCanvas(self.ui.figure2)
        layout2=QtGui.QVBoxLayout(self.ui.frameBar)
        layout2.addWidget(self.ui.canvas2)
        self.ui.layout2=layout2   
        
        #initialize history plot arrays
        Nsamples=3600
        self.ui.Nsamples=Nsamples
        #need one extra sample to fill the plotting interval
        self.ui.cpu=np.zeros(Nsamples+1) 
        self.ui.mem=np.zeros(Nsamples+1)
        self.ui.dt=[None]*(Nsamples+1)
        
        #initialize the process table
        self.doUpdates=True #flag for updating the process tab table
        updateProcTable(self)        
        
        #upon initialization completion, set System tab (first tab on left) as the visible tab
        self.ui.tabWidget.setCurrentIndex(0)
        
    def constantUpdate(self): 
        #redirct to global function
        constantUpdateActor(self)
        
    def confirmExit(self):
        reply = QtGui.QMessageBox.question(self, 'Message',
            "Are you sure to quit?", QtGui.QMessageBox.Yes | 
            QtGui.QMessageBox.No, QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
			#close application
            self.close()
        else:
			#do nothing and return
            pass     
            
    def update1Sec(self):
        self.update=1
        self.ctimer.stop()
        self.ctimer.start(1000)
        #clear persistent arrays when update rate changed
        self.ui.cpu=self.ui.cpu*0 
        self.ui.mem=self.ui.mem*0
        self.ui.dt=[None]*self.ui.Nsamples
        
    def update2Sec(self):
        self.update=2
        self.ctimer.stop()
        self.ctimer.start(2000)
        #clear persistent arrays when update rate changed
        self.ui.cpu=self.ui.cpu*0 
        self.ui.mem=self.ui.mem*0
        self.ui.dt=[None]*self.ui.Nsamples
        
    def update5Sec(self):
        self.update=5  
        self.ctimer.stop()
        self.ctimer.start(5000)
        #clear persistent arrays when update rate changed
        self.ui.cpu=self.ui.cpu*0 
        self.ui.mem=self.ui.mem*0
        self.ui.dt=[None]*self.ui.Nsamples
        
    def update10Sec(self):
        self.update=10       
        self.ctimer.stop()
        self.ctimer.start(10000)
        #clear persistent arrays when update rate changed
        self.ui.cpu=self.ui.cpu*0 
        self.ui.mem=self.ui.mem*0
        self.ui.dt=[None]*self.ui.Nsamples        
            
    def update60Duration(self):
        self.duration=60
    def update300Duration(self):
        self.duration=300
    def update600Duration(self):
        self.duration=600
    def update3600Duration(self):
        self.duration=3600
   
    def updateMatlab(self):
        #run license server command to extract license info
        info=commands.getstatusoutput('lmstat -S -c 27010@licenses1.sns.gov')
        info=str(info[1]) #seem to need to make this a string for Linux to work properly
        #test if info string contains MATLAB info
        if info.find("MATLAB") < 0:
            #case where no license server found
            outstr="No Matlab License Server Found to Check"
        else:
            indx0=info.find("Users of MATLAB:")
            indx1=info.find("licenses in use")
            if indx0 > -1 and indx1 > -1:
                outstr=info[indx0:indx1+15+1]
            else:
                outstr="Unable to determine Matlab license information"
        dialog=QtGui.QMessageBox(self)
        #print "outstr: "+outstr
        dialog.setText(outstr)
        dialog.setDetailedText(info) #give full info in detailed text
        dialog.exec_()
        
        
    def About(self):
        dialog=QtGui.QMessageBox(self)
        dialog.setText("PyQt4 System Monitoring Application V0.01")
        info='Application Info: \n\r * Changing the Update Rate Clears plots \n\r * It may take one full new update cycle for changes to take effect \n\r * Update rate shown in History plot xaxis label \n\r * Updating processes may take several seconds \n\r * CPU percentage can be greater than 100 when more than a single core is involved'
        dialog.setDetailedText(info) #give full info in detailed text
        dialog.exec_()

    def updateProcesses(self):
        if self.doUpdates == True:
            #case to toggle to False
            self.doUpdates=False
            self.ui.pushButtonUpdate.setText('Continue')
        else:
            #case where updates must be off
            self.doUpdates=True
            self.ui.pushButtonUpdate.setText('Hold Updates')
        
    def resizeEvent(self,resizeEvent):
        sz=self.ui.tableWidgetProcess.size()
        w=sz.width()
        self.ui.tableWidgetProcess.setColumnWidth(0,3*w/20)
        self.ui.tableWidgetProcess.setColumnWidth(1,5*w/20)
        self.ui.tableWidgetProcess.setColumnWidth(2,3*w/20)
        self.ui.tableWidgetProcess.setColumnWidth(3,3*w/20)
        self.ui.tableWidgetProcess.setColumnWidth(4,6*w/20)
                               
def constantUpdateActor(self):

    #check duration
    Ndur=self.duration

    #update global variables 

    #mode to show status in percentage
    cpu_stats = psutil.cpu_times_percent(interval=0,percpu=False) #syntax seems to be same for psutil versions 1 and 2
    percentcpubusy = 100.0 - cpu_stats.idle
    self.ui.progressBarStatusCPU.setValue(round(percentcpubusy))
    percentmembusy=psutil.virtual_memory().percent
    self.ui.progressBarStatusMemory.setValue(percentmembusy)
    Ncpus=len(psutil.cpu_percent(percpu=True))
    self.ui.Ncpus=Ncpus
    totalcpustr='CPU Count: '+str(Ncpus)
#        print "Total CPU str: ",totalcpustr
    self.ui.labelCPUCount.setText(totalcpustr)
    totalmem=int(round(float(psutil.virtual_memory().total)/(1024*1024*1024))) #psutil syntax OK for both versions
#        print "Total Mem: ",totalmem
    self.ui.totalmem=totalmem
    totalmemstr='Max Mem: '+str(totalmem)+' GB'
#        print "Total Mem str: ",totalmemstr
    self.ui.labelMaxMem.setText(totalmemstr)
    
    #update first position with most recent value overwriting oldest value which has been shifted to first position
    self.ui.cpu=np.roll(self.ui.cpu,1)
    self.ui.cpu[0]=percentcpubusy
    self.ui.mem=np.roll(self.ui.mem,1)
    self.ui.mem[0]=percentmembusy
#        self.ui.dt=np.roll(self.ui.dt,1)
#        self.ui.dt[0]=datetime.datetime.now()
    
    # update system tab
    if self.ui.tabWidget.currentIndex() == 0:
        #determine the computer uptime
        if psutilVer == 1:
            uptime = str(datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.BOOT_TIME))
        else:
            uptime = str(datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time()))
        self.ui.labelUptime.setText("System Uptime: "+uptime)


        
        #update the number of users each time interval as well
        userInfo=psutil.get_users() if psutilVer == 1 else psutil.users()
        lst=[]
        for item in userInfo:
            lst.append(item.name)
        uusers=set(lst)
        Nuusers=len(uusers)
        self.ui.labelNUsers.setText("Number of Users Logged On: "+str(Nuusers))
    
    #update the history plot
    if self.ui.tabWidget.currentIndex() == 1:
        #only update history plot if tab is active    
        font = {'family' : 'sans-serif',
            'weight' : 'bold',
            'size'   : 10}
        matplotlib.rc('font', **font)
     
        xtime=range(0,self.ui.Nsamples+1,self.update)
        
        Npts=Ndur/self.update
        
        plt.figure(self.ui.figure.number)     #make plot figure active   
        plt.clf() #clear figure each time for rolling updates to show
        plt.plot(xtime[0:Npts+1],self.ui.cpu[0:Npts+1],color='Blue',label='CPU Busy')
        plt.plot(xtime[0:Npts+1],self.ui.mem[0:Npts+1],color='Green',label='Mem Busy')
        plt.title('Composite CPU and Memory Activity',fontsize=10,fontweight='bold')
        plt.ylabel('% Busy',fontsize=9.5,fontweight='bold')
        
        if self.update == 1:
            xlab="Seconds with 1 Second Updates"
        elif self.update == 2:
            xlab="Seconds with 2 Second Updates"
        elif self.update == 5:
            xlab="Seconds with 5 Second Updates"    
        elif self.update == 10:
            xlab="Seconds with 10 Second Updates"
        plt.xlabel(xlab,fontsize=9.5,fontweight='bold')
        plt.legend(loc="upper right",prop={'size':9})
        plt.xlim([0,Ndur])
        self.ui.canvas.draw()
    
    #update the process table
    if self.ui.tabWidget.currentIndex() == 2:
        #only update process table if tab is active
        updateProcTable(self)
    
    #update the Users bar chart
    if self.ui.tabWidget.currentIndex() == 3:
        #only update bar chart if the tab is active.
        updateUserChart(self)
    
    
    
def updateProcTable(self):
    if self.doUpdates==True:
        table=self.ui.tableWidgetProcess
        #first remove all rows
        Nrows=table.rowCount()
        for row in range(Nrows):
            table.removeRow(0)
        
        #get the processes
        pidList=psutil.get_pid_list() if psutilVer == 1 else psutil.pids()
        Npids=len(pidList)
        
        #now add rows to the table according to the number of processes
    #    for row in range(Npids):
    #        table.insertRow(0)
        
        #now populate the table
        row=0  #table row counter incremented for each row added to the process table
        rout=0 #counter for number of rows to remove due to invalid processes 
        memtot=psutil.virtual_memory()  #psutil syntax OK for both versions
        
        #determine which column has been selected for sorting
        column_sorted=table.horizontalHeader().sortIndicatorSection()
        order = table.horizontalHeader().sortIndicatorOrder()
        #temporarily set sort column to outside column range so that table items can be filled properly
        table.sortItems(5,order=QtCore.Qt.AscendingOrder)
        #print table.horizontalHeader().sortIndicatorSection()
        
        #create empty dictionaries to be used by the process table
        d_user={}
        d_cpu={}
        d_mem={}
        d_name={}

        #fill the dictionaries - seems to need to be done faster than within loop which also fills the table...not sure why...
        for proc in psutil.process_iter():
            cpupct=proc.get_cpu_percent(interval=0) if psutilVer == 1 else proc.cpu_percent(interval=0)
            memVal=float(int(float(proc.get_memory_percent())*100.0))/100.0 if psutilVer == 1 else float(int(float(proc.memory_percent())*100.0))/100.0
            try:
                #don't update dictionaries if name gives an access denied error when checking process name
                pname=proc.name if psutilVer == 1 else proc.name()
                d_user.update({proc.pid:proc.username}) if psutilVer == 1 else d_user.update({proc.pid:proc.username()})
                d_cpu.update({proc.pid:cpupct})
                d_mem.update({proc.pid:memVal})
                d_name.update({proc.pid:pname})
            except:
                pass #place holder

        #now fill the table for display
        for proc in d_user.keys():
            #print "proc: ",proc," type: ",type(proc)
            pid=int(proc)
            #print "pid: ",pid

            table.insertRow(0)
            #print "inserting row"
            #set process id
            item=QtGui.QTableWidgetItem()
            item.setData(QtCore.Qt.DisplayRole,pid) 
            table.setItem(0,0,item)
            #set username
            #print " d_user[proc]: ",d_user[proc],"  proc: ",proc
            table.setItem(0,1,QtGui.QTableWidgetItem(d_user[proc]))
            #set CPU %
            item=QtGui.QTableWidgetItem()
            item.setData(QtCore.Qt.DisplayRole,d_cpu[proc])
            table.setItem(0,2,item)
            #set memory %
            item=QtGui.QTableWidgetItem()
            item.setData(QtCore.Qt.DisplayRole,d_mem[proc])
            table.setItem(0,3,item)
            #set process name
            table.setItem(0,4,QtGui.QTableWidgetItem(d_name[proc]))
            row+=1

            
     #   for row in range(rout):
     #       table.removeRow(Npids-row)
        #restore sort to previously selected column
        #table.sortItems(column_sorted,order=QtCore.Qt.AscendingOrder)
        table.sortItems(column_sorted,order=order)
        self.ui.labelLastUpdate.setText("Last Update: "+str(datetime.datetime.now()))

def updateUserChart(self):

    font = {'family' : 'sans-serif',
        'weight' : 'bold',
        'size'   : 9}

    matplotlib.rc('font', **font)
    
    f=plt.figure(self.ui.figure2.number)

#    self.ui.figure2=plt.figure(2)
    plt.clf()
    plt.cla()
#    f.gca().cla()

    #create empty dictionaries to be used by the process table
    d_user={}
    d_cpu={}
    d_mem={}
    d_name={}
    #fill the dictionaries - seems to need to be done faster than within loop which also fills the table...not sure why...
    for proc in psutil.process_iter():
        cpupct=proc.get_cpu_percent(interval=0) if psutilVer == 1 else proc.cpu_percent(interval=0)
        memVal=float(int(float(proc.get_memory_percent())*100.0))/100.0 if psutilVer == 1 else float(int(float(proc.memory_percent())*100.0))/100.0
        try:
            #don't update dictionaries if name gives an access denied error when checking process name
            pname=proc.name if psutilVer == 1 else proc.name()
            d_user.update({proc.pid:proc.username}) if psutilVer == 1 else d_user.update({proc.pid:proc.username()})
            d_cpu.update({proc.pid:cpupct})
            d_mem.update({proc.pid:memVal})
            d_name.update({proc.pid:pname})
        except:
            pass #place holder
            
    users=d_user.values()
    users_unique=list(set(users)) #use set() to find unique users then convert the resulting set to a list via list()
    Nusers=len(users_unique)

    #create cpu and memory by users dictionaries
    cpu_by_users={}
    mem_by_users={}
    for u in range(Nusers):
        cpu_by_users.update({users_unique[u]:0})
        mem_by_users.update({users_unique[u]:0})
    #apparently update does not order keys in sequence to users_unique
    #thus need to re-create users_unique according to the order of the users
    #in the cpu and mem dictionary keys
    users_unique=list(cpu_by_users.keys())

    #fill cpu and memory dictionaries sequencing thru each PID
    for pid in d_user.keys():
        user=d_user[pid]
        cpu_by_users[user]=cpu_by_users[user] + d_cpu[pid]
        mem_by_users[user]=mem_by_users[user] + d_mem[pid]

    #now convert to a list which we can index
    cpu_by_users_lst=cpu_by_users.values()
    mem_by_users_lst=mem_by_users.values()
        
    width=0.85

    colors=['b','g','r','c','m','y','gray','hotpink','brown','k']
    Nmax=len(colors) #don't want to have more users than colors...

    if self.ui.radioButtonCPU.isChecked():
        sortBy='cpu'
    elif self.ui.radioButtonMem.isChecked():
        sortBy='mem'
    else:
        print "invalid radio button selection - using CPU sort as default"
        sortBy='cpu'
    #sortBy='cpu' # 'cpu' or 'mem' - use for debugging
    #create sort index
    if sortBy=='cpu':
        indx=sorted(range(len(cpu_by_users_lst)), key=cpu_by_users_lst.__getitem__,reverse=True)
    elif sortBy=='mem':
        indx=sorted(range(len(mem_by_users_lst)), key=mem_by_users_lst.__getitem__,reverse=True)
    else:
        print 'Incorrect sort parameter'
    #sort lists
    cpu_by_users_sorted=[cpu_by_users_lst[x] for x in indx]
    mem_by_users_sorted=[mem_by_users_lst[x] for x in indx]
    users_unique_sorted=[users_unique[x] for x in indx]

    #restrict the number of users we'll show to Nmax
    if Nusers > Nmax:
        #replace the Nmaxth - 1 element with the total of the values from index Nmax - 1 to the end of the list
        cpu_by_users_sorted[Nmax-1]=sum(cpu_by_users_sorted[Nmax-1:])
        mem_remaining=sum(mem_by_users_sorted[Nmax-1:])
        users_unique_sorted[Nmax-1]='Remaining'
        Nshow=Nmax
    else:
        Nshow=Nusers

    if min(cpu_by_users_sorted) < 0:
        print " *** cp_by_users_sorted has values less than zero"
        print cpu_by_users_sorted
        print " ***"
    if min(mem_by_users_sorted) < 0:
        print " *** mem_by_users_sorted has values less than zero"
        print mem_by_users_sorted
        print " ***"        

    #range check the values of the sorted lists - may not be necessary, just being cautious...
    tst=np.array(cpu_by_users_sorted)<0  #need an array for summing
    indx=cpu_by_users_sorted<0           #need bool list for indexing
    if sum(tst) > 0:
        print "cpu_by_users < 0: ",sum(indx)
        cpu_by_users_sorted[indx]=0
    tst=np.array(cpu_by_users_sorted)>self.ui.Ncpus*100
    indx=cpu_by_users_sorted>self.ui.Ncpus*100
    if sum(tst) > 0:
        print "cpu_by_users > Ncpus*100: ",sum(indx)
        cpu_by_users_sorted[indx]=self.ui.Ncpus*100
    tst=np.array(mem_by_users_sorted)<0
    indx=mem_by_users_sorted<0
    if sum(tst) > 0:
        print "mem_by_users < 0: ",sum(indx)
        mem_by_users_sorted[indx]=0
    tst=np.array(mem_by_users_sorted)>self.ui.totalmem
    indx=mem_by_users_sorted>self.ui.totalmem
    if sum(tst) > 0:
        print "mem_by_users > totalmem: ",sum(indx)
        mem_by_users_sorted[indx]=self.ui.totalmem
    
    
    p=[] #list to contain plot objects for use by the legend   
    ind=np.arange(2)
    
    
    for u in range(Nshow):
        if u == 0:
            p.append(plt.bar(ind,(cpu_by_users_sorted[u],mem_by_users_sorted[u]),width,bottom=(0,0),color=colors[u]))
        else:
            p.append(plt.bar(ind,(cpu_by_users_sorted[u],mem_by_users_sorted[u]),width,bottom=(sum(cpu_by_users_sorted[0:u]),sum(mem_by_users_sorted[0:u])),color=colors[u]))
    
    plt.title('CPU and Memory Usage by User',fontsize=10,fontweight='bold')
    
    #remove default yaxis ticks then redraw them via ax1 and ax2 below
    frame=plt.gca()
    frame.axes.get_yaxis().set_ticks([])
    plt.xticks(np.arange(2)+width/2.,('CPU','Mem'),fontsize=9,fontweight='bold')
    ymaxCPU=round(int((sum(cpu_by_users_sorted[0:Nshow])+100)/100)*100)
    ymaxMEM=round(int((sum(mem_by_users_sorted[0:Nshow])+100)/100)*100)
    ymax=max([ymaxCPU,ymaxMEM,100])
#    plt.ylim([0,ymax])
    
    #compute composite %
    ylab=np.arange(6)/5.0*float(ymax)/float(self.ui.Ncpus)
    ylab=ylab*10
    tmp=ylab.astype('int')
    tmp1=tmp.astype('float')
    tmp1=tmp1/10
    ylab1=tmp1
    
    ax1=plt.twinx()
    ax1.set_ylabel('Composite CPU Percent',fontsize=9,fontweight='bold')
    ax1.yaxis.set_ticks_position('left')
    ax1.yaxis.set_label_position('left')
    ax1.set_yticks(ylab1)
    
    usersLegend=users_unique_sorted[0:Nshow]
    #reverse legend print order to have legend correspond with the order data are placed in the bar chart
    usersLegend.reverse()
    p.reverse()
    plt.legend(p,usersLegend)

    
    #place second y axis label on plot
    ylab2=np.arange(5)/4.0*float(ymax)
    ax2=plt.twinx()
    ax2.set_ylabel('Percent',fontsize=9,fontweight='bold')
    ax2.set_yticks(ylab2)
    #ax2.set_yticks(ylab2)
    ax2.yaxis.set_ticks_position('right')
    ax2.yaxis.set_label_position('right')

    self.ui.canvas2.draw()
    
def reLayout(self):
    tmpWidget=QtGui.QWidget()
    tmpWidget.setLayout(self.ui.layout2)
    tmpLayout = QtGui.QVBoxLayout(self.ui.frameBar)
    
if __name__=="__main__":
    app = QtGui.QApplication(sys.argv)
    sysmon = SysMon()
    sysmon.show()

    sys.exit(app.exec_())