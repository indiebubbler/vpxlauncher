import QtQuick
import QtQuick.Controls.Basic

TextField {
    id: control
    implicitHeight: 38
    color: theme.text
    placeholderTextColor: theme.muted
    selectionColor: theme.lampDeep
    selectedTextColor: "#ffffff"
    font.pixelSize: 13
    leftPadding: 12
    rightPadding: 12
    background: Rectangle {
        radius: 8
        color: theme.bg
        border.width: 1
        border.color: control.activeFocus ? theme.lamp : theme.line
    }
}
