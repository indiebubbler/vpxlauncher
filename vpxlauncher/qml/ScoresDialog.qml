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
            return record.label + (record.initials ? " · " + record.initials : "")
        if (record.status === "empty")
            return root.tr("No high score stored")
        if (record.status === "unsupported")
            return root.tr("Unsupported NVRAM format")
        if (record.status === "invalid")
            return root.tr("Could not decode NVRAM") + ": " + record.error
        return root.tr("Could not read NVRAM file") + ": " + record.error
    }

    function groupRecords(records) {
        const groups = []
        for (let i = 0; i < records.length; i++) {
            const record = records[i]
            let group = groups.length > 0 ? groups[groups.length - 1] : null
            if (!group || group.rom !== record.rom) {
                group = { title: record.title, rom: record.rom, records: [] }
                groups.push(group)
            }
            group.records.push(record)
        }
        return groups
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

        ListView {
            id: scoreList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.groupRecords(backend.scoreRecords)
            spacing: 8
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                required property var modelData
                width: scoreList.width
                height: 46 + modelData.records.length * 36
                radius: 8
                color: theme.raised
                border.width: 1
                border.color: theme.line

                Column {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 2

                    RowLayout {
                        width: parent.width
                        height: 30
                        Text {
                            Layout.fillWidth: true
                            text: modelData.title
                            color: theme.text
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.rom
                            color: theme.muted
                            font.pixelSize: 11
                        }
                    }

                    Repeater {
                        model: modelData.records
                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            width: parent.width
                            height: 34
                            radius: 4
                            color: index % 2 === 0 ? theme.surface : theme.bg

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 12
                                Text {
                                    Layout.fillWidth: true
                                    text: root.recordStatus(modelData)
                                    color: modelData.status === "score" ? theme.lamp : theme.muted
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
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
                text: root.tr("Only the first five entries in known NVRAM layouts are decoded; other files are listed as unsupported.")
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
