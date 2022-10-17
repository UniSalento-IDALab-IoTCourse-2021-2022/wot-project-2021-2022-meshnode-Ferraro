#!/usr/bin/env python3

###################################################################
#
# This is a unified test sample for BT Mesh
#
# To run the test:
#     test-mesh [token]
#
#            'token' is an optional argument. It must be a 16-digit
#            hexadecimal number. The token must be associated with
#            an existing node. The token is generated and assigned
#            to a node as a result of successful provisioning (see
#            explanation of "join" option).
#            When the token is set, the menu operations "attach"
#            and "remove" may be performed on a node specified
#            by this token.
#
#      The test imitates a device with 2 elements:
#            element 0: OnOff Server model
#                       Sample Vendor model
#            element 1: OnOff Client model
#
# The main menu:
#       token
#       join
#       attach
#       remove
#       dest
#       uuid
#       app-index
#       client-menu
#       exit
#
# The main menu options explained:
#     token
#            Set the unique node token.
#            The token can be set from command line arguments as
#            well.
#
#     join
#            Request provisioning of a device to become a node
#            on a mesh network. The test generates device UUID
#            which is displayed and will need to be provided to
#            an outside entity that acts as a Provisioner. Also,
#            during the provisioning process, an agent that is
#            part of the test, will request (or will be requested)
#            to perform a specified operation, e.g., a number will
#            be displayed and this number will need to be  entered
#            on the Provisioner's side.
#            In case of successful provisioning, the application
#            automatically attaches as a node to the daemon. A node
#            'token' is returned to the application and is used
#            for the runtime of the test.
#
#     attach
#            Attach the application to bluetoothd-daemon as a node.
#            For the call to be successful, the valid node token must
#            be already set, either from command arguments or by
#            executing "set token" operation or automatically after
#            successfully executing "join" operation in the same
#            test run.
#
#     remove
#           Permanently removes any node configuration from daemon
#           and persistent storage. After this operation, the node
#           is permanently forgotten by the daemon and the associated
#           node token is no longer valid.
#
#     dest
#           Set destination address to send messages: 4 hex digits
#
#     app-index
#           Set AppKey index to indicate which application key to use
#           to encode outgoing messages: up to 3 hex digits
#
#     vendor-send
#           Allows to send an arbitrary endor message.
#           The destination is set based on previously executed "dest"
#           command (if not set, the outbound message will fail).
#           User is prompted to enter hex bytearray payload.
#           The message is originated from the vendor model registered
#           on element 0. For the command to succeed, the AppKey index
#           that is set by executing "app-key" must correspond to the
#           application key to which the Sample Vendor model is bound.
#
#     client-menu
#           Enter On/Off client submenu.
#
#     quit
#           Exits the test.
#
###################################################################
import sys
import struct
import fcntl
import os
import numpy
import random
import dbus
import dbus.service
import dbus.exceptions
import json

from threading import Timer
import time
import uuid

try:
  from gi.repository import GLib
except ImportError:
  import glib as GLib
from dbus.mainloop.glib import DBusGMainLoop

try:
  from termcolor import colored, cprint
  set_error = lambda x: colored('!' + x, 'red', attrs=['bold'])
  set_cyan = lambda x: colored(x, 'cyan', attrs=['bold'])
  set_green = lambda x: colored(x, 'green', attrs=['bold'])
  set_yellow = lambda x: colored(x, 'yellow', attrs=['bold'])
except ImportError:
  print('!!! Install termcolor module for better experience !!!')
  set_error = lambda x: x
  set_cyan = lambda x: x
  set_green = lambda x: x
  set_yellow = lambda x: x

# Provisioning agent
try:
  import agent
except ImportError:
  print("agent not imported")
  agent = None

MESH_SERVICE_NAME = 'org.bluez.mesh'
DBUS_PROP_IFACE = 'org.freedesktop.DBus.Properties'
DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'

MESH_MGR_IFACE = 'org.bluez.mesh.Management1'
MESH_NETWORK_IFACE = 'org.bluez.mesh.Network1'
MESH_NODE_IFACE = 'org.bluez.mesh.Node1'
MESH_APPLICATION_IFACE = 'org.bluez.mesh.Application1'
MESH_ELEMENT_IFACE = 'org.bluez.mesh.Element1'

APP_COMPANY_ID = 0x05f1
APP_PRODUCT_ID = 0x0001
APP_VERSION_ID = 0x0001

VENDOR_ID_NONE = 0xffff

TRANSACTION_TIMEOUT = 6

app = None
bus = None
mainloop = None
node = None
node_mgr = None
mesh_net = None

dst_addr = 0x0000
app_idx = 0

# Node token housekeeping
token = None
have_token = False
attached = False

# Remote device UUID
have_uuid = False
remote_uuid = None

