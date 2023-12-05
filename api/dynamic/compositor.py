import sys
from .. import noderegistrar
noderegistrar.register_node_types('Compositor')
from ..noderegistrar import *

from ..nodesocket import create_node_socket_subclasses_for_annotations, CompositorNodeSocket
create_node_socket_subclasses_for_annotations(CompositorNodeSocket,sys.modules[__name__])