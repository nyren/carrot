"""
Centralized support for encoding/decoding of data structures. 
Requires a json library (`cjson`_, `simplejson`_, or `Python 2.6+`_). 

Optionally installs support for ``Hessian 1.0`` and ``YAML`` if the necessary
libraries are installed (`HessianPy`_ and `PyYAML`_, respectively).

.. _`cjson`: http://pypi.python.org/pypi/python-cjson/
.. _`simplejson`: http://code.google.com/p/simplejson/
.. _`Python 2.6+`: http://docs.python.org/library/json.html
.. _`HessianPy`: http://hessianpy.sourceforge.net/
.. _`PyYAML`: http://pyyaml.org/

.. attribute:: registry

    A default instance of ``SerializerRegistry``

.. method:: encode

    The :meth:`SerializerRegistry.encode` method of the default
    :attr:`registry`.

.. method:: decode

    The :meth:`SerializerRegistry.decode` method of the default 
    :attr:`registry`.

.. method:: set_default_registry

    The :meth:`SerializerRegistry.set_default_registry` method of the default
    :attr:`registry`.
"""

import codecs

__all__ = ['SerializerNotInstalled', 'registry']

class SerializerNotInstalled(StandardError):
    """Support for the requested serialization type is not installed"""


class SerializerRegistry(object):
    """The registry keeps track of serialization methods."""
    
    def __init__(self):
        self._encoders = {}
        self._decoders = {}
        self._default_encode = None
        self._default_content_type = None
        self._default_content_encoding = None

    def register(self, name, encoder, decoder, content_type, 
                 content_encoding='utf-8'):
        """
        Register a new encoder/decoder. 
        
        :param name: A convenience name for the serialization method. 
        
        :param encoder: A method that will be passed a python data structure
            and should return a string representing the serialized data. 
            If ``None``, then only a decoder will be registered. Encoding
            will not be possible.
            
        :param decoder: A method that will be passed a string representing
            serialized data and should return a python data structure. 
            If ``None``, then only an encoder will be registered. 
            Decoding will not be possible. 
            
        :param content_type: The mime-type describing the serialized
            structure. 
            
        :param content_encoding: The content encoding (character set) that
            the :param:`decoder` method will be returning. Will usually be
            ``utf-8``, ``us-ascii``, or ``binary``. 

        """
        if encoder: 
            self._encoders[name] = (content_type, content_encoding, encoder)
        if decoder:
            self._decoders[content_type] = decoder

    def set_default_serializer(self, name):
        """
        Set the default serialization method used by this library.
         
        :param name: The name of the registered serialization method. 
            For example, ``json`` (default), ``pickle``, ``yaml``, 
            or any custom methods registered using :meth:`register`.
 
        :raises SerializerNotInstalled: If the serialization method
            requested is not available.
        """
        try:
            (self._default_content_type, self._default_content_encoding, 
             self._default_encode) = self._encoders[name]
        except KeyError: 
            raise SerializerNotInstalled(
                "No encoder installed for %s" % name)

    def encode(self, data, serializer=None):
        """
        Serialize a data structure into a string suitable for sending
        as an AMQP message body. 
        
        :param data: The message data to send. Can be a list,
            dictionary or a string.

        :keyword serializer: An optional string representing
            the serialization method you want the data marshalled 
            into. (For example, ``json``, ``raw``, or ``pickle``).
            
            If ``None`` (default), then the serialization method
            set by ``set_default_serializer`` will be used, unless 
            ``data`` is a ``str`` or ``unicode`` object. In this 
            latter case, no serialization occurs as it would be 
            unnecessary.
            
            Note that if ``serializer`` is specified, then that
            serialization method will be used even if a ``str``
            or ``unicode`` object is passed in.
        
        :returns: A three-item tuple containing the content type 
            (e.g., ``application/json``), content encoding, (e.g., 
            ``utf-8``) and a string containing the serialized
            data.

        :raises SerializerNotInstalled: If the serialization method
              requested is not available. 
        """
        # If a raw string was sent, assume binary encoding 
        # (it's likely either ASCII or a raw binary file, but 'binary' 
        # charset will encompass both, even if not ideal.
        if isinstance(data, str) and not serializer:
            # In Python 3+, this would be "bytes"; allow binary data to be 
            # sent as a message without getting encoder errors
            content_type = 'application/data'
            content_encoding = 'binary'
            payload = data

        # For unicode objects, force it into a string
        elif isinstance(data, unicode) and not serializer: 
            content_type = 'text/plain'
            content_encoding = 'utf-8'
            payload = data.encode(content_encoding)

        # Special case serializer
        elif serializer == 'raw': 
            content_type = 'application/data'
            payload = data
            if isinstance(payload, unicode): 
                content_encoding = 'utf-8'
                payload = payload.encode(content_encoding)
            else:
                content_encoding = 'binary'
                
        else:
            if serializer: 
                try:
                    (content_type, content_encoding, 
                     encoder) = self._encoders[serializer]
                except KeyError: 
                    raise SerializerNotInstalled(
                        "No encoder installed for %s" % serializer)
            else:
                encoder = self._default_encode
                content_type = self._default_content_type
                content_encoding = self._default_content_encoding
            payload = encoder(data)

        return (content_type, content_encoding, payload)

    def decode(self, data, content_type, content_encoding):
        """
        Deserialize a data stream as serialized using ``encode`` 
        based on :param:`content_type`. 
        
        :param data: The message data to deserialize. 

        :param content_type: The content-type of the data.
            (e.g., ``application/json``).
            
        :param content_encoding: The content-encoding of the data.
            (e.g., ``utf-8``, ``binary``, or ``us-ascii``).

        :returns: The unserialized data. 
        """
        content_type = content_type or 'application/data'
        content_encoding = (content_encoding or 'utf-8').lower()

        # Don't decode 8-bit strings
        if content_encoding not in ('binary','ascii-8bit'):
            data = codecs.decode(data, content_encoding)

        try:
            decoder = self._decoders[content_type]
        except KeyError: 
            return data
            
        return decoder(data)


