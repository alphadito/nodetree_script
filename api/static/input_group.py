class InputGroup:
    prefix = ''
    @classmethod
    def __class_getitem__(cls, prefix):
        return type(f"Prefixed{cls.__name__}", (cls,), { '__annotations__':cls.__annotations__, 'prefix':prefix  })
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)