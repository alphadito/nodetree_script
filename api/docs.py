import os
from ..absolute_path import absolute_path
from .nodesocket import NodeSocket
import bpy
import glob

class Docs():
    def __init__(self, node_registrar,node_tree_type):
        self.nr = node_registrar
        self.nr.node_infos = sorted( self.nr.node_infos, key= lambda x: x.func_name )
        self.node_tree_type = node_tree_type

    def create_documentation(self):
        self.augment_node_info()
        self.write_typeshed()
        self.write_docs()

    def augment_node_info(self):
        for node_info in self.nr.node_infos:
            version = '.'.join([str(i) for i in bpy.app.version[:2]])
            img_prefix = 'compositing_' if self.node_tree_type == 'Compositor' else ''

            node_info.image = f"https://docs.blender.org/manual/en/{version}/_images/{img_prefix}node-types_{node_info.type.__name__}"
            node_info.link = f"https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/None/{node_info.func_name}.html"
            node_info.typesig = Docs.make_type_signature(node_info.default_value,union_func=lambda x: x +' | None = None')

    @staticmethod
    def make_type_signature(default_value,argdelim=', ',type_func=lambda x: x,union_func=lambda x: x):
        union_types = {}
        for argname, types in default_value.items():
            type_variants = []
            for typename, default_value_list in types.items():
                count = len(default_value_list)
                for i in range(1, count + 1):
                    composite_type = ""
                    if i > 1:
                        composite_type += "Tuple["
                    composite_type += ', '.join([type_func(typename)]*i)
                    if i > 1:
                        composite_type += "]"
                    type_variants.append( composite_type )
            union_types[argname] = union_func( ' | '.join( type_variants ) )

        return '(' + argdelim.join([f"{argname}: {union_type}" for argname, union_type in union_types.items()]) + ')'

    def write_typeshed(self):
        folders = 'typeshed/nodetree_script/api/dynamic'
        os.makedirs( absolute_path(folders), exist_ok=True )
        path = absolute_path( f"{folders}/{self.node_tree_type.lower()}.py" )
        contents = []
        with open(path, 'w') as fpy, open(path+'i', 'w') as fpyi:
            contents.append(self.import_string() )
            contents.append(self.enums())
            contents.append(self.node_funcs())
            contents.append(self.math_funcs())

            contents = ''.join(contents)
            fpy.write(contents)
            fpyi.write(contents)

        path = absolute_path( f"typeshed/nodetree_script/__init__.py" )
        contents = []
        with open(path,'w') as fpy, open(path+'i', 'w') as fpyi:
            contents.append(self.py_files())
            contents.append(self.node_socket_subclasses())

            contents = ''.join(contents)
            fpy.write(contents)
            fpyi.write(contents)

    def import_string(self):
        return f"""import enum\n"""

    def enums(self):
        lines = []
        for node_namespace, enums in self.nr.enums.items():
            if len(enums) == 0:
                continue
            lines.append( f"class {node_namespace}:\n")
            for e in enums:
                lines.append(f"  class {e.__name__}(enum.Enum):\n")
                for name, value in e.__members__.items():
                    lines.append(f"    {name} = '{value.name}'\n")
        return ''.join(lines)

    def node_funcs(self,indent="",add_self_arg=False):
        functions = []
        for node_info in self.nr.node_infos:
            return_type_hint = list(node_info.outputs.values())[0] if len(node_info.outputs) == 1 else f"{node_info.namespace}.Result"
            signature = '(self, '+node_info.typesig[1:] if add_self_arg else node_info.typesig
            functions.append( f'{indent}def {node_info.func_name}{signature} -> {return_type_hint}: """![]({node_info.image}.webp)"""\n' )
        return ''.join(functions)

    def math_funcs(self):
        return ''.join([f'def {func}(*vectors_or_values): pass\n' for func in self.nr.math_funcs])

    def py_files(self):
        def folder_glob(*args):
            return glob.glob( absolute_path(os.path.join(*args,'**','*.py')  ),recursive=True )
        py_files = folder_glob()
        excluded_files = folder_glob('api','dynamic') + folder_glob('typeshed') + folder_glob('examples') + [ absolute_path('__init__.py') ]
        contents = "".join(
            f"# {os.path.basename(path)}\n{open(path).read()}\n\n"
            for path in py_files if path not in excluded_files
        )
        contents = "\n".join( [ line for line in contents.split('\n') if not( line.startswith('from') or line.startswith('import') ) ] )
        return contents

    def node_socket_subclasses(self):
        return '\n'.join([ f"class {subclass.__name__}({NodeSocket.__name__}): pass" for subclass in NodeSocket.__subclasses__() ]) + '\n'

    def write_docs(self):
        joined_docs = ''.join([self.doc_string(node_info) for node_info in self.nr.node_infos])
        html = f"""
        <html>
        <head>
        <style>
            html {{
                background-color: #1D1D1D;
                color: #FFFFFF;
            }}
            a {{
                color: #4772B3;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
                max-width: 60em;
                margin: 0 auto;
            }}
            pre {{
                overflow: scroll;
                padding: 16px;
                background-color: #303030;
                border-radius: 5px;
            }}
        </style>
        </head>
        <body>
        <h1>{self.node_tree_type} Script</h1>
        <h3>Nodes</h3>
        {joined_docs}
        </body>
        </html>
        """
        path = absolute_path( f"docs/{self.node_tree_type.lower()}_documentation.html" )
        with open(path, 'w') as f:
            f.write(html)

    def doc_string(self,node_info):
        color_mappings = {
        'INT': '#598C5C',
        'FLOAT': '#A1A1A1',
        'BOOLEAN': '#CCA6D6',
        'GEOMETRY': '#00D6A3',
        'VALUE': '#A1A1A1',
        'VECTOR': '#6363C7',
        'MATERIAL': '#EB7582',
        'TEXTURE': '#9E4FA3',
        'COLLECTION': '#F5F5F5',
        'OBJECT': '#ED9E5C',
        'STRING': '#70B2FF',
        'RGBA': '#C7C729',
        'IMAGE': '#633863',
        'SHADER': '#63c763',
        'ROTATION':'#A663C7',
        }
        default_color = '#A1A1A1'
        def color_style(type):
            is_enum = lambda x: x.find('.') != -1
            if is_enum(type):
                color = color_mappings['STRING']
            else:
                enum_socket_type = self.nr.enum_socket_type.get('NodeSocket'+type,type.upper())
                color = color_mappings.get(enum_socket_type,default_color)

            return f"<span style='color:{color}'>{type}</span>"

        output_doc = '{ ' + ', '.join([ f'{outputname}: {color_style(type)}' for outputname,type in node_info.outputs.items() ]) + ' }'
        def primary_arg_doc(node_info):
            return f"""
            <h4>Chain Syntax</h4>
            <pre><code>{node_info.primary_arg['argname']}: { color_style(node_info.primary_arg['typename'])} = ...\n{node_info.primary_arg['argname']}.{node_info.func_name}(...)</code></pre>
            """

        argdelim=',\n  '
        return f"""
            <details style="margin: 10px 0;">
                <summary><code>{node_info.func_name}</code> - <a href="{node_info.link}">{node_info.type.bl_rna.name}</a></summary>
                <div style="margin-top: 5px;">
                    <img src="{node_info.image}.webp" onerror="if (this.src != '{node_info.image}.png') this.src = '{node_info.image}.png'" />
                    <h4>Signature</h4>
                    <pre><code>{node_info.func_name}(\n  {Docs.make_type_signature(node_info.default_value,argdelim=argdelim,type_func=color_style)[1:-1]}\n)</code></pre>
                    <h4>Result</h4>
                    <pre><code>{output_doc}</code></pre>
                    {primary_arg_doc(node_info) if node_info.primary_arg is not None else ""}
                </div>
            </details>
            """



