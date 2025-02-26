class ContactGroup(object):
    """Represents a RapidPro contact group

    Attributes:
        name: group name
        uuid: group uuid
    """

    def __init__(self, name, uuid=None):
        self.name = name
        self.uuid = uuid

    def __eq__(self, other):
        if isinstance(other, ContactGroup):
            return self.name == self.uuid and other.name == other.uuid
        return False

    def to_json_group(self):
        """Return corresponding json object for use in RapidPro file."""

        return {
            "uuid": self.uuid,
            "name": self.name,
            "query": None,
        }
