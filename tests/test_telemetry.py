import unittest
from core import telemetry


class TestTelemetry(unittest.TestCase):
    def test_kpis_structure(self):
        kpis = telemetry.get_kpis()
        self.assertIn("uptime", kpis)
        self.assertIn("total_messages", kpis)
        self.assertIn("total_tool_calls", kpis)
        self.assertIn("avg_latency", kpis)
        self.assertIn("active_sessions", kpis)

    def test_storage_info(self):
        info = telemetry.get_storage_info()
        self.assertIn("mount_path", info)
        self.assertIn("is_hf_bucket", info)
        self.assertIn("total_size_kb", info)

    def test_table_data_formats(self):
        traces = telemetry.get_traces_table_data()
        self.assertIsInstance(traces, list)

        sessions = telemetry.get_sessions_table_data()
        self.assertIsInstance(sessions, list)


if __name__ == "__main__":
    unittest.main()