# Scanned devices

scanned = {}

# Menu housekeeping
MAIN_MENU = 0
ON_OFF_CLIENT_MENU = 1

INPUT_NONE = 0
INPUT_TOKEN = 1
INPUT_DEST_ADDRESS = 2
INPUT_APP_KEY_INDEX = 3
INPUT_MESSAGE_PAYLOAD = 4
INPUT_UUID = 5

menus = []
current_menu = None

user_input = 0
input_error = False

send_opts = dbus.Dictionary(signature='sv')
send_opts = {'ForceSegmented' : dbus.Boolean(True)}

def raise_error(str_value):
	global input_error

	input_error = True
	print(set_error(str_value))

def clear_error():
	global input_error
	input_error = False

def is_error():
	return input_error

def app_exit():
	global mainloop
	global app

	for el in app.elements:
		for model in el.models:
			if model.timer != None:
				model.timer.cancel()
	mainloop.quit()

def set_token(str_value):
	global token
	global have_token

	if len(str_value) != 16:
		raise_error('Expected 16 digits')
		return

	try:
		input_number = int(str_value, 16)
	except ValueError:
		raise_error('Not a valid hexadecimal number')
		return

	token = numpy.uint64(input_number)
	have_token = True

def set_uuid(str_value):
	global remote_uuid
	global have_uuid

	if len(str_value) != 32:
		raise_error('Expected 32 digits')
		return

	remote_uuid = bytearray.fromhex(str_value)
	have_uuid = True

def array_to_string(b_array):
	str_value = ""
	for b in b_array:
		str_value += "%02x" % b
	return str_value

def generic_error_cb(error):
	print(set_error('D-Bus call failed: ') + str(error))

def generic_reply_cb():
	return

def attach_app_error_cb(error):
	print(set_error('Failed to register application: ') + str(error))

def attach(token):
	print('Attach mesh node to bluetooth-meshd daemon')

	mesh_net.Attach(app.get_path(), token,
					reply_handler=attach_app_cb,
					error_handler=attach_app_error_cb)

def join_cb():
	print('Join procedure started')

def join_error_cb(reason):
	print('Join procedure failed: ', reason)

def remove_node_cb():
	global attached
	global have_token

	print(set_yellow('Node removed'))
	attached = False
	have_token = False

def unwrap(item):
	if isinstance(item, dbus.Boolean):
		return bool(item)
	if isinstance(item, (dbus.UInt16, dbus.Int16, dbus.UInt32, dbus.Int32,
						dbus.UInt64, dbus.Int64)):
		return int(item)
	if isinstance(item, dbus.Byte):
		return bytes([int(item)])
	if isinstance(item, dbus.String):
			return item
	if isinstance(item, (dbus.Array, list, tuple)):
		return [unwrap(x) for x in item]
	if isinstance(item, (dbus.Dictionary, dict)):
		return dict([(unwrap(x), unwrap(y)) for x, y in item.items()])

	print(set_error('Dictionary item not handled: ') + type(item))

	return item

def attach_app_cb(node_path, dict_array):
	global attached

	attached = True

	print(set_yellow('Mesh app registered: ') + set_green(node_path))

	obj = bus.get_object(MESH_SERVICE_NAME, node_path)

	global node_mgr
	node_mgr = dbus.Interface(obj, MESH_MGR_IFACE)

	global node
	node = dbus.Interface(obj, MESH_NODE_IFACE)

	els = unwrap(dict_array)

	for el in els:
		idx = struct.unpack('b', el[0])[0]

		models = el[1]
		element = app.get_element(idx)
		element.set_model_config(models)
	

def interfaces_removed_cb(object_path, interfaces):
	print('Removed')
	if not mesh_net:
		return

	print(object_path)
	if object_path == mesh_net[2]:
		print('Service was removed')
		app_exit()

def print_state(state):
	print('State is ', end='')
	if state == 0:
		print('OFF')
	elif state == 1:
		print('ON')
	else:
		print('UNKNOWN')
class ModTimer():
	def __init__(self):
		self.seconds = None
		self.func = None
		self.thread = None
		self.busy = False

	def _timeout_cb(self):
		self.func()
		self.busy = True
		self._schedule_timer()
		self.busy =False

	def _schedule_timer(self):
		self.thread = Timer(self.seconds, self._timeout_cb)
		self.thread.start()

	def start(self, seconds, func):
		self.func = func
		self.seconds = seconds
		if not self.busy:
			self._schedule_timer()

	def cancel(self):
		if self.thread is not None:
			self.thread.cancel()
			self.thread = None

