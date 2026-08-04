class DotDict(dict):
    """dict를 dot(.)으로 접근할 수 있게 하는 래퍼 클래스"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__