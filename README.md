# Hikvision Finder

A read-only, dependency-free Python CLI for discovering Hikvision devices on a
local network without installing the SADP application or scanning every IP address.

It sends SADP UDP discovery probes and displays device-reported MAC addresses,
IPv4 addresses, models, serial numbers, DHCP status, and activation status.

## Scope and limitations

- Supports devices that respond to Hikvision SADP UDP inquiries. This is **not a
  universal discovery protocol for all camera manufacturers**.
- The discovery approach has been verified with Hikvision cameras and PoE switches.
  Compatibility with every model and firmware version is not guaranteed.
- The computer and devices must share a local network/VLAN that permits discovery
  multicast traffic. Routers, Wi-Fi isolation, switch port isolation, firewalls, and
  private NVR PoE networks can prevent discovery.
- Devices may respond even when DHCP is disabled or they are not activated.
  Discovery does not guarantee that their web or RTSP services are reachable.
- The tool does **not** assign IP addresses, change DHCP settings, activate devices,
  set passwords, or modify your computer's ARP table.

## Requirements

- Python 3.8 or newer; no third-party Python packages.
- An IPv4 address on the network adapter connected to the devices.
- macOS supports `--interface` through `ipconfig`.
- Linux supports `--interface` through the `ip` command.
- On Windows or other platforms, use `--local-ip`.

Live device discovery has been verified on macOS. Other platforms have not been
validated with physical devices.

## Quick start (macOS)

Connect your powered camera and your Mac's wired adapter to the same network.
Then follow these three steps. No `pip install` or `sudo` is needed for discovery.

### 1. Download once

```bash
git clone https://github.com/nijkah/hikvision_finder.git
cd hikvision_finder
```

### 2. Find your wired adapter

```bash
networksetup -listallhardwareports
```

Look for your USB Ethernet/LAN adapter and copy its **Device** value, for example:

```text
Hardware Port: USB 10/100/1000 LAN
Device: en4
```

### 3. Find cameras

Run this from the downloaded `hikvision_finder` folder. Replace `en4` if your
adapter has a different name:

```bash
python3 hikvision_finder.py --interface en4
```

Wait about 10 seconds. Match the **MAC** to the camera's label and read its **IP**.
`DHCP: yes` means automatic addressing is enabled; `ACTIVE: no` means the camera
still needs activation. If you see `DUPLICATE IP`, follow the
[duplicate-IP instructions below](#duplicate-initial-ip-addresses-on-macos).

**Next time:** reconnect the camera, open a terminal in the same folder, and run
the command in step 3 again. You do not need to download the tool again.

## Optional commands

Find one camera by its label's MAC (replace the fictional example):

```bash
python3 hikvision_finder.py -i en4 --mac 02:00:00:00:00:01
```

Search longer while a camera boots:

```bash
python3 hikvision_finder.py -i en4 --timeout 30
```

Get JSON output for another script:

```bash
python3 hikvision_finder.py -i en4 --json
```

On Windows or when selecting an adapter by address, use **your computer's wired
IPv4 address**, not the camera's address. Replace this example:

```bash
python3 hikvision_finder.py --local-ip 192.168.1.100
```

On Linux, replace `eth0` with your wired interface:

```bash
python3 hikvision_finder.py -i eth0
```

## Output reference

`--json` produces an object containing `local_ip`, `devices`, and `duplicate_ips`.
Responses are deduplicated by MAC. Multiple MACs reporting the same IP trigger a
duplicate-IP warning. Duplicate detection uses all responses, even with `--mac`.
Missing DHCP or activation values appear as `unknown` in the table and `null` in JSON.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | At least one matching device responded |
| 1 | No matching response received |
| 2 | Invalid input or network/interface error |
| 130 | Interrupted by the user |

No response is not definitive proof that a device is absent.

## Setting up a new camera

1. Power the camera through PoE or an appropriate separate power supply, and
   connect your computer to the same network.
2. Run discovery and match the MAC or serial number against the camera's label.
3. Check the camera's subnet and any duplicate-IP warnings.
4. Open its web interface. If necessary, create an administrator password to
   activate the camera, then enable DHCP in its network settings.
5. On a network with a DHCP server, run discovery again and locate the **same MAC**
   to find its newly assigned address.

A camera with DHCP disabled may already have a default static IP. A `169.254.x.x`
address is not required; do not reuse a previous camera's address without discovery.
When using internal wired networking alongside internet-connected Wi-Fi, macOS
network service ordering can keep Wi-Fi as the preferred internet connection.

### Duplicate initial IP addresses on macOS

If your computer and camera are in the same IPv4 subnet, and discovery confirms the
target MAC, you can temporarily direct your Mac's traffic for the shared IP to that
MAC. **This does not assign an IP address to the camera.** It affects other programs
connecting to that IP too, so remove the entry after setup.

Replace the example IP, fictional MAC, and interface below with your actual values:

```bash
sudo arp -s 192.168.1.64 02:00:00:00:00:01 ifscope en4
arp -n 192.168.1.64
open http://192.168.1.64

# After activation and DHCP setup, or when abandoning the setup
sudo arp -d 192.168.1.64 ifscope en4

# Find the new address using the same MAC
python3 hikvision_finder.py -i en4 --mac 02:00:00:00:00:01
```

If communication remains unreliable, isolate the camera on a separate setup PoE
switch/injector and configure it there before reconnecting it to the shared network.

## How it works

The tool sends XML `Probe` messages with `Types=inquiry` to
`239.255.255.250:37020` through the selected local IPv4 interface. It listens on
UDP 37020 and parses `ProbeMatch` replies. Probes repeat until the timeout expires.
Administrator privileges and camera credentials are normally unnecessary.

## Troubleshooting

- **No adapter IPv4:** check power, link status, and your computer's address settings.
  Direct connections without a DHCP server may not yet have an IPv4 address.
- **No responses:** check the VLAN, multicast forwarding, port isolation, and firewall.
  On macOS, also check local-network permissions for the application running Python.
- **Port binding error:** close other SADP/discovery programs and try again.
- **Wrong adapter:** explicitly select the wired interface or its local IPv4 address.
- **Camera still booting:** wait for startup and retry with `--timeout 30`.
- **Unexpected devices:** Hikvision switches and NVRs can respond too; check the model.
- **Sharing output:** results include MACs, serial numbers, and IP addresses. Redact
  unnecessary identifying information before posting logs publicly.

## Tests

```bash
python3 -m unittest -v
```

Tests use fictional MAC/IP values. No credentials or actual device inventories are
included in this repository.
