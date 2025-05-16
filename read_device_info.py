#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException, ModbusException
from pymodbus.pdu import ExceptionResponse

_LOGGER = logging.getLogger(__name__)


def read_device_list(host: str, port: int = 502, slave: int = 1, timeout: float = 3.0):
    """
    Liest per ReadDevId=3 (Function 0x2B), ObjectID=0x87 alle Subgeräte-Infos.
    Führt Paging durch, bis keine weiteren Pakete folgen.

    Args:
      host: IP oder Hostname des Modbus-TCP-Geräts
      port: TCP-Port (Standard 502)
      slave: Master-Slave-ID für ReadDevId
      timeout: Timeout in Sekunden

    Returns:
      Tuple[num_devices (int), info_dict (dict[int, bytes])] - Anzahl Geräte und rohes Bytes pro ObjectID
    """
    client = ModbusTcpClient(host, port=port, timeout=timeout)
    if not client.connect():
        raise ConnectionError(f"Verbindung zu {host}:{port} fehlgeschlagen")
    try:
        _LOGGER.debug("Lese Device List (OID=0x87)…")
        all_info = {}
        object_id = 0x87

        while True:
            try:
                resp = client.read_device_information(
                    read_code=3,
                    object_id=object_id,
                    slave=slave
                )
            except ModbusIOException as e:
                raise ConnectionError(f"Keine Antwort für OID=0x{object_id:02X}: {e}")

            if isinstance(resp, ExceptionResponse) or resp.isError():
                raise ModbusException(f"Modbus-Error bei OID=0x{object_id:02X}: {resp}")

            all_info.update(resp.information)

            if getattr(resp, "more_follows", False):
                object_id = resp.next_object_id
                _LOGGER.debug(f"Paging: weitere Daten ab OID=0x{object_id:02X}")
                continue
            break

        raw_count = all_info.get(0x87)
        if raw_count is None:
            raise ValueError("Antwort enthält keine Objekt-ID 0x87")
        num_devices = int.from_bytes(raw_count, byteorder='big')
        return num_devices, all_info
    finally:
        client.close()


def parse_device_description(desc_bytes: bytes) -> dict[int, str]:
    """
    Wandelt ein Byte-Paket in einen ASCII-String um und parsed
    '1=EMMA-A02;2=V100R024;...' in ein Dict {attr_id: value}.

    Args:
      desc_bytes: Rohbytes der Beschreibung

    Returns:
      Dict[int, str]: Attribut-IDs als Keys, Werte als Strings
    """
    desc_str = desc_bytes.decode('ascii', errors='ignore').rstrip('\x00')
    attrs = {}
    for pair in desc_str.split(';'):
        if '=' not in pair:
            continue
        k, v = pair.split('=', 1)
        try:
            attrs[int(k)] = v
        except ValueError:
            _LOGGER.debug(f"Unbekannter Schlüssel {k} in Beschreibung: {v}")
    return attrs


def identify_subdevices(host: str, port: int = 502, master_slave: int = 1, timeout: float = 3.0) -> list[dict]:
    """
    Identifiziert alle Sub-Devices vom Typ 'CHARGER' und liefert eine Liste von Dicts.

    Jeder Dict enthält:
      obj_id (int)
      attrs (dict[int, str])
      slave_id (int)
    """
    count, info = read_device_list(host, port, master_slave, timeout)
    _LOGGER.info(f"Gefundene Geräte insgesamt: {count}")
    chargers = []

    for oid, raw in info.items():
        if oid == 0x87:
            continue
        attrs = parse_device_description(raw)
        if attrs.get(8, "").upper() == "CHARGER":
            sid_val = attrs.get(5)
            try:
                sid = int(sid_val)
            except (TypeError, ValueError):
                _LOGGER.warning(f"Ungültige Slave-ID in OID=0x{oid:02X}: {sid_val}")
                continue
            chargers.append({"obj_id": oid, "attrs": attrs, "slave_id": sid})
            _LOGGER.info(f"Charger gefunden: OID=0x{oid:02X}, Slave ID={sid}")

    if not chargers:
        _LOGGER.warning("Kein CHARGER-Sub-Device gefunden.")
    return chargers
