#! /usr/bin/env python
# -*- coding: utf-8 -*-
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# Outback Power Communicator by RogueProeliator <rp@rogueproeliator.com>
# 	Indigo plugin designed to read information from an Outback Power controller (MATE3
#	currently) used in solar power systems
#
#	Version 1.0.7:
#		Initial release of the plugin
#
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////


#/////////////////////////////////////////////////////////////////////////////////////////
# Python imports
#/////////////////////////////////////////////////////////////////////////////////////////
import re
import string
import os
from datetime import datetime

import RPFramework
import outbackPowerDevice

#/////////////////////////////////////////////////////////////////////////////////////////
# Constants and configuration variables
#/////////////////////////////////////////////////////////////////////////////////////////


#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# Plugin
#	Primary Indigo plugin class that is universal for all devices (controllers) to be
#	controlled
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class Plugin(RPFramework.RPFrameworkPlugin.RPFrameworkPlugin):

	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class creation; setup the device tracking
	# variables for later use
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		# RP framework base class's init method
		super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs, "http://www.duncanware.com/Downloads/IndigoHomeAutomation/Plugins/OutbackPowerCommunicator/OutbackPowerCommunicatorVersionInfo.html", managedDeviceClassModule=outbackPowerDevice)
	
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Overridden Configuration/Setup Routines
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called in order to create the tables for the plugin... it will
	# only be called when the database has connected
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def verifyAndCreateTables(self, dbConn):
		if dbConn:
			if not dbConn.TableExists("mate3ControllerLog"):
				sqlStr = "CREATE TABLE mate3ControllerLog (id #AUTO_INCR_KEY, deviceid INTEGER, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP, batteryvoltage FLOAT);"
				dbConn.ExecuteWithSubstitution(sqlStr)
		
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# Menu Item Commands
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called whenever the user has clicked on the Export Historical
	# Data menu command
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def exportHistoricalData(self, valuesDict, typeId):
		# this callback method must also do the validation... check to ensure that
		# at least one controller has been selected from the list
		errorsDict = indigo.Dict()
		controllerList = valuesDict.get("targetController")
		
		if len(controllerList) == 0:
			errorsDict["targetController"] = "Please select the controllers for data export"
			return (False, valuesDict, errorsDict)
		
		# validate the date range entered as text...
		strBeginDate = valuesDict.get("exportDateRangeStart", "")
		strEndDate = valuesDict.get("exportDateRangeEnd", "")
		
		try:
			dtBeginDate = datetime.strptime(strBeginDate, "%m/%d/%Y")
		except:
			if self.debugLevel >= RPFramework.RPFrameworkPlugin.DEBUGLEVEL_LOW:
				self.exceptionLog()
			errorsDict["exportDateRangeStart"] = "Please enter a valid begin date for data export"
			return (False, valuesDict, errorsDict)
			
		try:
			dtEndDate = datetime.strptime(strEndDate, "%m/%d/%Y")
		except:
			if self.debugLevel >= RPFramework.RPFrameworkPlugin.DEBUGLEVEL_LOW:
				self.exceptionLog()
			errorsDict["exportDateRangeEnd"] = "Please enter a valid ending date for data export"
			return (False, valuesDict, errorsDict)
			
		# validate that a filename was entered for the exportHistoricalData
		exportFilename = valuesDict.get("exportFilename")
		if exportFilename == "":
			errorsDict["exportFilename"] = ""
			return (False, valuesDict, errorsDict)
	
		# attempt to export the data from the SQL database...
		self.logDebugMessage("MATE3 data export commencing", RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
		
		# retrieve the sql rows from each controller
		exportRows = []
		for controllerDevice in controllerList:
			rpDevice = self.managedDevices[int(controllerDevice)]
			rpDevice.queueDeviceCommand(RPFramework.RPFrameworkCommand.RPFrameworkCommand("EXPORTLOGGEDDATA", commandPayload=(exportFilename, dtBeginDate, dtEndDate)))
		
		# successfully dispatched export commands...
		return (True, valuesDict)
		