class Application(dbus.service.Object):

	def __init__(self, bus):
		self.path = '/example'
		self.agent = None
		self.elements = []
		dbus.service.Object.__init__(self, bus, self.path)

	def set_agent(self, agent):
		self.agent = agent

	def get_path(self):
		return dbus.ObjectPath(self.path)

	def add_element(self, element):
		self.elements.append(element)

	def get_element(self, idx):
		for ele in self.elements:
			if ele.get_index() == idx:
				return ele

	def get_properties(self):
		return {
			MESH_APPLICATION_IFACE: {
				'CompanyID': dbus.UInt16(APP_COMPANY_ID),
				'ProductID': dbus.UInt16(APP_PRODUCT_ID),
				'VersionID': dbus.UInt16(APP_VERSION_ID)
			}
		}

	@dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
	def GetManagedObjects(self):
		response = {}
		response[self.path] = self.get_properties()
		response[self.agent.get_path()] = self.agent.get_properties()
		for element in self.elements:
			response[element.get_path()] = element.get_properties()
		return response

	@dbus.service.method(MESH_APPLICATION_IFACE,
					in_signature="t", out_signature="")
	def JoinComplete(self, value):
		global token
		global have_token
		global attach

		print(set_yellow('Joined mesh network with token ') +
				set_green(format(value, '016x')))

		token = value
		have_token = True

	@dbus.service.method(MESH_APPLICATION_IFACE,
					in_signature="s", out_signature="")
	def JoinFailed(self, value):
		print(set_error('JoinFailed '), value)


class Element(dbus.service.Object):
	PATH_BASE = '/example/ele'

	def __init__(self, bus, index):
		self.path = self.PATH_BASE + format(index, '02x')
		self.models = []
		self.bus = bus
		self.index = index
		dbus.service.Object.__init__(self, bus, self.path)

	def _get_sig_models(self):
		mods = []
		for model in self.models:
			opts = []
			id = model.get_id()
			vendor = model.get_vendor()
			if vendor == VENDOR_ID_NONE:
				mod = (id, opts)
				mods.append(mod)
		return mods

	def _get_v_models(self):
		mods = []
		for model in self.models:
			opts = []
			id = model.get_id()
			v = model.get_vendor()
			if v != VENDOR_ID_NONE:
				mod = (v, id, opts)
				mods.append(mod)
		return mods

	def get_properties(self):
		vendor_models = self._get_v_models()
		sig_models = self._get_sig_models()

		props = {'Index' : dbus.Byte(self.index)}
		props['Models'] = dbus.Array(sig_models, signature='(qa{sv})')
		props['VendorModels'] = dbus.Array(vendor_models,
							signature='(qqa{sv})')
		#print(props)
		return { MESH_ELEMENT_IFACE: props }

	def add_model(self, model):
		model.set_path(self.path)
		self.models.append(model)

	def get_index(self):
		return self.index

	def set_model_config(self, configs):
		for config in configs:
			mod_id = config[0]
			self.update_model_config(mod_id, config[1])

	@dbus.service.method(MESH_ELEMENT_IFACE,
					in_signature="qqvay", out_signature="")
	def MessageReceived(self, source, key, dest, data):
		print(('Message Received on Element %02x') % self.index, end='')
		print(', src=', format(source, '04x'), end='')

		if isinstance(dest, int):
			print(', dst=%04x' % dest)
		elif isinstance(dest, dbus.Array):
			dst_str = array_to_string(dest)
			print(', dst=' + dst_str)

		for model in self.models:
			model.process_message(source, dest, key, data)

	@dbus.service.method(MESH_ELEMENT_IFACE,
					in_signature="qa{sv}", out_signature="")

	def UpdateModelConfiguration(self, model_id, config):
		cfg = unwrap(config)
		print(cfg)
		self.update_model_config(model_id, cfg)

	def update_model_config(self, model_id, config):
		print(('Update Model Config '), end='')
		print(format(model_id, '04x'))
		for model in self.models:
			if model_id == model.get_id():
				model.set_config(config)
				return

	@dbus.service.method(MESH_ELEMENT_IFACE,
					in_signature="", out_signature="")

	def get_path(self):
		return dbus.ObjectPath(self.path)

