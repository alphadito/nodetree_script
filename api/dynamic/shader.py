import sys
from .. import noderegistrar
noderegistrar.register_node_types('Shader')
from ..noderegistrar import *

from ..nodesocket import create_node_socket_subclasses_for_annotations, ShaderNodeSocket
create_node_socket_subclasses_for_annotations(ShaderNodeSocket, sys.modules[__name__])