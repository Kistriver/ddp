# -*- coding: utf-8 -*-
__author__ = "Kachalov Alexey"
__version__ = '2.1'

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
    __version__ = 2

    T_BINARY = 0
    T_INTEGER = 1
    T_NEGATIVE_INTEGER = 2
    T_FLOAT = 3
    T_COMPLEX = 4
    T_STRING = 5
    T_BOOLEAN_FALSE = 6
    T_BOOLEAN_TRUE = 7
    T_NULL = 8
    T_MAP = 9
    T_ARRAY = 10
    T_RESERVED_11 = 11
    T_RESERVED_12 = 12
    T_RESERVED_13 = 13
    T_RESERVED_14 = 14
    T_RESERVED_15 = 15

    KEY_T_ALLOW = [T_BINARY, T_INTEGER, T_NEGATIVE_INTEGER, T_COMPLEX,
                   T_FLOAT, T_STRING, T_BOOLEAN_FALSE, T_BOOLEAN_TRUE, T_NULL]

    def __init__(self):
        pass

    @classmethod
    def encode(cls, data, version=True):
        v = bytes(0)
        if version:
            v = cls._int_pack((0b0 << 7) + (cls.__version__ & 0b01111111))
        t, d = cls._encode(data)
        if len(d) == 0:
            ld = d = bytes(0)
            lld = bytes([0])
        else:
            ld = cls._encode(len(d))[1]
            lld = cls._encode(len(ld))[1]

        ts = (0b1 << 7) + ((t & 0b00001111) << 3) + (lld[0] & 0b00000111)
        """
        (HVVV VVVV)(HTTT TSSS)<L><D>
        H - Is it header byte (1 bit)  > |
        V - Version (7 bits)           > | (1 byte)
        H - Is it header byte (1 bit)  > |
        T - Type (4 bits)              > |
        S - Size of L (3 bits)         > | (1 byte)
        L - Lengths of D (`S` bytes)
        D - Data (`L` bytes) (max size of data is 2**(8*(2**3 - 1)) - 1 = 65536 TB)
        """
        return v + bytes([ts]) + ld + d

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
        elif isinstance(data, complex):
            t = cls.T_COMPLEX
            d = cls.encode(data.real, version=False) + \
                cls.encode(data.imag, version=False)
        elif isinstance(data, bool):
            if data:
                t = cls.T_BOOLEAN_TRUE
            else:
                t = cls.T_BOOLEAN_FALSE
            d = bytes(0)
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
                d += cls.encode(k, version=False) + \
                     cls.encode(v, version=False)
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
    def _decode(cls, data):
        v, t, d, ost = cls._decode_headers(data)

        if t == cls.T_BINARY:
            d = d
        elif t == cls.T_FLOAT:
            d = float(d)
        elif t == cls.T_COMPLEX:
            real, d, _ = cls._decode(d)
            imag, _, _ = cls._decode(d)
            d = complex(real, imag)
        elif t == cls.T_INTEGER:
            d = cls._int_unpack(d)
        elif t == cls.T_NEGATIVE_INTEGER:
            d = -cls._int_unpack(d)
        elif t == cls.T_BOOLEAN_FALSE:
            d = False
        elif t == cls.T_BOOLEAN_TRUE:
            d = True
        elif t == cls.T_NULL:
            d = None
        elif t == cls.T_STRING:
            d = d.decode("utf-8")
        elif t == cls.T_MAP:
            osti = d
            d = {}
            while len(osti) > 0:
                ki, osti, ti = cls._decode(osti)
                if ti not in cls.KEY_T_ALLOW:
                    raise KeyException(
                        "Key type not allowed: type(%s) value(%s)" %
                        (hex(ti[0]), repr(ki)))
                vi, osti, ti = cls._decode(osti)
                d[ki] = vi
        elif t == cls.T_ARRAY:
            osti = d
            d = []
            while len(osti) > 0:
                di, osti, ti = cls._decode(osti)
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
        supv = [2]
        if version not in supv:
            raise VersionException(
                "Version %i is not compatible with %i" %
                (cls.__version__, version))

    @classmethod
    def _decode_version(cls, data):
        if isinstance(data, int):
            data = bytes([data])

        # version
        v = (data[0] & 0b10000000) >> 7
        if v == 0:
            # version
            v = cls._int_unpack(bytes([data[0] & 0b01111111]))
            cls.supported(v)
            return v
        else:
            return None

    @classmethod
    def _decode_header(cls, data):
        if isinstance(data, int):
            data = bytes([data])

        # type
        t = (data[0] & 0b01111000) >> 3
        # length length
        ll = cls._int_unpack(bytes([data[0] & 0b00000111]))
        return t, ll

    @classmethod
    def _decode_length(cls, data, ll):
        if isinstance(data, int):
            data = bytes([data])

        # length
        l = data[:ll]
        if isinstance(l, int):
            l = bytes([l])
        l = cls._int_unpack(l)
        return l

    @classmethod
    def _decode_data(cls, data, l):
        d = data[:l]
        ost = data[l:]
        return d, ost

    @classmethod
    def _decode_headers(cls, data):
        i = 0
        v = cls._decode_version(data[i])
        if v is None:
            t, ll = cls._decode_header(data[i])
        else:
            i += 1
            t, ll = cls._decode_header(data[i])

        i += 1
        l = cls._decode_length(data[i:], ll)
        i += ll
        d, ost = cls._decode_data(data[i:], l)
        return v, t, d, ost


class DdpSocket(Ddp):
    @classmethod
    def decode(cls, data, ost=False):
        if ost:
            return cls._decode(data)[0:1]
        else:
            return cls._decode(data)[0]

    @classmethod
    def _decode_headers(cls, socket):
        if isinstance(socket, bytes):
            return super()._decode_headers(socket)

        h = socket.recv(1)
        v = cls._decode_version(h)
        if v is None:
            t, ll = cls._decode_header(h)
        else:
            t, ll = cls._decode_header(socket.recv(1))

        l = cls._decode_length(socket.recv(ll), ll)
        d, ost = cls._decode_data(socket.recv(l), l)
        return v, t, d, ost

    @classmethod
    def encode(cls, data, version=True, socket=None):
        d = super().encode(data, version)
        if socket:
            socket.send(d)

        return d