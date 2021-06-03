import copy
import math

class NodesLayout(object):
    '''
    Attributes:
        layout: a dictionary keyed by node uuids, whose values give information
            how to display the node in the RapidPro UI, for example like this:
                {
                  "type": "wait_for_response",
                  "position": {
                    "left": 1040,
                    "top": 1000
                  },
                  "config": {
                    "cases": {}
                  }
                }
    '''

    # Distance between nodes so they don't overlap
    HORIZONTAL_MARGIN = 250
    VERTICAL_MARGIN = 200

    def __init__(self, layout=None):
        if layout is None:
            self._layout = dict()
        else:
            self._layout = layout

    def get_node(self, uuid):
        return self._layout.get(uuid)

    def layout(self):
        return self._layout

    def bounding_box(self):
        xmin = math.inf
        xmax = -math.inf
        ymin = math.inf
        ymax = -math.inf
        for node_layout in self._layout.values():
            xmin = min(xmin, node_layout["position"]["left"])
            xmax = max(xmax, node_layout["position"]["left"])
            ymin = min(ymin, node_layout["position"]["top"])
            ymax = max(ymax, node_layout["position"]["top"])
        return xmin, xmax, ymin, ymax

    def center(self):
        xmin, xmax, ymin, ymax = self.bounding_box()
        return (xmax+xmin)//2, (ymax+ymin)//2   

    def shift(self, xshift, yshift):
        for node_layout in self._layout.values():
            NodesLayout.shift_node_layout(node_layout, xshift, yshift)

    def shift_node_layout(node_layout, xshift, yshift):
        node_layout["position"]["left"] += xshift
        node_layout["position"]["top"] += yshift

    def normalize(self):
        '''Shift all nodes to ensure non-negative coordinates.'''

        if self._layout == dict():
            return

        xmin, xmax, ymin, ymax = self.bounding_box()
        xshift = -min(0, xmin)
        yshift = -min(0, ymin)
        self.shift(xshift, yshift)

    def insert_after(self, node_uuid, node_layout):
        '''Insert a new node with the given uuid and layout and adjust its
        position so that it comes below all the nodes in the current
        nodes layout'''

        if node_layout is None:
            return

        _, _, _, ymax = self.bounding_box()
        xcenter, _ = self.center()
        node_layout = copy.deepcopy(node_layout)
        node_layout["position"]["top"] = ymax + NodesLayout.VERTICAL_MARGIN
        node_layout["position"]["left"] = xcenter
        self._layout[node_uuid] = node_layout

    def merge(self, nodes_layout):
        '''Merge nodes_layout with this layout.

        The nodes_layout will be inserted below this layout.'''

        if self._layout == dict():
            if nodes_layout != dict():
                self._layout = nodes_layout
            return

        nodes_layout = copy.deepcopy(nodes_layout)      
        _, _, _, ymax = self.bounding_box()
        xcenter, _ = self.center()
        _, _, ymin2, _ = nodes_layout.bounding_box()
        xcenter2, _ = nodes_layout.center()
        nodes_layout.shift(xcenter - xcenter2, ymax - ymin2 + NodesLayout.VERTICAL_MARGIN)
        self._layout.update(nodes_layout._layout)


    def replace(self, node_uuid, nodes_layout):
        '''Remove the node with the given uuid from the layout and in its
        position insert the given layout of nodes.
        Other nodes in the original layout that may overlap the inserted
        nodes are shifted out of the way (using the expand method).'''

        node_layout = self.get_node(node_uuid)
        if node_layout is None:
            return

        nodes_layout = copy.deepcopy(nodes_layout)
        xcenter, ycenter = nodes_layout.center()
        xshift = node_layout["position"]["left"] - xcenter
        yshift = node_layout["position"]["top"] - ycenter
        nodes_layout.shift(xshift, yshift)
        bbox = nodes_layout.bounding_box()
        self.expand(bbox)
        self._layout.pop(node_uuid)
        self._layout.update(nodes_layout._layout)

    def expand(self, bbox):
        '''Shift all nodes to ensure they don't overlap the given bounding box'''

        xmin, xmax, ymin, ymax = bbox
        xcenter, ycenter = (xmax+xmin)//2, (ymax+ymin)//2
        for node_layout in self._layout.values():
            if node_layout["position"]["left"] < xcenter:
                node_layout["position"]["left"] -= xcenter - xmin
            else:
                node_layout["position"]["left"] += xcenter - xmin
            if node_layout["position"]["left"] < ycenter:
                node_layout["position"]["left"] -= ycenter - ymin
            else:
                node_layout["position"]["left"] += ycenter - ymin

    def from_single_node_layout(node_uuid, node_layout):
        return NodesLayout({node_uuid : node_layout})


def make_tree_layout(operand, switch_uuid, node_variations, node_layout):
    if node_layout is None:
        return NodesLayout()

    tree_layout = dict()
    for i, variation in enumerate(node_variations):
        layout = copy.deepcopy(node_layout)
        layout["position"]["left"] = NodesLayout.HORIZONTAL_MARGIN*i
        layout["position"]["top"] = NodesLayout.VERTICAL_MARGIN
        tree_layout[variation["uuid"]] = layout

    if operand == "@contact.groups":
        switch_type = "split_by_groups"
    # "wait_for_response" for @input.text?
    else:
        switch_type = "split_by_expression"

    switch_layout = {
        "type": switch_type,
        "position": {
            "left": NodesLayout.HORIZONTAL_MARGIN//2*(len(node_variations)-1),
            "top": 0
        },
        "config": {
            "cases": {}
        }
    }

    tree_layout[switch_uuid] = switch_layout
    return NodesLayout(tree_layout)


def normalize_flow_layout(flow):
    nodes_layout = NodesLayout(flow.get("_ui", dict()).get("nodes"))
    nodes_layout.normalize()
    if "_ui" in flow:
        flow["_ui"]["nodes"] = nodes_layout.layout()

