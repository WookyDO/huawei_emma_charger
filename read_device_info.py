#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException, ModbusException
from pymodbus.pdu import ExceptionResponse

_LOGGER = logging.getLogger(__name__)

def read_device_list(host: str,
                     port: int = 502,
                     slave: int = 1,
                     timeout: float = 3.0):
    """
    Liest per ReadDevId=3, ObjectID=0x87 alle Subgeräte-Infos (Paging).
    Gibt zurück: (num_devices: int, info: dict[obj_id:int, raw_bytes])
    """
    client = ModbusTcpClient(host, port=port, timeout=timeout)
    if not client.connect():
        raise ConnectionError(f"Verbindung zu {host}:{port} fehlgeschlagen")
    try:
        _LOGGER.info("Lese Device List (OID=0x87)…")
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
                _LOGGER.info(f"Paging: weitere Daten ab OID=0x{object_id:02X}")
            else:
                break

        # Anzahl Geräte (OID 0x87)
        raw_count = all_info.get(0x87)
        if raw_count is None:
            raise ValueError("Antwort enthält keine Objekt-ID 0x87")
        num_devices = int.from_bytes(raw_count, byteorder='big')
        return num_devices, all_info

    finally:
        client.close()


def parse_device_description(desc_bytes: bytes) -> dict[int, str]:
    """
    Wandelt raw_bytes in ascii-String um und parsed '1=…;2=…' in Dict.
    """
    desc_str = desc_bytes.decode('ascii', errors='ignore').rstrip('\x00')
    attrs: dict[int, str] = {}
    for pair in desc_str.split(';'):
        if '=' in pair:
            k, v = pair.split('=', 1)
            try:
                attrs[int(k)] = v
            except ValueError:
                # falls kein integer key, ignorieren oder als str speichern
                continue
    return attrs


def identify_subdevices(host: str,
                        port: int = 502,
                        master_slave: int = 1,
                        timeout: float = 3.0) -> list[dict]:
    """
    Liest alle Sub
