from test_toolkit import Fixture
from factorykit.common import FactoryError
from factorykit.tasks import render_packet


class LinuxPacketTests(Fixture):
    def test_linux_packet_uses_actual_host_guidance_and_pinned_specs(self):
        self.config['runtime']['execution_platform'] = 'linux'
        packet = render_packet(self.config, 'tablekeeper', [1, 2, 3, 4], 'all')[0].decode()
        self.assertIn('This execution host is Linux', packet)
        self.assertIn('Do not prune unrelated resources', packet)
        self.assertNotIn('on this Mac', packet)
        self.assertNotIn('pinned local socket', packet)
        self.assertIn('Official synthetic tablekeeper specification 4', packet)

    def test_unknown_host_does_not_emit_misleading_guidance(self):
        self.config['runtime']['execution_platform'] = 'unknown'
        with self.assertRaises(FactoryError):
            render_packet(self.config, 'tablekeeper', [1], 'separate')