"""
.. data:: registry

Global registry of serializers/deserializers.

"""
registry = SerializerRegistry()

"""
.. function:: encode(data, serializer=default_serializer)

Encode data using the registry's default encoder.

"""
encode = registry.encode

"""
.. function:: decode(data, content_type, content_encoding):

Decode data using the registry's default decoder.

"""
decode = registry.decode

"""
.. function:: set_default_serializer(name)

Change the registry's default serializer.

"""
set_default_serializer = registry.set_default_serializer

def register_json():
    """Register a encoder/decoder for JSON serialization."""
    
    # Try to import a module that provides json parsing and emitting, starting
    # with the fastest alternative and falling back to the slower ones.
    try:
        # cjson is the fastest
        import cjson
        json_serialize = cjson.encode
        json_deserialize = cjson.decode
    except ImportError:
        try:
            # Then try to find simplejson. Later versions has C speedups which
            # makes it pretty fast.
            import simplejson
            json_serialize = simplejson.dumps
            json_deserialize = simplejson.loads
        except ImportError:
            try:
                # Then try to find the python 2.6 stdlib json module.
                import json
                json_serialize = json.dumps
                json_deserialize = json.loads
            except ImportError:
                # If all of the above fails, fallback to the simplejson
                # embedded in Django.
                from django.utils import simplejson
                json_serialize = simplejson.dumps
                json_deserialize = simplejson.loads

    registry.register('json', json_serialize, json_deserialize, 
                      content_type='application/json', 
                      content_encoding='utf-8')


# def register_hessian():
#     """Register a encoder/decoder for HessianPy-based serialization"""
# 
#     try:
#         from hessian import hessian
#     
#         def h_encode(body):
#             sio = StringIO()
#             hessian.Reply().write(
#                           hessian.WriteContext(sio),
#                           ({}, '', body))
#             return sio.getvalue()
#         
#         def h_decode(body):
#             payload = StringIO(body)
#             ctx = hessian.ParseContext(payload)
#             (method, headers, params) = hessian.Call().read(ctx, ctx.read(1))
#             print (method, headers, params)
#             return params
# 
#         registry.register('hessian', h_encode, h_decode, 
#                           content_type='application/x-hessian', 
#                           content_encoding='binary')
#     except ImportError: 
#         def not_available(*args, **kwargs):
#             raise SerializerNotInstalled(
#                 "No decoder installed for Hessian. "
#                 "Install the HessianPy library")
#         registry.register('hessian', None, not_available, 
#                           'application/x-hessian')


def register_yaml():
    """Register a encoder/decoder for YAML serialization.
    It is slower than JSON, but allows for more data types
    to be serialized. Useful if you need to send data such as
    dates"""
    try:
        import yaml
        registry.register('yaml', yaml.safe_dump, yaml.safe_load, 
                          content_type='application/x-yaml', 
                          content_encoding='utf-8')
    except ImportError:
        def not_available(*args, **kwargs):
            """
            In case a client receives a yaml message, but yaml 
            isn't installed.
            """
            raise SerializerNotInstalled(
                "No decoder installed for YAML. Install the PyYAML library")
        registry.register('yaml', None, not_available, 'application/x-yaml')


def register_pickle():
    """The fastest serialization method, but restricts 
    you to python clients."""
    import cPickle
    registry.register('pickle', cPickle.dumps, cPickle.loads, 
                      content_type='application/x-python-serialize', 
                      content_encoding='binary')


# Register the base serialization methods.
register_json()
register_pickle()
register_yaml()
#register_hessian()

# JSON is assumed to always be available, so is the default.
# (this matches the historical use of carrot.)
registry.set_default_serializer('json')