class Model():
	def __init__(self, model_id):
		self.cmd_ops = []
		self.model_id = model_id
		self.vendor = VENDOR_ID_NONE
		self.bindings = []
		self.pub_period = 0
		self.pub_id = 0
		self.path = None
		self.timer = None

	def set_path(self, path):
		self.path = path

	def get_id(self):
		return self.model_id

	def get_vendor(self):
		return self.vendor

	def process_message(self, source, dest, key, data):
		return

	def set_publication(self, period):
		self.pub_period = period

	def send_publication(self, data):
		pub_opts = dbus.Dictionary({'Vendor' : dbus.UInt16(int('05f1',16))},signature='sv')

		print('Send publication ', end='')
		node.Publish(self.path, self.model_id, pub_opts, data,
						reply_handler=generic_reply_cb,
						error_handler=generic_error_cb)

	def send_message(self, dest, key, data):
		global send_opts

		node.Send(self.path, dest, key, send_opts, data,
						reply_handler=generic_reply_cb,
						error_handler=generic_error_cb)

	def set_config(self, config):
		if 'Bindings' in config:
			self.bindings = config.get('Bindings')
			print('Bindings: ', end='')
			print(self.bindings)
		if 'PublicationPeriod' in config:
			self.set_publication(config.get('PublicationPeriod'))
			print('Model publication period ', end='')
			print(self.pub_period, end='')
			print(' ms')
		if 'Subscriptions' in config:
			print('Model subscriptions ', end='')
			self.print_subscriptions(config.get('Subscriptions'))
			print()

	def print_subscriptions(self, subscriptions):
		for sub in subscriptions:
			if isinstance(sub, int):
				print('%04x,' % sub, end=' ')

			if isinstance(sub, list):
				label = uuid.UUID(bytes=b''.join(sub))
				print(label, ',', end=' ')

########################
# My vendor model
########################

class MyVendor(Model):
	def __init__(self, model_id):
		Model.__init__(self, model_id)
		self.vendor = 0x05F1 #!!! Linux Foundation Company ID, needs to be changed
		self.cmd_ops = { 0x8201,  # get
				 0x8202,  # set
				 0x8203,  # set unacknowledged
				 0x8204}  # status per publication

		print("My Vendor Server ")
		self.state = 0
		print_state(self.state)
		self.pub_timer = ModTimer()
		self.t_timer = ModTimer()
	

	def set_publication(self, period):

		self.pub_period = period
		print("in setting publication")
		if period == 0:
			self.pub_timer.cancel()
			return

		# We do not handle ms in this example
		if period < 1000:
			return
		
		with open('scan.txt') as f:
			lines = f.readlines()
			if len(lines) == 0:
				mainloop.quit()
				return
		
			for line in lines:
				if '[NEW]' in line:
					if line.split(' ')[3] != 'undefined':
						scanned[line.split(' ')[4][0:-1]] = line.split(' ')[3]
					else:
						for test in lines:
							if '[CHG]' in test:
								if test.split(' ')[2] == line.split(' ')[2]:
									scanned[line.split(' ')[4][0:-1]] = test.split(' ')[3][0:-1]


		if len(scanned) == 0:
			mainloop.quit()
			return
		
		print(scanned)

		self.state = json.dumps(scanned).encode('utf-8')

		self.pub_timer.start(period/1000, self.publish)

	def publish(self):
		print('Publish')
		data = struct.pack(f'>H{len(self.state)}s', 0xFFFF, self.state)
		self.send_publication(data)
	
	
	def process_message(self, source, dest, key, data):
		print("message received")
		return

########################
# Main entry
########################
def main():

	DBusGMainLoop(set_as_default=True)

	global bus
	bus = dbus.SystemBus()
	global mainloop
	global app
	global mesh_net
	global menu
	global current_menu

	if len(sys.argv) > 1 :
		set_token(sys.argv[1])

	mesh_net = dbus.Interface(bus.get_object(MESH_SERVICE_NAME,
						"/org/bluez/mesh"),
						MESH_NETWORK_IFACE)

	mesh_net.connect_to_signal('InterfacesRemoved', interfaces_removed_cb)

	app = Application(bus)

	# Provisioning agent
	if agent != None:
		app.set_agent(agent.Agent(bus))

	first_ele = Element(bus, 0x00)
	#second_ele = Element(bus, 0x01)

	print(set_yellow('Register MyVendor model on element 0'))
	first_ele.add_model(MyVendor(0x0001))
	
	#print(set_yellow('Register OnOff Client model on element 0'))
	#first_ele.add_model(OnOffClient(0x1001))
	
	#print(set_yellow('Register OnOff Client model on element 1'))
	#second_ele.add_model(OnOffClient(0x1001))

	app.add_element(first_ele)
	# app.add_element(second_ele)
	mainloop = GLib.MainLoop()

	# Provisioning...
	if agent == None:
		print(set_error('Provisioning agent not found'))
		return

	uuid = bytearray.fromhex("0a0102030405060708090A0B0C0D0E0F")
	random.shuffle(uuid)
	uuid_str = array_to_string(uuid)

	print(set_yellow('Joining with UUID ') + set_green(uuid_str))
	mesh_net.Join(app.get_path(), uuid,
		reply_handler=join_cb,
		error_handler=join_error_cb)
	

	mainloop.run()

	with open("/home/pi/project/src/token.txt") as tkfile:
		tkfile.write(f"{token}")
	
	
if __name__ == '__main__':
	main()