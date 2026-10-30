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
    }

    contentItem: ColumnLayout {
        spacing: 8

        Text {
            text: "Ustawienia"
            color: theme.text
            font.pixelSize: 20
            font.weight: Font.DemiBold
            Layout.bottomMargin: 8
        }

        Text { text: "Plik wykonywalny VPinballX"; color: theme.muted; font.pixelSize: 12 }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            AppTextField {
                id: exeField
                Layout.fillWidth: true
                placeholderText: "VPinballX_BGFX (Linux) lub VPinballX_BGFX.exe (Windows)"
            }
            AppButton { text: "Wybierz…"; onClicked: exeDialog.open() }
        }

        Text {
            text: "Foldery ze stołami, jeden na linię"
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
                placeholderText: "Dodaj folder przyciskiem obok"
            }
            AppButton {
                text: "Dodaj folder…"
                Layout.alignment: Qt.AlignTop
                onClicked: dirDialog.open()
            }
        }

        Text {
            text: "Zmienne środowiskowe gry, KLUCZ=wartość w osobnych liniach"
            color: theme.muted
            font.pixelSize: 12
            Layout.topMargin: 8
        }
        AppTextArea {
            id: envArea
            Layout.fillWidth: true
            placeholderText: "np. __NV_PRIME_RENDER_OFFLOAD=1"
        }

        Text {
            text: "Dodatkowe argumenty (przed -play)"
            color: theme.muted
            font.pixelSize: 12
            Layout.topMargin: 8
        }
        AppTextField {
            id: argsField
            Layout.fillWidth: true
            placeholderText: "opcjonalnie"
        }

        Text {
            text: "Plik logu VPinball (vpinball.log)"
            color: theme.muted
            font.pixelSize: 12
            Layout.topMargin: 8
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            AppTextField { id: logField; Layout.fillWidth: true }
            AppButton { text: "Wybierz…"; onClicked: logFileDialog.open() }
        }

        AppButton {
            id: autoArtBtn
            Layout.topMargin: 8
            checkable: true
            text: checked ? "Pobieraj grafiki po skanowaniu: włączone" : "Pobieraj grafiki po skanowaniu: wyłączone"
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 16
            spacing: 8
            Item { Layout.fillWidth: true }
            AppButton { text: "Anuluj"; onClicked: root.close() }
            AppButton {
                text: "Zapisz"
                accent: true
                onClicked: {
                    backend.saveSettings(exeField.text, dirsArea.text, envArea.text, argsField.text, autoArtBtn.checked, logField.text)
                    root.close()
                }
            }
        }

        FileDialog {
            id: exeDialog
            title: "Wybierz plik VPinballX"
            onAccepted: exeField.text = backend.urlToPath(selectedFile)
        }
        FileDialog {
            id: logFileDialog
            title: "Wybierz plik vpinball.log"
            onAccepted: logField.text = backend.urlToPath(selectedFile)
        }
        FolderDialog {
            id: dirDialog
            title: "Wybierz folder ze stołami"
            onAccepted: {
                var p = backend.urlToPath(selectedFolder)
                var cur = dirsArea.text.trim()
                dirsArea.text = cur === "" ? p : cur + "\n" + p
            }
        }
    }
}
