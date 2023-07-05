import uuid
from .contact_group import ContactGroup

def generate_random_uuid():
    return str(uuid.uuid4())

class UUIDLookup(object):
	def __init__(self):
		self._groups = dict()
		self._flows = dict()

	def add_group(self, name, uuid):
		self._groups[name] = uuid

	def add_flow(self, name, uuid):
		self._flows[name] = uuid

	def lookup_group(self, name):
		'''UUIDs are autogenerated for new groups.'''
		if not name in self._groups:
			self._groups[name] = generate_random_uuid()
		return self._groups[name]

	def lookup_flow(self, name):
		return self._flows.get(name, None)

	def all_groups(self):
		for name, uuid in self._groups.items():
			yield ContactGroup(name, uuid)