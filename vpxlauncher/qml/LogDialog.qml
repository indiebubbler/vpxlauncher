import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Podgląd vpinball.log (ostatnie uruchomienie).
Popup {
    id: root
    modal: true
    focus: true
    padding: 20
    anchors.centerIn: Overlay.overlay
    width: Math.min(1100, (parent ? parent.width : 1000) - 48)
    height: Math.min(760, (parent ? parent.height : 700) - 48)
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

    function refresh() {
        info.text = backend.logInfo()
        area.text = backend.readLog()
        area.cursorPosition = area.length   // przewiń na koniec, tam jest najświeższy wpis
    }

    onAboutToShow: refresh()

    contentItem: ColumnLayout {
        spacing: 10

        Text {
            text: root.tr("Game log")
            color: theme.text
            font.pixelSize: 20
            font.weight: Font.DemiBold
        }
        Text {
            id: info
            Layout.fillWidth: true
            color: theme.muted
            font.pixelSize: 12
            elide: Text.ElideMiddle
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 8
            color: theme.bg
            border.width: 1
            border.color: theme.line

            ScrollView {
                anchors.fill: parent
                anchors.margins: 2
                clip: true

                TextArea {
                    id: area
                    readOnly: true
                    selectByMouse: true
                    color: theme.text
                    selectionColor: theme.lampDeep
                    selectedTextColor: "#ffffff"
                    font.family: Qt.platform.os === "windows" ? "Consolas" : "monospace"
                    font.pixelSize: 12
                    wrapMode: TextArea.NoWrap
                    leftPadding: 10
                    topPadding: 8
                    background: null
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            AppButton { text: root.tr("Refresh"); onClicked: root.refresh() }
            AppButton {
                text: root.tr("Copy all")
                onClicked: {
                    area.selectAll()
                    area.copy()
                    area.deselect()
                }
            }
            Item { Layout.fillWidth: true }
            AppButton { text: root.tr("Close"); accent: true; onClicked: root.close() }
        }
    }
}
