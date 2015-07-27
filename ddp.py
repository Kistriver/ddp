# -*- coding: utf-8 -*-
__author__ = "Kachalov Alexey"
__version__ = 1

import logging


class DdpException(Exception):
    pass


class KeyException(DdpException):
    pass


class TypeException(DdpException):
    pass


class VersionException(DdpException):
    pass


class Ddp(object):
    __version__ = 1

    T_BINARY = bytes([0])
    T_INTEGER = bytes([1])
    T_NEGATIVE_INTEGER = bytes([2])
    T_FLOAT = bytes([3])
    T_STRING = bytes([4])
    T_BOOLEAN = bytes([5])
    T_NULL = bytes([6])
    T_MAP = bytes([7])
    T_ARRAY = bytes([8])

    KEY_T_ALLOW = [T_BINARY, T_INTEGER, T_NEGATIVE_INTEGER, T_FLOAT, T_STRING, T_BOOLEAN, T_NULL]

    def __init__(self):
        pass

    @classmethod
    def encode(cls, data, version=True):
        v = bytes(0)
        if version:
            v = cls._int_pack(cls.__version__)
        t, d = cls._encode(data)
        ld = cls._encode(len(d))[1]
        lld = cls._encode(len(ld))[1]
        """
        VTSLD
        V - Version (1 byte)
        T - Type (1 byte)
        S - Size of L (1 byte)
        L - Lengths of D (`S` bytes)
        D - Data (`L` bytes)
        """
        return v + t + lld + ld + d

    @classmethod
    def _encode(cls, data):
        if isinstance(data, (tuple, set)):
            data = list(data)

        if isinstance(data, bytes):
            t = cls.T_BINARY
            d = data
        elif isinstance(data, float):
            t = cls.T_FLOAT
            d = str(data).encode()
        elif isinstance(data, bool):
            t = cls.T_BOOLEAN
            d = bytes([data])
        elif isinstance(data, int):
            if data >= 0:
                t = cls.T_INTEGER
                d = cls._int_pack(data)
            else:
                t = cls.T_NEGATIVE_INTEGER
                d = cls._int_pack(-data)
        elif data is None:
            t = cls.T_NULL
            d = bytes(0)
        elif isinstance(data, str):
            t = cls.T_STRING
            d = data.encode("utf-8")
        elif isinstance(data, dict):
            t = cls.T_MAP
            d = bytes(0)
            for k, v in data.items():
                d += cls.encode(k, version=False) + cls.encode(v, version=False)
        elif isinstance(data, list):
            t = cls.T_ARRAY
            d = bytes(0)
            for di in data:
                d += cls.encode(di, version=False)
        else:
            raise TypeException("Not supported: %s" % repr(data))

        return t, d

    @classmethod
    def decode(cls, data, ost=False):
        if not isinstance(data, bytes):
            raise TypeException("Not bytes")

        if ost:
            return cls._decode(data)[0:1]
        else:
            return cls._decode(data)[0]

    @classmethod
    def _decode(cls, data, version=True):
        i = 0
        if version:
            # version
            v = cls._int_unpack(bytes([data[i]]))
            i += 1
            cls.supported(v)
        # type
        t = bytes([data[i]])
        i += 1
        # length length
        ll = cls._int_unpack(bytes([data[i]]))
        i += 1
        # length
        l = data[i:i + ll]
        if isinstance(l, int):
            l = bytes([l])
        l = cls._int_unpack(l)

        d = data[i + ll:i + ll + l]
        ost = data[i + ll + l:]
        if t == cls.T_BINARY:
            d = d
        elif t == cls.T_FLOAT:
            d = float(d)
        elif t == cls.T_INTEGER:
            d = cls._int_unpack(d)
        elif t == cls.T_NEGATIVE_INTEGER:
            d = -cls._int_unpack(d)
        elif t == cls.T_BOOLEAN:
            if d == bytes([0]):
                d = False
            else:
                d = True
        elif t == cls.T_NULL:
            d = None
        elif t == cls.T_STRING:
            d = d.decode("utf-8")
        elif t == cls.T_MAP:
            osti = d
            d = {}
            while len(osti) > 0:
                ki, osti, ti = cls._decode(osti, version=False)
                if ti not in cls.KEY_T_ALLOW:
                    raise KeyException("Key type not allowed: type(%s) value(%s)" % (hex(ti[0]), repr(ki)))
                vi, osti, ti = cls._decode(osti, version=False)
                d[ki] = vi
        elif t == cls.T_ARRAY:
            osti = d
            d = []
            while len(osti) > 0:
                di, osti, ti = cls._decode(osti, version=False)
                d.append(di)
        else:
            raise TypeException("Not supported: %s" % hex(t))

        return d, ost, t

    @staticmethod
    def _int_pack(n):
        bs = bytes(0)

        if n == 0:
            return bytes([0])

        while n > 0:
            bs = bytes([n % 256]) + bs
            n //= 256

        return bs

    @staticmethod
    def _int_unpack(bs):
        n = 0
        for b in bs:
            n *= 10**8
            n += int(bin(b)[2:])

        return int(str(n), 2)

    @classmethod
    def supported(cls, version):
        supv = [1]
        if version not in supv:
            raise VersionException("Version %i is not compatible with %i" % (cls.__version__, version))
