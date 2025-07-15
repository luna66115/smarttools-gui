#!/usr/bin/env python3
import sys
import subprocess
import re
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QVBoxLayout, QStyleFactory,
    QMessageBox, QPushButton, QLabel, QHBoxLayout, QDialog, QTextEdit
)
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor
from PyQt6.QtCore import Qt, QProcess, QTimer

def is_command_available(cmd):
    result = subprocess.run(['which', cmd], capture_output=True, text=True)
    return result.returncode == 0

def is_smartd_running():
    result = subprocess.run(['systemctl', 'is-active', 'smartd'], capture_output=True, text=True)
    return result.stdout.strip() == 'active'

def start_smartd():
    subprocess.run(['pkexec', 'systemctl', 'start', 'smartd'])

def stop_smartd():
    subprocess.run(['pkexec', 'systemctl', 'stop', 'smartd'])

def install_smartmontools():
    subprocess.run(['pkexec', 'apt', 'install', '-y', 'smartmontools'])

def parse_journal_output(output):
    problems = set()
    lines = output.strip().splitlines()
    for line in lines:
        m = re.search(r"Device: (\S+).*FAILED", line)
        if m:
            problems.add(m.group(1))
    if problems:
        return f"⚠️ Fehler bei {', '.join(sorted(problems))}", list(problems)
    else:
        return "✅ Alle Laufwerke OK", []

def get_disks():
    output = subprocess.run(["lsblk", "-dn", "-o", "NAME"], capture_output=True, text=True)
    devices = []
    for line in output.stdout.strip().splitlines():
        devices.append(f"/dev/{line.strip()}")
    return devices

def parse_smartctl(device):
    result = subprocess.run(["smartctl", "-a", "-d", "sat", device], capture_output=True, text=True)
    info = {"Device": device}
    if result.returncode != 0:
        info["Error"] = "SMART nicht lesbar"
        return info
    lines = result.stdout.splitlines()
    for line in lines:
        if "Model Family:" in line or "Device Model:" in line or "Model Number:" in line:
            info["Model"] = line.split(":", 1)[1].strip()
        elif "Serial Number:" in line:
            info["Serial"] = line.split(":", 1)[1].strip()
        elif "Firmware Version:" in line:
            info["Firmware"] = line.split(":", 1)[1].strip()
        elif "SMART overall-health self-assessment test result" in line:
            info["Health"] = line.split(":", 1)[1].strip()
        elif "Temperature_Celsius" in line:
            parts = line.split()
            if len(parts) >= 10:
                info["Temp"] = parts[9] + " °C"
    return info

