import unittest
import argparse
from hikvision_finder import normalize_mac, parse_response, duplicate_ips, positive_seconds


class FinderTests(unittest.TestCase):
    def test_mac_formats(self):
        for value in ['02-00-00-ab-cd-ef', '02:00:00:AB:CD:EF', '0200.00ab.cdef']:
            self.assertEqual(normalize_mac(value), '02:00:00:AB:CD:EF')
        with self.assertRaises(ValueError):
            normalize_mac('not-a-mac')

    def test_response_and_unknown_boolean(self):
        d = parse_response(b'<ProbeMatch><MAC>02-00-00-00-00-01</MAC>'
                           b'<IPv4Address>192.0.2.64</IPv4Address><DHCP>false</DHCP></ProbeMatch>')
        self.assertEqual(d['ip'], '192.0.2.64')
        self.assertIs(d['dhcp'], False)
        self.assertIsNone(d['activated'])

    def test_namespace(self):
        d = parse_response(b'<ProbeMatch xmlns="urn:test"><MAC>02-00-00-00-00-01</MAC>'
                           b'<Activated>true</Activated></ProbeMatch>')
        self.assertTrue(d['activated'])

    def test_ignores_invalid_packets(self):
        for packet in [b'bad', b'<Probe/>', b'<ProbeMatch/>',
                       b'<!DOCTYPE x><ProbeMatch><MAC>02-00-00-00-00-01</MAC></ProbeMatch>']:
            self.assertIsNone(parse_response(packet))

    def test_duplicates_require_distinct_macs(self):
        a = {'ip': '192.0.2.64', 'mac': '02:00:00:00:00:01'}
        b = {'ip': '192.0.2.64', 'mac': '02:00:00:00:00:02'}
        self.assertEqual(duplicate_ips([a, a]), {})
        self.assertEqual(len(duplicate_ips([a, b])['192.0.2.64']), 2)

    def test_time_limits(self):
        for value in ['0', '-1', 'nan', 'inf']:
            with self.assertRaises(argparse.ArgumentTypeError):
                positive_seconds(value)
        self.assertEqual(positive_seconds('0.5'), 0.5)


if __name__ == '__main__':
    unittest.main()
