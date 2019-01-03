import logging
from pysnmp.hlapi import *

logger = logging.getLogger(__name__)

class Poller():
    """
    snmp.Poller
    This module wraps the pysnmp APIs to connect to a device

    Usage
    poller = Poller(device, authentication)
    gen = poller.snmp_connect_bulk(self.oids)

    You can then iterate through the generator:
    for item in gen:
        errorIndication, errorStatus, errorIndex, varBinds = item
    """
    
    auth_protocols = {
        'md5': usmHMACMD5AuthProtocol,
        'sha': usmHMACSHAAuthProtocol,
        'sha224': usmHMAC128SHA224AuthProtocol,
        'sha256': usmHMAC192SHA256AuthProtocol,
        'sha384': usmHMAC256SHA384AuthProtocol,
        'sha512': usmHMAC384SHA512AuthProtocol,
        'noauth': usmNoAuthProtocol
    }

    priv_protocols = {
        'des': usmDESPrivProtocol,
        '3des': usm3DESEDEPrivProtocol,
        'aes': usmAesCfb128Protocol,
        'aes192': usmAesCfb192Protocol,
        'aes256': usmAesCfb256Protocol,
        'nopriv': usmNoPrivProtocol
    }

    def __init__(self, device, authentication):
        self.authentication = authentication
        self.device = device
        self._build_auth_object()

    def snmp_connect(self, oid):
        """
        Only use for old SNMP agents
        Prefer snmp_connect_bulk in all cases
        Send an snmp get request
        """
        gen = getCmd(
            SnmpEngine(),
            self.auth_object,
            UdpTransportTarget((self.device['host'], self.device['port'])),
            ContextData(),
            ObjectType(ObjectIdentity(oid)))
        return next(gen)

    def snmp_connect_bulk(self, oids):
        """
        Optimised get - supported with SNMPv2C
        Send a single getbulk request
        Supported inputs:
        String - e.g. 1.3.6.1.2.1.31.1.1.1
        Tuple - e.g. (IF-MIB, ifSpeed)
        List of Tuple - e.g. ([(IF-MIB,ifSpeed), (HOST-RESOURCES-MIB,cpu)])

        Recommended to only call with lists of OIDs from the same table
        Otherwise you can end up polling for End of MIB.
        """
        non_repeaters = 0
        max_repetitions = 25

        if (isinstance(oids, str)):
            oid_object = [ObjectType(ObjectIdentity(oids))]
        elif (isinstance(oids, tuple)):
            oid_object = [ObjectType(ObjectIdentity(*oids))]
        elif(isinstance(oids, list)): # List of Tuple
            oid_object = [ObjectType(ObjectIdentity(*oid)) for oid in oids]

        gen = bulkCmd(
            SnmpEngine(),
            self.auth_object,
            UdpTransportTarget((self.device['host'], self.device['port'])),
            ContextData(),
            non_repeaters,
            max_repetitions,             
            *oid_object,
            lexicographicMode=False)

        return gen

    def process_metrics(self, gen, processor=None):
        if not processor:
            processor = mib_print

        metrics = {}
        index = 0
        for item in gen:
            index += 1
            errorIndication, errorStatus, errorIndex, varBinds = item

            if errorIndication:
                logger.error(errorIndication)
            elif errorStatus:
                logger.error('%s at %s' % (errorStatus.prettyPrint(),
                                    errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
            else:
                processor(index=str(index), varBinds=varBinds, metrics=metrics)

        return metrics

    def _build_auth_object(self):
        authentication = self.authentication
        if (authentication['version'] == 3):
            self.auth_object = UsmUserData(
                authentication['user'],
                authentication['auth']['key'],
                authentication['priv']['key'],
                self.auth_protocols.get(authentication['auth']['protocol'], None),
                self.priv_protocols.get(authentication['priv']['protocol'], None))
        elif(authentication['version'] == 2):
            self.auth_object = CommunityData(authentication['user'], mpModel=1)
        elif(authentication['version'] == 1):
            self.auth_object = CommunityData(authentication['user'], mpModel=0)

def mib_print(index, varBinds, metrics):
    for varBind in varBinds:
        print(' = '.join([x.prettyPrint() for x in varBind]))
