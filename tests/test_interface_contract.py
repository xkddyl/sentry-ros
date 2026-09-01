from __future__ import annotations

import json
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


class InterfaceContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.topics = yaml.safe_load(
            (ROOT / "config" / "interfaces" / "ros_topics.yaml").read_text(
                encoding="utf-8"
            )
        )

    def test_control_and_tf_names_are_canonical(self) -> None:
        commands = self.topics["commands"]
        self.assertEqual(commands["raw_chassis"]["topic"], "/cmd_vel")
        self.assertEqual(commands["teleop_chassis"]["topic"], "/cmd_vel_teleop")
        self.assertEqual(commands["safe_chassis"]["topic"], "/sentry/cmd_vel_safe")
        self.assertEqual(
            commands["raw_chassis_control"]["topic"],
            "/sentry/chassis_control",
        )
        self.assertEqual(
            commands["safe_chassis_control"]["topic"],
            "/sentry/chassis_control_safe",
        )
        self.assertEqual(
            self.topics["state"]["hardware_diagnostics"]["topic"],
            "/sentry/hardware_diagnostics",
        )
        self.assertEqual(
            self.topics["tf_ownership"]["global_topics"], ["/tf", "/tf_static"]
        )
        self.assertNotIn("/sentry/tf", json.dumps(self.topics, ensure_ascii=False))

    def test_safety_node_owns_both_safe_control_buses(self) -> None:
        source = (
            ROOT
            / "ros2_ws"
            / "src"
            / "sentinel_core"
            / "sentinel_core"
            / "safety_supervisor.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"/cmd_vel"', source)
        self.assertIn('"/cmd_vel_teleop"', source)
        self.assertIn('"/sentry/chassis_control"', source)
        self.assertIn('"/sentry/cmd_vel_safe"', source)
        self.assertIn('"/sentry/chassis_control_safe"', source)
        self.assertNotIn('"/sentry/tf"', source)

    def test_hardware_bridge_consumes_safe_chassis_control_only(self) -> None:
        source = (
            ROOT
            / "ros2_ws"
            / "src"
            / "sentinel_core"
            / "sentinel_core"
            / "hardware_bridge.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"/sentry/cmd_vel_safe"', source)
        self.assertIn('"/sentry/chassis_control_safe"', source)
        self.assertIn('"/sentry/hardware_diagnostics"', source)
        self.assertNotIn(
            '"/sentry/chassis_control",',
            source,
            "hardware bridge must not subscribe to the raw mode bus",
        )

    def test_active_files_do_not_create_namespaced_tf(self) -> None:
        roots = [
            ROOT / "ros2_ws" / "src",
            ROOT / "isaac_sim",
            ROOT / "config",
            ROOT / "tools" / "integration",
        ]
        offenders: list[Path] = []
        for base in roots:
            for path in base.rglob("*"):
                if not path.is_file() or path.suffix not in {
                    ".py",
                    ".sh",
                    ".yaml",
                    ".yml",
                    ".xml",
                    ".json",
                }:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                if "/sentry/tf" in text:
                    offenders.append(path)
        self.assertEqual(offenders, [])

    def test_workspace_mcp_uses_uvx_from_package(self) -> None:
        config = json.loads((ROOT / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
        server = config["servers"]["rosMcp"]
        self.assertEqual(server["command"], "uvx")
        self.assertEqual(
            server["args"],
            ["--from", "ros-mcp==3.1.0", "ros-mcp", "--transport=stdio"],
        )


if __name__ == "__main__":
    unittest.main()
