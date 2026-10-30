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

    property string sortLabel: "Nazwa"
    readonly property var tileNames: ["Małe", "Średnie", "Duże", "Bardzo duże", "Ogromne"]
    readonly property var tileWidths: [160, 210, 280, 380, 520]

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
                placeholderText: "Szukaj stołu lub autora (Ctrl+F)"
                onTextChanged: backend.setQuery(text)
            }
            Item { Layout.fillWidth: true }
            AppButton {
                id: favBtn
                text: "Tylko ulubione"
                checkable: true
                onToggled: backend.setFavoritesOnly(checked)
            }
            AppButton {
                id: sortBtn
                text: "Sortuj: " + win.sortLabel
                onClicked: sortMenu.popup(sortBtn, 0, sortBtn.height + 4)
            }
            AppButton {
                id: sizeBtn
                text: "Kafelki: " + win.tileNames[backend.tileSize]
                onClicked: sizeMenu.popup(sizeBtn, 0, sizeBtn.height + 4)
            }
            AppButton {
                id: libBtn
                text: "Biblioteka"
                onClicked: libMenu.popup(libBtn, 0, libBtn.height + 4)
            }
            AppButton { text: "Ustawienia"; onClicked: settingsDialog.open() }
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
            text: "Ekran gry: " + backend.monitorLabel
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
            text: "Pokaż log gry"
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
            text: "Biblioteka jest pusta"
            color: theme.text
            font.pixelSize: 22
            font.weight: Font.DemiBold
            Layout.alignment: Qt.AlignHCenter
        }
        Text {
            text: "Zeskanuj folder ze stołami .vpx, dodaj pliki albo upuść je na to okno."
            color: theme.muted
            font.pixelSize: 14
            Layout.alignment: Qt.AlignHCenter
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 8
            AppButton { text: "Skanuj foldery"; accent: true; onClicked: backend.scan() }
            AppButton { text: "Dodaj stół…"; onClicked: addDialog.open() }
        }
    }

    // Stan pusty: filtr nic nie znalazł
    Text {
        anchors.centerIn: parent
        visible: grid.count === 0 && backend.totalTables > 0
        text: "Nic nie pasuje do wyszukiwania ani filtra."
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
        AppMenuItem { text: "Skanuj foldery"; enabled: !backend.scanning; onTriggered: backend.scan() }
        AppMenuItem { text: "Dodaj stół…"; onTriggered: addDialog.open() }
        AppMenuItem {
            text: "Pobierz brakujące grafiki"
            enabled: !backend.fetchingArt
            onTriggered: backend.fetchArtwork()
        }
        AppMenuItem {
            text: backend.removedCount > 0 ? "Przywróć usunięte stoły (" + backend.removedCount + ")" : "Przywróć usunięte stoły"
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
        AppMenuItem { text: "Małe"; onTriggered: backend.setTileSize(0) }
        AppMenuItem { text: "Średnie"; onTriggered: backend.setTileSize(1) }
        AppMenuItem { text: "Duże"; onTriggered: backend.setTileSize(2) }
        AppMenuItem { text: "Bardzo duże"; onTriggered: backend.setTileSize(3) }
        AppMenuItem { text: "Ogromne"; onTriggered: backend.setTileSize(4) }
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
        AppMenuItem { text: "Nazwa"; onTriggered: win.setSort("name", "Nazwa") }
        AppMenuItem { text: "Ostatnio grane"; onTriggered: win.setSort("recent", "Ostatnio grane") }
        AppMenuItem { text: "Najczęściej grane"; onTriggered: win.setSort("most", "Najczęściej grane") }
        AppMenuItem { text: "Ostatnio dodane"; onTriggered: win.setSort("added", "Ostatnio dodane") }
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
        AppMenuItem { text: "Graj"; onTriggered: backend.launch(cardMenu.tableId) }
        AppMenuItem {
            text: cardMenu.isFavorite ? "Usuń z ulubionych" : "Dodaj do ulubionych"
            onTriggered: backend.toggleFavorite(cardMenu.tableId)
        }
        AppMenuItem {
            text: "Wybierz grafikę…"
            onTriggered: {
                imageDialog.targetId = cardMenu.tableId
                imageDialog.open()
            }
        }
        AppMenuItem {
            text: "Znajdź grafikę online"
            enabled: !backend.fetchingArt
            onTriggered: backend.fetchArtworkFor(cardMenu.tableId)
        }
        AppMenuItem { text: "Usuń grafikę"; onTriggered: backend.clearArtwork(cardMenu.tableId) }
        AppMenuItem { text: "Usuń z biblioteki"; onTriggered: backend.removeTable(cardMenu.tableId) }
    }

    FileDialog {
        id: addDialog
        title: "Dodaj stoły"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["Stoły Visual Pinball (*.vpx)"]
        onAccepted: backend.addTables(selectedFiles)
    }

    FileDialog {
        id: imageDialog
        property int targetId: -1
        title: "Wybierz grafikę stołu"
        nameFilters: ["Obrazy (*.png *.jpg *.jpeg *.webp)"]
        onAccepted: backend.setArtwork(targetId, selectedFile)
    }

    SettingsDialog { id: settingsDialog }
    LogDialog { id: logDialog }
}
