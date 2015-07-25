#! /usr/bin/env python
# -*- coding: utf-8 -*-
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# Outback Power Communicator by RogueProeliator <rp@rogueproeliator.com>
# 	See plugin.py for more plugin details and information
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////

#/////////////////////////////////////////////////////////////////////////////////////////
# Python imports
#/////////////////////////////////////////////////////////////////////////////////////////
import indigo
import simplejson
import time
import RPFramework
import os

#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# MATE3ControllerDevice
#	Handles the configuration of a single MATE3 device from which we can read status info
#	regarding its attached devices
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class MATE3ControllerDevice(RPFramework.RPFrameworkRESTfulDevice.RPFrameworkRESTfulDevice):
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class receiving a command to start device
	# communication. The plugin will call other commands when needed, simply zero out the
	# member variables
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, plugin, device):
		super(MATE3ControllerDevice, self).__init__(plugin, device)
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should return the HTTP address that will be used to connect to the
	# RESTful device. It may connect via IP address or a host name
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getRESTfulDeviceAddress(self):
		return (self.indigoDevice.pluginProps.get("httpHostAddress", ""), int(self.indigoDevice.pluginProps.get("portNumber", "80")))
		
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Command and Response Handlers
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should be overridden in individual device classes whenever they must
	# handle custom commands that are not already defined
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def handleUnmanagedCommandInQueue(self, deviceHTTPAddress, rpCommand):
		if rpCommand.commandName == "EXPORTLOGGEDDATA":
			exportParams = rpCommand.commandPayload
			exportFilename = exportParams[0]
			dtBeginDate = exportParams[1]
			dtEndDate = exportParams[2]
			try:
				if self.dbConn:
					self.dbConn.QueryFromTableUsingRange("mate3ControllerLog", "deviceid", str(self.indigoDevice.id), dtBeginDate, dtEndDate, ["batteryVoltage"])
				else:
					indigo.server.log("Export data failed for Device " + controllerDevice + " - data logging is not enabled.")
				exportRows = self.dbConn.FetchAll()
				
				# create the file that will be used for export...
				exportFilename = os.path.expanduser(exportFilename)
				outFile = open(exportFilename, 'w')
				
				# write out the header row
				outFile.write('EntryID, TimeStamp, IndigoDevice, Voltage\n')
		
				# write out each line from the retrieved rows
				for voltageRow in exportRows:
					outFile.write(str(voltageRow[0]) + "," + str(voltageRow[1]) + "," + str(voltageRow[2]) + "," + str(voltageRow[3]) + "\n")
		
				# close the file
				outFile.close()
			
				self.hostPlugin.logDebugMessage("MATE3 data exported successfully to " + exportFilename, RPFramework.RPFrameworkPlugin.DEBUGLEVEL_LOW)
			except Exception, e:
				indigo.server.log("Error exporting MATE3 data: " + str(e), isError=True)
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called whenever a valid response has been received from the
	# MATE3 status update action
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def mate3StatusResponseReceived(self, responseObj, rpCommand):
		# this should be a standard JSON object... attempt to parse it using the normal
		# JSON routines available from Indigo
		try:
			# parse the response... the expected format will be:
			# Dictionary
			#	status properties
			#	"ports" => array of dictionaries
			responseJSON = simplejson.loads(responseObj)
			
			# first update the MATE3 controller states that are not related to ports
			# "Sys_Time" => controllerSystemTime & "Sys_Batt_V" => batteryVoltage
			controllerProps = responseJSON["devstatus"]
			self.hostPlugin.logDebugMessage("Effect execution: Update state 'controllerSystemTime' to '" + str(controllerProps["Sys_Time"]) + "'", RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			self.indigoDevice.updateStateOnServer(key='controllerSystemTime', value=controllerProps["Sys_Time"])
			
			self.hostPlugin.logDebugMessage("Effect execution: Update state 'batteryVoltage' to '" + str(controllerProps["Sys_Batt_V"]) + "'", RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			self.indigoDevice.updateStateOnServer(key='batteryVoltage', value=controllerProps["Sys_Batt_V"])
			
			# update the selected state into the main display state for the "sensor"; currently we only support
			# the single state
			self.indigoDevice.updateStateOnServer(key='sensorValue', value=controllerProps["Sys_Batt_V"], uiValue=str(controllerProps["Sys_Batt_V"]) + "V")
			
			# loop through the ports returned in the array
			portsArray = controllerProps["ports"]
			for portData in portsArray:
				portNumber = str(portData["Port"])
				self.hostPlugin.logDebugMessage("Processing data for port " + portNumber, RPFramework.RPFrameworkPlugin.DEBUGLEVEL_HIGH)
				if portNumber in self.childDevices:
					portDevice = self.childDevices[portNumber]
					self.hostPlugin.logDebugMessage("Found port child device ID:" + str(portDevice.indigoDevice.id), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_HIGH)
					
					# loop through each item in the object and determine if there is a corresponding
					# device state in indigo
					deviceStatePrefix = portDevice.indigoDevice.pluginProps.get("deviceStateJSONPrefix", "")
					self.hostPlugin.logDebugMessage("Using state prefix: " + deviceStatePrefix, RPFramework.RPFrameworkPlugin.DEBUGLEVEL_HIGH)
					for portValueItem, portValueData in portData.iteritems():
						deviceStateName = deviceStatePrefix + portValueItem
						self.hostPlugin.logDebugMessage("Checking state: " + deviceStateName + "; value: " + str(portValueData), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_HIGH)
						if portValueItem != "Port" and deviceStateName in portDevice.indigoDevice.states:
							if isinstance(portValueData, list):
								portDevice.indigoDevice.updateStateOnServer(key=deviceStateName, value=" ".join(portValueData)) 
							else:
								portDevice.indigoDevice.updateStateOnServer(key=deviceStateName, value=portValueData)

					# update the state column with the proper value
					valueStateName = portDevice.indigoDevice.pluginProps["sensorValueState"]
					portDevice.indigoDevice.updateStateOnServer(key="sensorValue", value=portDevice.indigoDevice.states[valueStateName], uiValue="%.1f"%portDevice.indigoDevice.states[valueStateName])
			
			# update the database with the new values that are being tracked
			if self.dbConn != None:
				self.hostPlugin.logDebugMessage("Logging voltage to SQL database...", RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
				insertSql = "INSERT INTO mate3ControllerLog (deviceid, batteryvoltage) VALUES (%s, %d);"
				self.dbConn.ExecuteWithSubstitution(insertSql, (str(self.indigoDevice.id), float(self.indigoDevice.states.get("batteryVoltage"))))
				
			# retrieve the last XX minutes of data, calculating the minimum, maximum and average voltage; this is only
			# to be done if it has been enabled in the device properties
			if self.indigoDevice.pluginProps.get("enableVoltageTracking", False) == True:
				self.hostPlugin.logDebugMessage("Retrieving voltage tracking aggregate...", RPFramework.RPFrameworkPlugin.DEBUGLEVEL_HIGH)
				trackingSql = "SELECT MIN(batteryvoltage), MAX(batteryvoltage), AVG(batteryvoltage), COUNT() FROM mate3ControllerLog WHERE ts > datetime('now', '-" + self.indigoDevice.pluginProps.get("voltageTrackingInterval", "15") + " Minute') GROUP BY batteryvoltage"
				self.dbConn.ExecuteSQL(trackingSql)
				trackingRow = self.dbConn.FetchOne()
				
				# minimum in tracking range
				variableId = int(str(self.indigoDevice.pluginProps.get("voltageTrackingMinVariable", 0)))
				if variableId > 0:
					indigo.variable.updateValue(variableId, value=str(trackingRow[0]))
					
				# maximum in tracking range
				variableId = int(str(self.indigoDevice.pluginProps.get("voltageTrackingMaxVariable", 0)))
				if variableId > 0:
					indigo.variable.updateValue(variableId, value=str(trackingRow[1]))
					
				# average in tracking range
				variableId = int(str(self.indigoDevice.pluginProps.get("voltageTrackingAvgVariable", 0)))
				if variableId > 0:
					indigo.variable.updateValue(variableId, value=str(trackingRow[2]))
				
				# count of readings in tracking range
				variableId = int(str(self.indigoDevice.pluginProps.get("voltageTrackingCountVariable", 0)))
				if variableId > 0:
					indigo.variable.updateValue(variableId, value=str(trackingRow[3]))
				
				self.hostPlugin.logDebugMessage("Updated Aggregate data:" + str(trackingRow), RPFramework.RPFrameworkPlugin.DEBUGLEVEL_MED)
			
			# flag the states as having updated successfully 
			self.indigoDevice.updateStateOnServer(key='lastUpdateRead', value=time.strftime("%x %X"))
		except:
			indigo.server.log(u"Error reading response [ID:" + str(self.indigoDevice.id) + "]", isError=True)
			self.hostPlugin.exceptionLog()
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will handle an error as thrown by the REST call... it allows 
	# descendant classes to do their own processing
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-		
	def handleRESTfulError(self, rpCommand, err):
		if self.hostPlugin.debug:
			indigo.server.log("An error occurred executing the GET/PUT request (Device: " + str(self.indigoDevice.id) + "): " + str(err), isError=True)
		
		
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# MATE3ConnectedPortDevice
#	Handles the devices which may be attached to the MATE3 controllers on the various
#	available ports (may represent many different devices types in Indigo)
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class MATE3ConnectedPortDevice(RPFramework.RPFrameworkNonCommChildDevice.RPFrameworkNonCommChildDevice):

	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class receiving a command to start device
	# communication. The plugin will call other commands when needed, simply zero out the
	# member variables
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, plugin, device):
		super(MATE3ConnectedPortDevice, self).__init__(plugin, device)
		