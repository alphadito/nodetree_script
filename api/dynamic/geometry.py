import sys
from .. import noderegistrar
noderegistrar.register_node_types('Geometry')
from ..noderegistrar import *

from ..nodesocket import create_node_socket_subclasses_for_annotations, GeometryNodeSocket
create_node_socket_subclasses_for_annotations(GeometryNodeSocket, sys.modules[__name__])