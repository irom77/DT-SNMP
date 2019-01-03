import logging
from .poller import Poller

logger = logging.getLogger(__name__)

class HostResourceMIB():
	"""
	Metric processing for Host-Resouce-Mib
	Host infrastructure statistics

	This is supported by most device types 

	Reference
	http://www.net-snmp.org/docs/mibs/host.html

	Usage
	hr_mib = HostResourceMIB(device, authentication)
	host_metrics = hr_mib.poll_metrics()

	Returns a dictionary containing values for:
	cpu, memory, disk

	TODO implement disk splits
	"""

	mib_name = 'HOST-RESOURCES-MIB'

	def __init__(self, device, authentication):
		self.poller = Poller(device, authentication)

	def poll_metrics(self):
		cpu = self._poll_cpu()
		storage = self._poll_storage()

		average_cpu = cpu.get('cpu', [])
		memory = storage.get('memory', [])
		disk = storage.get('disk', [])

		metrics = {
			'cpu_utilisation': average_cpu,
			'memory_utilisation': memory,
			'disk_utilisation': disk
		}
		return metrics

	def _poll_cpu(self):
		cpu_metrics = [
		    'hrProcessorLoad',
		]
		oids = [(self.mib_name, metric) for metric in cpu_metrics]
		gen = self.poller.snmp_connect_bulk(oids)
		return self.poller.process_metrics(gen, calculate_cpu_metrics)

	def _poll_storage(self):
		storage_metrics = [
		    'hrStorageDescr',
		    'hrStorageSize',
		    'hrStorageUsed',
		]
		oids = [(self.mib_name, metric) for metric in storage_metrics]
		gen = self.poller.snmp_connect_bulk(oids)
		return self.poller.process_metrics(gen, calculate_storage_metrics)

def calculate_cpu_metrics(index, varBinds, metrics):
	cpu = {}
	for key,val in varBinds:
		cpu['value'] = float(val)

	cpu['dimension'] = {'Index': index}
	cpu['is_absolute_number'] = True

	metrics.setdefault('cpu', []).append(cpu)

def calculate_storage_metrics(index, varBinds, metrics):
	memory_types = ['memory', 'swap space', 'ram']
	name = ''
	for varBind in varBinds:
		name = varBinds[0][1].prettyPrint()
		size = float(varBinds[1][1])
		used = float(varBinds[2][1])
		utilisation = 0
		# Division by 0 excpetion - e.g. Swap Space 0 used of 0
		if size > 0:
			utilisation = (used / size)*100
		storage = {}
		storage['dimension'] = {'Storage': name}
		storage['value'] = utilisation
		storage['is_absolute_number'] = True

	# Memory metrics as a dimension under memory_utilisation
	if any(x in name.lower() for x in memory_types):
		metrics.setdefault('memory', []).append(storage)
	else:
		metrics.setdefault('disk', []).append(storage)