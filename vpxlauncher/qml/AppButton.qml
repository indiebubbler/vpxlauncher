import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control
    property bool accent: false

    implicitHeight: 38
    leftPadding: 14
    rightPadding: 14
    font.pixelSize: 13

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.accent ? "#1a1204" : theme.text
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: 8
        color: control.accent
               ? (control.down ? theme.lampDeep : theme.lamp)
               : (control.down || control.checked ? theme.line : (control.hovered ? theme.raised : theme.surface))
        border.width: 1
        border.color: control.visualFocus ? theme.lamp : (control.accent ? "transparent" : theme.line)
    }
}
