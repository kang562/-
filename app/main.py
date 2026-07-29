from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from .config import SettingsStore, available_skins, skin_manifest
from .input_listener import GlobalInputListener
from .pet_window import PetWindow


APP_NAME = "桌面宠物"


def create_tray_icon(app: QApplication) -> QIcon:
    fallback = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#1d1b25"))
    painter.setPen(QColor("#d2a95a"))
    painter.drawEllipse(5, 5, 54, 54)
    painter.setBrush(QColor("#5d9be8"))
    painter.setPen(QColor("#ffffff"))
    painter.drawEllipse(16, 23, 12, 17)
    painter.drawEllipse(36, 23, 12, 17)
    painter.end()
    icon = QIcon(pixmap)
    return icon if not icon.isNull() else fallback


class DesktopPetApplication:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.store = SettingsStore.create_default()
        self.settings = self.store.load()
        skin_dir, manifest = skin_manifest(self.settings["skin"])
        self.window = PetWindow(self.settings, skin_dir, manifest)
        self.window.settings_changed.connect(self.save_settings)
        self.window.exit_requested.connect(self.quit)

        self.listener = GlobalInputListener(self.window)
        self.listener.input_received.connect(self.window.show_input)
        self.listener.listener_error.connect(self.window.show_listener_error)

        self.tray = QSystemTrayIcon(create_tray_icon(app), app)
        self.tray.setToolTip(APP_NAME)
        self.tray.setContextMenu(self._build_tray_menu())
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()
        self._restore_position()
        self.window.show()
        self.listener.start()

    def _build_tray_menu(self) -> QMenu:
        menu = QMenu()
        show_action = QAction("隐藏宠物" if self.window.isVisible() else "显示宠物", menu)
        show_action.triggered.connect(self.toggle_visibility)
        menu.addAction(show_action)

        self.top_action = QAction("保持置顶", menu, checkable=True)
        self.top_action.setChecked(bool(self.settings["always_on_top"]))
        self.top_action.toggled.connect(self.window.set_always_on_top)
        menu.addAction(self.top_action)

        self.input_action = QAction("显示键鼠提示", menu, checkable=True)
        self.input_action.setChecked(bool(self.settings["input_display_enabled"]))
        self.input_action.toggled.connect(self.set_input_display)
        menu.addAction(self.input_action)

        scale_menu = menu.addMenu("缩放")
        for scale in (0.8, 1.0, 1.2, 1.4):
            action = QAction(f"{int(scale * 100)}%", scale_menu, checkable=True)
            action.setChecked(abs(float(self.settings["window_scale"]) - scale) < 0.01)
            action.triggered.connect(lambda _checked=False, value=scale: self.window.set_scale(value))
            scale_menu.addAction(action)

        skins = available_skins()
        if skins:
            skin_menu = menu.addMenu("切换皮肤")
            for skin_name in skins:
                action = QAction(skin_name, skin_menu, checkable=True)
                action.setChecked(skin_name == self.settings["skin"])
                action.triggered.connect(lambda _checked=False, value=skin_name: self.set_skin(value))
                skin_menu.addAction(action)

        menu.addSeparator()
        reset_action = QAction("恢复右下角位置", menu)
        reset_action.triggered.connect(self.reset_position)
        menu.addAction(reset_action)
        menu.addSeparator()
        quit_action = QAction("退出桌宠", menu)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)
        return menu

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.toggle_visibility()

    def toggle_visibility(self) -> None:
        self.window.setVisible(not self.window.isVisible())
        self.tray.setContextMenu(self._build_tray_menu())

    def set_input_display(self, enabled: bool) -> None:
        self.settings["input_display_enabled"] = enabled
        self.save_settings(self.settings)

    def set_skin(self, skin_name: str) -> None:
        skin_dir, manifest = skin_manifest(skin_name)
        self.settings["skin"] = skin_name
        self.window.set_skin(skin_dir, manifest)
        self.save_settings(self.settings)
        self.tray.setContextMenu(self._build_tray_menu())

    def _restore_position(self) -> None:
        position = self.settings["position"]
        if isinstance(position.get("x"), int) and isinstance(position.get("y"), int):
            self.window.move(position["x"], position["y"])
            return
        self.reset_position(save=False)

    def reset_position(self, _checked: bool = False, save: bool = True) -> None:
        screen = self.app.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.window.move(geometry.right() - self.window.width() - 20, geometry.bottom() - self.window.height() - 20)
        if save:
            self.settings["position"] = {"x": self.window.x(), "y": self.window.y()}
            self.save_settings(self.settings)

    def save_settings(self, settings: dict) -> None:
        self.settings = settings
        self.store.save(settings)

    def quit(self) -> None:
        self.listener.stop()
        self.tray.hide()
        self.app.quit()


def main() -> int:
    QCoreApplication.setOrganizationName("DesktopPet")
    QCoreApplication.setApplicationName(APP_NAME)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    controller = DesktopPetApplication(app)
    _ = controller
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
