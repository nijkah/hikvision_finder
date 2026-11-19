#!/usr/bin/env python3
"""Read-only Hikvision SADP UDP discovery; Python standard library only."""
import argparse
import ipaddress
import json
import math
import platform
import re
import socket
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

GROUP = '239.255.255.250'
PORT = 37020


def normalize_mac(value):
    compact = value.replace(':', '').replace('-', '').replace('.', '')
    if not re.fullmatch(r'[0-9a-fA-F]{12}', compact):
        raise ValueError('MAC must contain 12 hexadecimal digits')
    return ':'.join(compact[i:i + 2] for i in range(0, 12, 2)).upper()


def parse_response(packet):
    # Ignore malformed/unrelated traffic, including DTD-bearing XML.
    if b'<!DOCTYPE' in packet.upper() or b'<!ENTITY' in packet.upper():
        return None
    try:
        root = ET.fromstring(packet)
        if root.tag.split('}')[-1] != 'ProbeMatch':
            return None
        fields = {e.tag.split('}')[-1]: (e.text or '').strip() for e in root}
        mac = normalize_mac(fields.get('MAC', ''))
    except (ET.ParseError, ValueError):
        return None
    def boolean(name):
        return {'true': True, 'false': False}.get(fields.get(name, '').lower())
    return {
        'mac': mac, 'ip': fields.get('IPv4Address', ''),
        'subnet_mask': fields.get('IPv4SubnetMask', ''),
        'gateway': fields.get('IPv4Gateway', ''),
        'model': fields.get('DeviceDescription', ''),
        'serial': fields.get('DeviceSN', ''),
        'http_port': fields.get('HttpPort', ''),
        'dhcp': boolean('DHCP'), 'activated': boolean('Activated'),
    }


def interface_ip(name):
    if platform.system() == 'Darwin':
        return subprocess.check_output(['ipconfig', 'getifaddr', name], text=True).strip()
    if platform.system() == 'Linux':
        result = json.loads(subprocess.check_output(
            ['ip', '-j', '-4', 'addr', 'show', 'dev', name], text=True))
        addresses = [a['local'] for item in result for a in item.get('addr_info', [])
                     if a.get('family') == 'inet']
        if addresses:
            return addresses[0]
        raise ValueError('Interface has no IPv4 address')
    raise ValueError('On this OS use --local-ip with the adapter IPv4 address')


def discover(local_ip, timeout=10, interval=3):
    devices = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', PORT))
        packed = socket.inet_aton(local_ip)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, packed)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                        socket.inet_aton(GROUP) + packed)
        deadline = time.monotonic() + timeout
        next_send = 0
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_send:
                probe = ('<?xml version="1.0" encoding="utf-8"?>'
                         f'<Probe><Uuid>{str(uuid.uuid4()).upper()}</Uuid>'
                         '<Types>inquiry</Types></Probe>').encode()
                sock.sendto(probe, (GROUP, PORT))
                next_send = now + interval
            sock.settimeout(max(0.001, min(1, deadline - time.monotonic())))
            try:
                packet, _ = sock.recvfrom(65535)
            except socket.timeout:
                continue
            device = parse_response(packet)
            if device:
                devices[device['mac']] = device
    return sorted(devices.values(), key=lambda d: (d['ip'], d['mac']))


def duplicate_ips(devices):
    grouped = {}
    for device in devices:
        if device['ip'] and device['ip'] != '0.0.0.0':
            grouped.setdefault(device['ip'], set()).add(device['mac'])
    return {ip: sorted(macs) for ip, macs in grouped.items() if len(macs) > 1}


def positive_seconds(text):
    value = float(text)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError('Must be a finite number greater than zero')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--interface', '-i', help='macOS/Linux adapter, e.g. en4 or eth0')
    source.add_argument('--local-ip', help='Your computer adapter IPv4 address, NOT the camera IP')
    parser.add_argument('--timeout', type=positive_seconds, default=10, help='Discovery seconds (default: 10)')
    parser.add_argument('--interval', type=positive_seconds, default=3, help='Probe interval seconds (default: 3)')
    parser.add_argument('--mac', help='Only display this MAC; duplicate checks still use all replies')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON')
    args = parser.parse_args()
    try:
        target = normalize_mac(args.mac) if args.mac else None
        local_ip = str(ipaddress.IPv4Address(args.local_ip or interface_ip(args.interface)))
        all_devices = discover(local_ip, args.timeout, args.interval)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        print('Check adapter IPv4, local-network/firewall permissions and UDP 37020 availability.', file=sys.stderr)
        return 2
    devices = [d for d in all_devices if not target or d['mac'] == target]
    duplicates = duplicate_ips(all_devices)
    if args.json:
        print(json.dumps({'local_ip': local_ip, 'devices': devices,
                          'duplicate_ips': duplicates}, indent=2, ensure_ascii=False))
    else:
        print(f'Adapter IPv4: {local_ip} | Responses: {len(all_devices)} | Matches: {len(devices)}')
        print(f'{"MAC":17}  {"IP":15}  {"DHCP":7}  {"ACTIVE":7}  MODEL')
        def state(value):
            return {True: 'yes', False: 'no', None: 'unknown'}[value]
        for d in devices:
            print(f'{d["mac"]:17}  {d["ip"]:15}  {state(d["dhcp"]):7}  '
                  f'{state(d["activated"]):7}  {d["model"]}')
            print(f'  Mask: {d["subnet_mask"]} | Gateway: {d["gateway"]} | '
                  f'HTTP: {d["http_port"]} | Serial: {d["serial"]}')
        for ip, macs in duplicates.items():
            print(f'DUPLICATE IP: {ip} -> {", ".join(macs)}')
        if not devices:
            print('No matching response. Check power, boot time, VLAN and multicast/firewall settings.')
    return 0 if devices else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
