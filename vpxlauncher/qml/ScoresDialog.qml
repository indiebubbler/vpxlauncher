import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

Popup {
    id: root
    modal: true
    focus: true
    padding: 20
    anchors.centerIn: Overlay.overlay
    width: Math.min(760, (parent ? parent.width : 800) - 48)
    height: Math.min(600, (parent ? parent.height : 640) - 48)
    closePolicy: Popup.CloseOnEscape

    function tr(message) {
        return backend.translate(message)
    }

    function recordStatus(record) {
        if (record.status === "score")
            return root.tr("Score found")
        if (record.status === "empty")
            return root.tr("No high score stored")
        if (record.status === "unsupported")
            return root.tr("Unsupported NVRAM format")
        if (record.status === "invalid")
            return root.tr("Could not decode NVRAM") + ": " + record.error
        return root.tr("Could not read NVRAM file") + ": " + record.error
    }

    background: Rectangle {
        radius: 12
        color: theme.surface
        border.width: 1
        border.color: theme.line
    }
    Overlay.modal: Rectangle { color: "#b3070b12" }

    onOpened: backend.scanScores()

    contentItem: ColumnLayout {
        spacing: 10

        Text {
            text: root.tr("PinMAME high scores")
            color: theme.text
            font.pixelSize: 20
            font.weight: Font.DemiBold
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: backend.settingsNvramDir
                color: theme.muted
                font.pixelSize: 12
                elide: Text.ElideMiddle
            }
            AppButton {
                text: root.tr("Choose folder...")
                onClicked: folderDialog.open()
            }
            AppButton {
                text: root.tr("Refresh")
                enabled: !backend.scoreScanning
                onClicked: backend.scanScores()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 34
            color: theme.raised
            radius: 5
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                Text {
                    Layout.fillWidth: true
                    text: root.tr("ROM")
                    color: theme.muted
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }
                Text {
                    width: 150
                    horizontalAlignment: Text.AlignRight
                    text: root.tr("Best score")
                    color: theme.muted
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }
            }
        }

        ListView {
            id: scoreList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: backend.scoreRecords
            spacing: 2
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                required property var modelData
                width: scoreList.width
                height: 48
                radius: 5
                color: index % 2 === 0 ? theme.surface : theme.raised

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 12
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: modelData.rom
                            color: theme.text
                            font.pixelSize: 13
                            elide: Text.ElideRight
                        }
                        Text {
                            text: root.recordStatus(modelData)
                            color: modelData.status === "score" ? theme.lamp : theme.muted
                            font.pixelSize: 11
                            elide: Text.ElideRight
                        }
                    }
                    Text {
                        width: 150
                        horizontalAlignment: Text.AlignRight
                        text: modelData.scoreText || "—"
                        color: modelData.status === "score" ? theme.text : theme.muted
                        font.pixelSize: 14
                        font.weight: modelData.status === "score" ? Font.DemiBold : Font.Normal
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: !backend.scoreScanning && backend.scoreRecords.length === 0
                         && !backend.scoreScanFailed
                width: parent.width - 32
                text: root.tr("No NVRAM files found.")
                color: theme.muted
                font.pixelSize: 14
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }
        }

        Text {
            Layout.fillWidth: true
            text: backend.scoreScanStatus
            color: theme.muted
            font.pixelSize: 11
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: root.tr("Only known NVRAM layouts are decoded; other files are listed as unsupported.")
                color: theme.muted
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }
            AppButton { text: root.tr("Close"); onClicked: root.close() }
        }

    }

    FolderDialog {
        id: folderDialog
        title: root.tr("Choose PinMAME NVRAM folder")
        onAccepted: backend.setNvramDirectory(backend.urlToPath(selectedFolder))
    }
}
