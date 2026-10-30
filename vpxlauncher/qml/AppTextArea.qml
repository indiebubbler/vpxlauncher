import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: root
    property alias text: area.text
    property alias placeholderText: area.placeholderText

    implicitHeight: 92
    radius: 8
    color: theme.bg
    border.width: 1
    border.color: area.activeFocus ? theme.lamp : theme.line

    ScrollView {
        anchors.fill: parent
        anchors.margins: 2
        clip: true

        TextArea {
            id: area
            color: theme.text
            placeholderTextColor: theme.muted
            selectionColor: theme.lampDeep
            selectedTextColor: "#ffffff"
            font.pixelSize: 13
            wrapMode: TextArea.NoWrap
            leftPadding: 10
            topPadding: 8
            background: null
        }
    }
}
