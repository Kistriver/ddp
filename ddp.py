# -*- coding: utf-8 -*-
__author__ = "Alexey Kachalov"
__version__ = '3.0'

import logging


class DdpException(Exception):
    pass


class KeyException(DdpException, KeyError):
    pass


class TypeException(DdpException, TypeError):
    pass


class VersionException(DdpException):
    pass


class Ddp(object):
    __version__ = 3
    _supported = [3]

    T_BINARY = 0
    T_INTEGER = 1
    T_NEGATIVE_INTEGER = 2
    T_FLOAT = 3
    T_NEGATIVE_FLOAT = 4
    T_COMPLEX = 5
    T_STRING = 6
    T_BOOLEAN_FALSE = 7
    T_BOOLEAN_TRUE = 8
    T_NULL = 9
    T_MAP = 10
    T_ARRAY = 11
    T_RESERVED_12 = 12
    T_RESERVED_13 = 13
    T_RESERVED_14 = 14
    T_RESERVED_15 = 15

    KEY_T_ALLOW = [T_BINARY, T_INTEGER, T_NEGATIVE_INTEGER, T_COMPLEX, T_FLOAT,
                   T_NEGATIVE_FLOAT, T_STRING, T_BOOLEAN_FALSE, T_BOOLEAN_TRUE, T_NULL]

    NAMES_T = ["T_BINARY", "T_INTEGER", "T_NEGATIVE_INTEGER", "T_FLOAT",
               "T_NEGATIVE_FLOAT", "T_COMPLEX", "T_STRING", "T_BOOLEAN_FALSE",
               "T_BOOLEAN_TRUE", "T_NULL", "T_MAP", "T_ARRAY", "T_RESERVED_12",
               "T_RESERVED_13", "T_RESERVED_14", "T_RESERVED_15"]

    @classmethod
    def encode(cls, data, version=True):
        """
        Encode data

        Protocol structure:
        (HVVV VVVV)(HTTT TSSS)<L><D>
        H - Is it header byte (1 bit)  > |
        V - Version (7 bits)           > | (1 byte)
        H - Is it header byte (1 bit)  > |
        T - Type (4 bits)              > |
        S - Size of L (3 bits)         > | (1 byte)
        L - Lengths of D (`S` bytes)
        D - Data (`L` bytes) (max size of data is 2**(8*(2**3 - 1)) - 1 = 65536 TB)

        :param data:
        :param version: encode version in header. Default is `True`
        :type version: bool
        :return: encoded data
        :rtype: bytes
        """
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
        logging.debug("type(%s) datalen(%i) data(%s)" %
                      (
                          cls.NAMES_T[t & 0b00001111],
                          len(d),
                          repr(data)
                      )
                      )
        return v + bytes([ts]) + ld + d

    @classmethod
    def _encode(cls, data):
        """
        Encode data

        :param data:
        :return: (type, encoded data)
        """
        if isinstance(data, (tuple, set)):
            data = list(data)

        if isinstance(data, bytes):
            t = cls.T_BINARY
            d = data
        elif isinstance(data, float):
            if data == float("inf") or data == float("-inf"):
                raise TypeException("Inf/-Inf not supported")

            if data == 0:
                t = cls.T_FLOAT
                d = bytes(0)
            elif data == -1:
                t = cls.T_NEGATIVE_FLOAT
                d = bytes(0)
            elif data > 0:
                t = cls.T_FLOAT
                data = cls._float_pack(data)
                d = cls.encode(data[0], version=False) + \
                    cls.encode(data[1], version=False)
            else:
                t = cls.T_NEGATIVE_FLOAT
                data = cls._float_pack(-data)
                d = cls.encode(data[0], version=False) + \
                    cls.encode(data[1], version=False)
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
                if data == 0:
                    d = bytes(0)
                else:
                    d = cls._int_pack(data)
            else:
                t = cls.T_NEGATIVE_INTEGER
                if data == -1:
                    d = bytes(0)
                else:
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
        """
        Decode data

        :param data:
        :type data: bytes
        :param ost: return rest of data. Default is `False`
        :type: bool
        :return:
        """
        if not isinstance(data, bytes):
            raise TypeException("Not bytes")

        if ost:
            return cls._decode(data)[0:1]
        else:
            return cls._decode(data)[0]

    @classmethod
    def _decode(cls, data):
        """
        Decode data

        :param data:
        :return: (data, rest of data, type)
        :rtype: (mixed, bytes, int)
        """
        v, t, d, ost = cls._decode_headers(data)
        logging.debug("version(%s) type(%s) datalen(%i) bytes(%s)" %
                      (
                          "-" if v is None else v,
                          cls.NAMES_T[t],
                          len(d),
                          repr(d)
                      )
                      )

        if t == cls.T_BINARY:
            pass
        elif t == cls.T_FLOAT:
            osti = d
            d = {}
            d['m'], osti, _ = cls._decode(osti)
            d['exp'], _, _ = cls._decode(osti)
            d = cls._float_unpack(**d)
        elif t == cls.T_NEGATIVE_FLOAT:
            osti = d
            d = {}
            d['m'], osti, _ = cls._decode(osti)
            d['exp'], _, _ = cls._decode(osti)
            d = -cls._float_unpack(**d)
        elif t == cls.T_COMPLEX:
            real, d, _ = cls._decode(d)
            imag, _, _ = cls._decode(d)
            d = complex(real, imag)
        elif t == cls.T_INTEGER:
            if len(d) == 0:
                d = 0
            else:
                d = cls._int_unpack(d)
        elif t == cls.T_NEGATIVE_INTEGER:
            if len(d) == 0:
                d = -1
            else:
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
                        (hex(ti), repr(ki)))
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
        """
        Pack int into bytes

        :param n: int
        :type n: int
        :return: bytes
        """
        bs = bytes(0)

        if n == 0:
            return bytes([0])

        while n > 0:
            bs = bytes([n % 2 ** 8]) + bs
            n >>= 8

        return bs

    @staticmethod
    def _int_unpack(bs):
        """
        Unpack int from bytes

        :param bs: bytes
        :type bs: bytes
        :return: int
        """
        n = 0
        for b in bs:
            n <<= 8
            n += b

        return n

    @classmethod
    def _float_pack(cls, n):
        """
        Get mantissa and exponent from float

        :param n:
        :type n: float
        :return: (integral, fractional)
        :rtype: (int, int)
        """
        import math
        m, exp = math.frexp(n)
        m = int(str(m)[2:])

        return m, exp

    @classmethod
    def _float_unpack(cls, m, exp):
        """
        Make float from mantissa and exp

        :param m: mantissa
        :type m: int
        :param exp: exponent
        :type exp: int
        :return: float
        :rtype: float
        """
        import math
        m = float("0.%i" % m)
        return math.ldexp(m, exp)

    @classmethod
    def supported(cls, version):
        """
        Check version compatibility

        :param version:
        :type version: int
        :return: None

        :raise VersionException: version is not compatible
        """
        if version not in cls._supported:
            raise VersionException(
                "Version %i is not compatible with %i" %
                (cls.__version__, version))

    @classmethod
    def _decode_version(cls, data):
        """
        Get version from data

        :param data:
        :return: version or None
        :rtype: int, None
        """
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
        """
        Get header byte from data

        :param data:
        :return: (type, size of data length)
        :rtype: (int, int)
        """
        if isinstance(data, int):
            data = bytes([data])

        # type
        t = (data[0] & 0b01111000) >> 3
        # length length
        ll = cls._int_unpack(bytes([data[0] & 0b00000111]))
        return t, ll

    @classmethod
    def _decode_length(cls, data, ll):
        """
        Get length of data

        :param data:
        :param ll: size of data length
        :type ll: int
        :return: length of data
        :rtype: int
        """
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
        """
        Get data

        :param data:
        :param l: length of data
        :type l: int
        :return: (version, type, data, rest of data)
        :rtype: (int, int, mixed, bytes)
        """
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
