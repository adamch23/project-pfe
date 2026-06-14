import subprocess
import os
import signal
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class MonitoringService:
    def __init__(self):
        self.processes: Dict[str, Optional[subprocess.Popen]] = {
            "windows_exporter": None,
            "prometheus": None,
            "grafana": None
        }
        
        # Base paths
        self.base_dir = r"E:\Ressource Monitoring"
        self.prometheus_dir = os.path.join(self.base_dir, "prometheus-3.5.3.windows-amd64")
        self.grafana_exe = os.path.join(self.base_dir, "GrafanaLabs", "grafana", "bin", "grafana.exe")
        
        # Executables and configs
        self.exporter_exe = os.path.join(self.prometheus_dir, "windows_exporter.exe")
        self.prometheus_exe = os.path.join(self.prometheus_dir, "prometheus.exe")
        self.prometheus_config = os.path.join(self.prometheus_dir, "prometheus.yml")

    def start_all(self):
        """Starts all monitoring components."""
        logger.info("Starting monitoring components...")
        
        # 1. Start Windows Exporter
        if not self.processes["windows_exporter"] or self.processes["windows_exporter"].poll() is not None:
            try:
                self.processes["windows_exporter"] = subprocess.Popen(
                    [self.exporter_exe],
                    cwd=self.prometheus_dir,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                logger.info("✅ Windows Exporter started.")
            except Exception as e:
                logger.error(f"❌ Failed to start Windows Exporter: {e}")

        # 2. Start Prometheus
        if not self.processes["prometheus"] or self.processes["prometheus"].poll() is not None:
            try:
                self.processes["prometheus"] = subprocess.Popen(
                    [self.prometheus_exe, "--config.file=" + self.prometheus_config],
                    cwd=self.prometheus_dir,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                logger.info("✅ Prometheus started.")
            except Exception as e:
                logger.error(f"❌ Failed to start Prometheus: {e}")

        # 3. Start Grafana
        if not self.processes["grafana"] or self.processes["grafana"].poll() is not None:
            try:
                grafana_root = os.path.dirname(os.path.dirname(self.grafana_exe))
                self.processes["grafana"] = subprocess.Popen(
                    [self.grafana_exe, "server"],
                    cwd=grafana_root,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                logger.info("✅ Grafana started.")
            except Exception as e:
                logger.error(f"❌ Failed to start Grafana: {e}")

    def stop_all(self):
        """Stops all monitoring components."""
        logger.info("Stopping monitoring components...")
        for name, proc in self.processes.items():
            if proc and proc.poll() is None:
                try:
                    logger.info(f"Stopping {name} (PID: {proc.pid})...")
                    # On Windows, we use taskkill to ensure the whole tree is killed if necessary
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                    proc.wait(timeout=5)
                    logger.info(f"✅ {name} stopped.")
                except Exception as e:
                    logger.error(f"❌ Error stopping {name}: {e}")
            self.processes[name] = None

    def get_status(self) -> Dict[str, str]:
        """Checks the status of the processes."""
        status = {}
        for name, proc in self.processes.items():
            if proc and proc.poll() is None:
                status[name] = "running"
            else:
                status[name] = "stopped"
        return status

# Singleton instance
monitoring_manager = MonitoringService()
