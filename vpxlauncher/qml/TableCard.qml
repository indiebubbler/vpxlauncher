import QtQuick
import QtQuick.Controls.Basic

// Kafelek stołu: grafika, ulubione, "żarówka" Graj, tytuł i autor.
Item {
    id: root

    required property int index
    required property int tableId
    required property string title
    required property string author
    required property string artwork
    required property bool favorite
    required property int playCount
    required property string lastPlayed

    property bool running: false
    property bool dropping: false
    property real k: 1.0   // skala czcionek i przycisków dla dużych kafelków

    signal play()
    signal favoriteToggled()
    signal contextRequested()
    signal imageDropped(var urls)

    readonly property bool focused: GridView.isCurrentItem && GridView.view.activeFocus
    readonly property bool hot: hover.containsMouse || lampArea.containsMouse
                                || starArea.containsMouse || focused

    function tr(message) {
        const currentLanguage = backend.language
        return backend.translate(message)
    }

    Rectangle {
        id: card
        anchors.fill: parent
        anchors.margins: 8
        radius: 8
        color: theme.surface
        border.width: (root.dropping || root.focused) ? 2 : 1
        border.color: (root.dropping || root.focused) ? theme.lamp : (root.hot ? theme.muted : theme.line)

        MouseArea {
            id: hover
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: (mouse) => {
                root.GridView.view.currentIndex = root.index
                root.GridView.view.forceActiveFocus()
                if (mouse.button === Qt.RightButton)
                    root.contextRequested()
            }
            onDoubleClicked: (mouse) => {
                if (mouse.button === Qt.LeftButton)
                    root.play()
            }
        }

        Rectangle {
            id: art
            x: 8
            y: 8
            width: card.width - 16
            height: Math.round(width * 1.2)
            color: theme.raised

            Image {
                anchors.fill: parent
                source: root.artwork
                visible: root.artwork !== ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize.width: Math.round(art.width * 1.5)
            }

            Text {
                anchors.centerIn: parent
                visible: root.artwork === ""
                text: root.title.length > 0 ? root.title.charAt(0).toUpperCase() : "?"
                color: theme.line
                font.pixelSize: Math.round(art.width * 0.45)
                font.weight: Font.DemiBold
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 12
                visible: root.artwork === "" && root.hot
                text: root.tr("Drop an image here")
                color: theme.muted
                font.pixelSize: Math.round(12 * root.k)
            }

            Rectangle {
                id: star
                width: Math.round(32 * root.k)
                height: width
                radius: width / 2
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: 8
                color: "#cc0f1623"
                visible: root.favorite || root.hot

                Text {
                    anchors.centerIn: parent
                    text: root.favorite ? "★" : "☆"
                    color: root.favorite ? theme.lamp : theme.text
                    font.pixelSize: Math.round(16 * root.k)
                }
                MouseArea {
                    id: starArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.favoriteToggled()
                }
            }

            // Jedyny mocny element: bursztynowa "żarówka" uruchamiająca stół.
            Rectangle {
                id: lamp
                width: Math.round(48 * root.k)
                height: width
                radius: width / 2
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 12
                color: root.running ? theme.line : theme.lamp
                opacity: root.hot ? 1 : 0
                visible: opacity > 0
                Behavior on opacity { NumberAnimation { duration: 120 } }

                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width + 10
                    height: width
                    radius: width / 2
                    color: "transparent"
                    border.width: 2
                    border.color: theme.lamp
                    opacity: 0.35
                    visible: !root.running
                }
                Text {
                    anchors.centerIn: parent
                    anchors.horizontalCenterOffset: 2
                    text: "▶"
                    color: "#1a1204"
                    font.pixelSize: Math.round(18 * root.k)
                }
                MouseArea {
                    id: lampArea
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: !root.running
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.play()
                }
            }
        }

        Column {
            x: 8
            y: art.y + art.height + 8
            width: card.width - 16
            spacing: 2

            Text {
                width: parent.width
                text: root.title
                color: theme.text
                font.pixelSize: Math.round(14 * root.k)
                font.weight: Font.Medium
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                visible: text !== ""
                text: root.author
                color: theme.muted
                font.pixelSize: Math.round(12 * root.k)
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                visible: text !== ""
                text: root.lastPlayed !== ""
                      ? root.tr("Last played: {date}").replace("{date}", root.lastPlayed)
                      : ""
                color: theme.muted
                font.pixelSize: Math.round(11 * root.k)
                elide: Text.ElideRight
            }
        }
    }

    DropArea {
        anchors.fill: parent
        onEntered: (drag) => { root.dropping = drag.hasUrls }
        onExited: root.dropping = false
        onDropped: (drop) => {
            root.dropping = false
            if (drop.hasUrls) {
                root.imageDropped(drop.urls)
                drop.accept()
            }
        }
    }
}
