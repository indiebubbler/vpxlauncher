import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

Popup {
    id: root
    modal: true
    focus: true
    padding: 24
    anchors.centerIn: Overlay.overlay
    width: Math.min(700, (parent ? parent.width : 720) - 48)
    closePolicy: Popup.CloseOnEscape

    function tr(message) {
        const currentLanguage = backend.language
        return backend.translate(message)
    }

    background: Rectangle {
        radius: 12
        color: theme.surface
        border.width: 1
        border.color: theme.line
    }
    Overlay.modal: Rectangle { color: "#b3070b12" }

    onAboutToShow: {
        exeField.text = backend.settingsExecutable
        dirsArea.text = backend.settingsDirs
        envArea.text = backend.settingsEnv
        argsField.text = backend.settingsArgs
        autoArtBtn.checked = backend.settingsAutoArt
        logField.text = backend.settingsLogPath
        languageBox.currentIndex = backend.languageCodes.indexOf(backend.language)
        graphicsBackendBox.currentIndex = backend.graphicsBackendValues.indexOf(backend.graphicsBackend)
    }

    contentItem: ColumnLayout {
        spacing: 8

        Text {
            text: root.tr("Settings")
            color: theme.text
            font.pixelSize: 20
            font.weight: Font.DemiBold
            Layout.bottomMargin: 8
        }

        Text { text: root.tr("VPinballX executable"); color: theme.muted; font.pixelSize: 12 }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            AppTextField {
                id: exeField
                Layout.fillWidth: true
                placeholderText: root.tr("VPinballX_BGFX (Linux) or VPinballX_BGFX.exe (Windows)")
            }
            AppButton { text: root.tr("Browse..."); onClicked: exeDialog.open() }
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: root.tr("Language")
                color: theme.muted
                font.pixelSize: 12
                Layout.fillWidth: true
            }
            ComboBox {
                id: languageBox
                Layout.preferredWidth: 180
                model: backend.languageNames
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: root.tr("Graphics backend")
                color: theme.muted
                font.pixelSize: 12
                Layout.fillWidth: true
            }
            ComboBox {
                id: graphicsBackendBox
                Layout.preferredWidth: 240
                model: backend.graphicsBackendNames
            }
        }
        Text {
            text: root.tr("VPinball may fall back to its default if the selected backend is unavailable.")
            color: theme.muted
            font.pixelSize: 11
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Text {
            text: root.tr("Table folders, one per line")
            color: theme.muted
            font.pixelSize: 12
            Layout.topMargin: 8
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            AppTextArea {
                id: dirsArea
                Layout.fillWidth: true
                placeholderText: root.tr("Add a folder using the button")
            }
            AppButton {
                text: root.tr("Add folder...")
                Layout.alignment: Qt.AlignTop
                onClicked: dirDialog.open()
            }
        }

        Text {
            text: root.tr("Game environment variables, KEY=value on separate lines")
            color: theme.muted
            font.pixelSize: 12
            Layout.topMargin: 8
        }
        AppTextArea {
            id: envArea
            Layout.fillWidth: true
            placeholderText: root.tr("e.g. __NV_PRIME_RENDER_OFFLOAD=1")
        }

        Text {
            text: root.tr("Additional arguments (before -play)")
            color: theme.muted
            font.pixelSize: 12
            Layout.topMargin: 8
        }
        AppTextField {
            id: argsField
            Layout.fillWidth: true
            placeholderText: root.tr("optional")
        }

        Text {
            text: root.tr("VPinball log file (vpinball.log)")
            color: theme.muted
            font.pixelSize: 12
            Layout.topMargin: 8
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            AppTextField { id: logField; Layout.fillWidth: true }
            AppButton { text: root.tr("Browse..."); onClicked: logFileDialog.open() }
        }

        AppButton {
            id: autoArtBtn
            Layout.topMargin: 8
            checkable: true
            text: checked
                  ? root.tr("Download artwork after scanning: enabled")
                  : root.tr("Download artwork after scanning: disabled")
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 16
            spacing: 8
            Item { Layout.fillWidth: true }
            AppButton { text: root.tr("Cancel"); onClicked: root.close() }
            AppButton {
                text: root.tr("Save")
                accent: true
                onClicked: {
                    backend.saveSettings(
                        exeField.text, dirsArea.text, envArea.text, argsField.text,
                        autoArtBtn.checked, logField.text, backend.languageCodes[languageBox.currentIndex],
                        backend.graphicsBackendValues[graphicsBackendBox.currentIndex]
                    )
                    root.close()
                }
            }
        }

        FileDialog {
            id: exeDialog
            title: root.tr("Choose VPinballX executable")
            onAccepted: exeField.text = backend.urlToPath(selectedFile)
        }
        FileDialog {
            id: logFileDialog
            title: root.tr("Choose vpinball.log file")
            onAccepted: logField.text = backend.urlToPath(selectedFile)
        }
        FolderDialog {
            id: dirDialog
            title: root.tr("Choose table folder")
            onAccepted: {
                var p = backend.urlToPath(selectedFolder)
                var cur = dirsArea.text.trim()
                dirsArea.text = cur === "" ? p : cur + "\n" + p
            }
        }
    }
}
