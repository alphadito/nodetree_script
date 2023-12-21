from ..state import State
def scripted_expression(scripted_expression: str) -> 'NodeSocket':
    value_node = State.current_node_tree.new_node(State.NodeSocket.type_to_node[float][0].__name__)
    fcurve = value_node.outputs[0].driver_add("default_value")
    fcurve.driver.expression = scripted_expression
    return State.NodeSocket.create(value_node.outputs[0])