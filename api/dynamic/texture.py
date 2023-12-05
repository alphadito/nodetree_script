import sys
from .. import noderegistrar
noderegistrar.register_node_types('Texture')
from ..noderegistrar import *

from ..nodesocket import create_node_socket_subclasses_for_annotations, TextureNodeSocket
create_node_socket_subclasses_for_annotations(TextureNodeSocket, sys.modules[__name__])