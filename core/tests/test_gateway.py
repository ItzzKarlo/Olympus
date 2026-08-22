import unittest

from olympus_core.monitoring.gateway import (
    parse_linux_default_route,
    parse_macos_default_route,
    parse_windows_default_route,
    resolve_gateway,
)


class GatewayDetectionTests(unittest.IsolatedAsyncioTestCase):
    def test_parses_linux_default_route(self) -> None:
        route = (
            "Iface Destination Gateway Flags RefCnt Use Metric Mask\n"
            "eth0 00000000 01B2A8C0 0003 0 0 100 00000000\n"
        )
        self.assertEqual(parse_linux_default_route(route), "192.168.178.1")

    def test_parses_macos_default_route(self) -> None:
        route = "   route to: default\ndestination: default\n    gateway: 172.20.10.1\n"
        self.assertEqual(parse_macos_default_route(route), "172.20.10.1")

    def test_parses_lowest_metric_windows_default_route(self) -> None:
        route = """
        0.0.0.0          0.0.0.0      10.10.0.1      10.10.0.5     35
        0.0.0.0          0.0.0.0  192.168.178.1  192.168.178.20     15
        """
        self.assertEqual(parse_windows_default_route(route), "192.168.178.1")

    async def test_explicit_gateway_overrides_auto_detection(self) -> None:
        gateway = await resolve_gateway("10.10.0.1")
        self.assertEqual(gateway.host, "10.10.0.1")
        self.assertEqual(gateway.source, "configured")


if __name__ == "__main__":
    unittest.main()