class ModelInfoDialog(QDialog):
    def __init__(self, model_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modellbezeichnung")
        self.resize(400, 150)
        layout = QVBoxLayout(self)
        label = QLabel(model_text, self)
        label.setWordWrap(True)
        layout.addWidget(label)
        btn_close = QPushButton("Schließen", self)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

class SmartWindow(QWidget):
    def __init__(self, disks_info):
        super().__init__()
        self.setWindowTitle("SMART‑Monitor , by S. Macri 2025")
        self.resize(800, 300)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(self)
        headers = ["Device", "Model", "Serial", "Firmware", "Health", "Temp", "Error"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(disks_info))

        for row, disk in enumerate(disks_info):
            for col, key in enumerate(headers):
                val = disk.get(key, "")
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Signal für Klick auf Zelle verbinden
        self.table.cellClicked.connect(self.cell_clicked)

        layout.addWidget(self.table)

    def cell_clicked(self, row, column):
        if self.table.horizontalHeaderItem(column).text() == "Model":
            model_text = self.table.item(row, column).text()
            if model_text:
                dlg = ModelInfoDialog(model_text, self)
                dlg.exec()

class InfoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("smartd & smartmontools Hilfe")
        self.resize(600, 400)
        layout = QVBoxLayout(self)

        text = (
            "<h2>Was ist smartd?</h2>"
            "<p><b>smartd</b> ist ein Dienst (Daemon), der kontinuierlich den Zustand deiner "
            "Festplatten/SSDs überwacht und bei Problemen automatisch Alarm schlägt.</p>"
            "<h3>Vorteile</h3>"
            "<ul><li>Automatische Überwachung</li><li>Warnungen bei Fehlern</li><li>Kann Aktionen wie Email-Benachrichtigungen auslösen</li></ul>"
            "<h3>Was sind smartmontools?</h3>"
            "<p>Das Paket enthält smartctl (zum Abfragen von SMART-Daten) und smartd (den Daemon). "
            "Ohne diese Tools funktioniert die automatische Überwachung nicht.</p>"
            "<h3>Tipps</h3>"
            "<ul>"
            "<li>Stelle sicher, dass smartmontools installiert sind</li>"
            "<li>smartd läuft und ist aktiviert (<code>systemctl status smartd</code>)</li>"
            "<li>Bei Problemen hilft die Tabelle, betroffene Laufwerke schnell zu erkennen</li>"
            "</ul>"
        )

        label = QTextEdit(self)
        label.setReadOnly(True)
        label.setHtml(text)
        layout.addWidget(label)

def set_dark_theme(app):
    app.setStyle(QStyleFactory.create("Fusion"))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    app.setPalette(palette)

class TrayApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        set_dark_theme(self)

        self.tray_icon = QSystemTrayIcon(QIcon.fromTheme("drive-harddisk"), self)
        self.tray_icon.setToolTip("Starte Überwachung …")

        self.menu = QMenu()
        self.menu.addAction(QAction("SMART-Daten anzeigen", self, triggered=self.show_smart))
        self.menu.addAction(QAction("smartd starten", self, triggered=start_smartd))
        self.menu.addAction(QAction("smartd stoppen", self, triggered=stop_smartd))
        self.menu.addAction(QAction("smartmontools installieren", self, triggered=install_smartmontools))
        self.menu.addAction(QAction("Info zu smartd & smartmontools", self, triggered=self.show_info))
        self.menu.addSeparator()
        self.menu.addAction(QAction("Beenden", self, triggered=self.quit))

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self.on_tray_activated)

        self.smart_window = None
        self.proc = None

        self.update_install_status()
        self.update_smartd_status()
        self.update_status("Starte Überwachung ...")
        self.initial_check()
        self.start_journal_follow()

        self.tray_icon.show()

        self.timer = QTimer()
        self.timer.timeout.connect(self.periodic_update)
        self.timer.start(5 * 60 * 1000)

    def update_install_status(self):
        installed = is_command_available("smartctl")
        for action in self.menu.actions():
            if action.text().startswith("smartmontools installieren"):
                action.setEnabled(not installed)
        if not installed:
            self.update_status("⚠️ smartmontools nicht installiert!")

    def update_smartd_status(self):
        running = is_smartd_running()
        for action in self.menu.actions():
            if action.text().startswith("smartd starten"):
                action.setEnabled(not running)
            elif action.text().startswith("smartd stoppen"):
                action.setEnabled(running)
        if not running:
            self.update_status("⚠️ smartd Dienst läuft nicht!")

    def update_status(self, text):
        self.tray_icon.setToolTip(text)

    def initial_check(self):
        result = subprocess.run(["journalctl", "-u", "smartd", "-n", "100"], capture_output=True, text=True)
        self.process_journal_output(result.stdout)

    def start_journal_follow(self):
        self.proc = QProcess()
        self.proc.readyReadStandardOutput.connect(self.on_journal_output)
        self.proc.start("journalctl", ["-u", "smartd", "-f"])

    def on_journal_output(self):
        output = bytes(self.proc.readAllStandardOutput()).decode("utf-8")
        self.process_journal_output(output)

    def process_journal_output(self, output):
        status_text, problems = parse_journal_output(output)
        self.update_status(status_text)
        # Optional: hier könntest du bei Problemen Benachrichtigungen einbauen

    def periodic_update(self):
        self.update_install_status()
        self.update_smartd_status()
        self.initial_check()

    def show_smart(self):
        disks = get_disks()
        disks_info = []
        for d in disks:
            info = parse_smartctl(d)
            disks_info.append(info)
        if self.smart_window is None:
            self.smart_window = SmartWindow(disks_info)
        else:
            self.smart_window.close()
            self.smart_window = SmartWindow(disks_info)
        self.smart_window.show()
        self.smart_window.raise_()
        self.smart_window.activateWindow()

    def show_info(self):
        dlg = InfoDialog()
        dlg.exec()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_smart()

if __name__ == "__main__":
    app = TrayApp(sys.argv)
    sys.exit(app.exec())
