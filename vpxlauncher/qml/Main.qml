import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: win
    width: 1280
    height: 820
    minimumWidth: 1000
    minimumHeight: 720
    visible: true
    title: "VPX Launcher"
    color: theme.bg

    property string sortLabel: "Name"
    readonly property var tileNames: ["Small", "Medium", "Large", "Very large", "Huge"]
    readonly property var tileWidths: [160, 210, 280, 380, 520]

    function tr(message) {
        const currentLanguage = backend.language
        return backend.translate(message)
    }

    function stepTile(delta) {
        backend.setTileSize(Math.max(0, Math.min(4, backend.tileSize + delta)))
    }

    function setSort(key, label) {
        sortLabel = label
        backend.setSort(key)
    }

    component AppMenuItem: MenuItem {
        id: mi
        implicitHeight: 34
        contentItem: Text {
            text: mi.text
            color: mi.enabled ? theme.text : theme.muted
            font.pixelSize: 13
            verticalAlignment: Text.AlignVCenter
            leftPadding: 6
        }
        background: Rectangle {
            radius: 6
            color: mi.highlighted ? theme.line : "transparent"
        }
    }

    Shortcut { sequence: "Ctrl+F"; onActivated: search.forceActiveFocus() }
    Shortcut { sequences: ["Ctrl++", "Ctrl+="]; onActivated: win.stepTile(1) }
    Shortcut { sequence: "Ctrl+-"; onActivated: win.stepTile(-1) }

    Connections {
        target: backend
        function onSettingsRequested() { settingsDialog.open() }
    }

    // Upuszczenie plików .vpx lub folderów w dowolnym miejscu okna dodaje je do biblioteki.
    DropArea {
        anchors.fill: parent
        onDropped: (drop) => { if (drop.hasUrls) backend.handleDrop(drop.urls) }
    }

    header: Rectangle {
        height: 64
        color: theme.surface

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: theme.line
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            spacing: 8

            Text {
                text: "VPX Launcher"
                color: theme.text
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.rightMargin: 12
            }
            AppTextField {
                id: search
                Layout.fillWidth: true
                Layout.maximumWidth: 420
                placeholderText: win.tr("Search tables or authors (Ctrl+F)")
                onTextChanged: backend.setQuery(text)
            }
            Item { Layout.fillWidth: true }
            AppButton {
                id: favBtn
                text: win.tr("Favorites only")
                checkable: true
                onToggled: backend.setFavoritesOnly(checked)
            }
            AppButton {
                id: sortBtn
                text: win.tr("Sort:") + " " + win.tr(win.sortLabel)
                onClicked: sortMenu.popup(sortBtn, 0, sortBtn.height + 4)
            }
            AppButton {
                id: sizeBtn
                text: win.tr("Tiles:") + " " + win.tr(win.tileNames[backend.tileSize])
                onClicked: sizeMenu.popup(sizeBtn, 0, sizeBtn.height + 4)
            }
            AppButton {
                id: libBtn
                text: win.tr("Library")
                onClicked: libMenu.popup(libBtn, 0, libBtn.height + 4)
            }
            AppButton { text: win.tr("Settings"); onClicked: settingsDialog.open() }
        }
    }

    footer: Rectangle {
        height: 34
        color: theme.surface

        Rectangle {
            anchors.top: parent.top
            width: parent.width
            height: 1
            color: theme.line
        }
        Rectangle {
            id: dot
            width: 8
            height: 8
            radius: 4
            x: 16
            anchors.verticalCenter: parent.verticalCenter
            color: theme.lamp
            visible: backend.running || backend.scanning || backend.fetchingArt
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            x: dot.visible ? 32 : 16
            width: parent.width - x - logLink.width - monitorLink.width - 72
            text: backend.status
            color: theme.muted
            font.pixelSize: 12
            elide: Text.ElideRight
        }
        Text {
            id: monitorLink
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: logLink.left
            anchors.rightMargin: 24
            text: win.tr("Game display:") + " " + backend.monitorLabel
            color: monitorArea.containsMouse ? theme.lamp : theme.muted
            font.pixelSize: 12
            font.underline: true
            MouseArea {
                id: monitorArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: monitorMenu.popup()
            }
        }
        Text {
            id: logLink
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
            anchors.rightMargin: 16
            text: win.tr("Show game log")
            color: logArea.containsMouse ? theme.lamp : theme.muted
            font.pixelSize: 12
            font.underline: true
            MouseArea {
                id: logArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: logDialog.open()
            }
        }
    }

    GridView {
        id: grid
        anchors.fill: parent
        anchors.margins: 8
        clip: true
        focus: true
        keyNavigationEnabled: true
        model: tableModel
        boundsBehavior: Flickable.StopAtBounds

        // Docelowa szerokość kafelka zależy od wybranego rozmiaru; kolumny dopasowują się do okna.
        readonly property int columns: Math.max(1, Math.floor(width / win.tileWidths[backend.tileSize]))
        cellWidth: Math.floor(width / columns)
        // Skala czcionek i przycisków rośnie razem z kafelkiem (1.0 do 1.7).
        readonly property real k: Math.min(1.7, Math.max(1.0, (cellWidth - 32) / 200))
        // 16 px marginesów komórki + 3 x 8 px odstępów + obraz 1:1,2 + blok tekstu (ok. 72 px x skala)
        cellHeight: Math.round((cellWidth - 32) * 1.2) + 40 + Math.round(72 * k)

        WheelHandler {
            acceptedModifiers: Qt.ControlModifier
            onWheel: (event) => win.stepTile(event.angleDelta.y > 0 ? 1 : -1)
        }

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
            contentItem: Rectangle {
                implicitWidth: 6
                radius: 3
                color: theme.line
            }
            background: null
        }

        Keys.onReturnPressed: { if (currentItem) backend.launch(currentItem.tableId) }
        Keys.onEnterPressed: { if (currentItem) backend.launch(currentItem.tableId) }

        delegate: TableCard {
            width: grid.cellWidth
            height: grid.cellHeight
            running: backend.running
            k: grid.k
            onPlay: backend.launch(tableId)
            onFavoriteToggled: backend.toggleFavorite(tableId)
            onImageDropped: (urls) => backend.setArtworkFromDrop(tableId, urls)
            onContextRequested: {
                cardMenu.tableId = tableId
                cardMenu.isFavorite = favorite
                cardMenu.popup()
            }
        }
    }

    // Stan pusty: biblioteka bez stołów
    ColumnLayout {
        anchors.centerIn: parent
        spacing: 12
        visible: backend.totalTables === 0 && !backend.scanning

        Text {
            text: win.tr("The library is empty")
            color: theme.text
            font.pixelSize: 22
            font.weight: Font.DemiBold
            Layout.alignment: Qt.AlignHCenter
        }
        Text {
            text: win.tr("Scan a folder with .vpx tables, add files, or drop them into this window.")
            color: theme.muted
            font.pixelSize: 14
            Layout.alignment: Qt.AlignHCenter
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 8
            AppButton { text: win.tr("Scan folders"); accent: true; onClicked: backend.scan() }
            AppButton { text: win.tr("Add table..."); onClicked: addDialog.open() }
        }
    }

    // Stan pusty: filtr nic nie znalazł
    Text {
        anchors.centerIn: parent
        visible: grid.count === 0 && backend.totalTables > 0
        text: win.tr("No tables match the search or filter.")
        color: theme.muted
        font.pixelSize: 14
    }

    Menu {
        id: libMenu
        padding: 6
        background: Rectangle {
            implicitWidth: 260
            radius: 8
            color: theme.raised
            border.width: 1
            border.color: theme.line
        }
        AppMenuItem { text: win.tr("Scan folders"); enabled: !backend.scanning; onTriggered: backend.scan() }
        AppMenuItem { text: win.tr("Add table..."); onTriggered: addDialog.open() }
        AppMenuItem {
            text: win.tr("Download missing artwork")
            enabled: !backend.fetchingArt
            onTriggered: backend.fetchArtwork()
        }
        AppMenuItem {
            text: backend.removedCount > 0
                  ? win.tr("Restore removed tables ({count})").replace("{count}", backend.removedCount)
                  : win.tr("Restore removed tables")
            enabled: backend.removedCount > 0
            onTriggered: backend.restoreRemoved()
        }
    }

    Menu {
        id: monitorMenu
        padding: 6
        background: Rectangle {
            implicitWidth: 380
            radius: 8
            color: theme.raised
            border.width: 1
            border.color: theme.line
        }
        Repeater {
            model: backend.monitorChoices
            delegate: AppMenuItem {
                required property int index
                required property string modelData
                text: (index === backend.monitorIndex ? "✓  " : "     ") + modelData
                onTriggered: backend.setMonitorChoice(index)
            }
        }
    }

    Menu {
        id: sizeMenu
        padding: 6
        background: Rectangle {
            implicitWidth: 220
            radius: 8
            color: theme.raised
            border.width: 1
            border.color: theme.line
        }
        AppMenuItem { text: win.tr("Small"); onTriggered: backend.setTileSize(0) }
        AppMenuItem { text: win.tr("Medium"); onTriggered: backend.setTileSize(1) }
        AppMenuItem { text: win.tr("Large"); onTriggered: backend.setTileSize(2) }
        AppMenuItem { text: win.tr("Very large"); onTriggered: backend.setTileSize(3) }
        AppMenuItem { text: win.tr("Huge"); onTriggered: backend.setTileSize(4) }
    }

    Menu {
        id: sortMenu
        padding: 6
        background: Rectangle {
            implicitWidth: 200
            radius: 8
            color: theme.raised
            border.width: 1
            border.color: theme.line
        }
        AppMenuItem { text: win.tr("Name"); onTriggered: win.setSort("name", "Name") }
        AppMenuItem { text: win.tr("Recently played"); onTriggered: win.setSort("recent", "Recently played") }
        AppMenuItem { text: win.tr("Most played"); onTriggered: win.setSort("most", "Most played") }
        AppMenuItem { text: win.tr("Recently added"); onTriggered: win.setSort("added", "Recently added") }
    }

    Menu {
        id: cardMenu
        property int tableId: -1
        property bool isFavorite: false
        padding: 6
        background: Rectangle {
            implicitWidth: 220
            radius: 8
            color: theme.raised
            border.width: 1
            border.color: theme.line
        }
        AppMenuItem { text: win.tr("Play"); onTriggered: backend.launch(cardMenu.tableId) }
        AppMenuItem {
            text: cardMenu.isFavorite ? win.tr("Remove from favorites") : win.tr("Add to favorites")
            onTriggered: backend.toggleFavorite(cardMenu.tableId)
        }
        AppMenuItem {
            text: win.tr("Choose artwork...")
            onTriggered: {
                imageDialog.targetId = cardMenu.tableId
                imageDialog.open()
            }
        }
        AppMenuItem {
            text: win.tr("Find artwork online")
            enabled: !backend.fetchingArt
            onTriggered: backend.fetchArtworkFor(cardMenu.tableId)
        }
        AppMenuItem { text: win.tr("Remove artwork"); onTriggered: backend.clearArtwork(cardMenu.tableId) }
        AppMenuItem { text: win.tr("Remove from library"); onTriggered: backend.removeTable(cardMenu.tableId) }
    }

    FileDialog {
        id: addDialog
        title: win.tr("Add tables")
        fileMode: FileDialog.OpenFiles
        nameFilters: [win.tr("Visual Pinball tables (*.vpx)")]
        onAccepted: backend.addTables(selectedFiles)
    }

    FileDialog {
        id: imageDialog
        property int targetId: -1
        title: win.tr("Choose table artwork")
        nameFilters: [win.tr("Images (*.png *.jpg *.jpeg *.webp)")]
        onAccepted: backend.setArtwork(targetId, selectedFile)
    }

    SettingsDialog { id: settingsDialog }
    LogDialog { id: logDialog }
}
