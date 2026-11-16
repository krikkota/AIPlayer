import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: panel
    required property var config
    property alias queryText: prompt.text
    readonly property bool settingsVisible: modelSettings.visible
    readonly property bool running: config.operation === "semantic"
    readonly property bool hasTranscript: config.transcriptReady && bridge.rows.length > 0
    property int lastResult: -1
    signal showTranscript(int index)
    spacing: 12

    function launch() {
        if (!config.selectedModel.length) panel.openSettings()
        else if (prompt.text.trim().length && panel.hasTranscript && !config.busy)
            bridge.findMeaning(prompt.text)
    }
    function openSettings() { modelSettings.open(); bridge.refreshOllama() }
    Connections {
        target: bridge
        function onMeaningSettingsRequested() { panel.openSettings() }
        function onChanged() {
            if (panel.config.meaningIndex >= 0 && panel.config.meaningIndex !== panel.lastResult) {
                results.positionViewAtIndex(panel.config.meaningIndex, ListView.Contain)
            }
            panel.lastResult = panel.config.meaningIndex
        }
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        Text { textFormat: Text.PlainText;
            text: "Найдите обсуждение темы, даже если в записи использованы другие слова."
            color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 13
            lineHeight: 1.4; wrapMode: Text.WordWrap; Layout.fillWidth: true
        }
        PButton {
            id: settingsButton
            objectName: "meaningSettingsButton"
            iconName: "settings"; quiet: true
            Layout.alignment: Qt.AlignTop
            hint: modelSettings.visible ? "" : "Настройки смыслового поиска"
            Accessible.name: "Настройки смыслового поиска"
            onClicked: panel.openSettings()
        }
    }
    Popup {
        id: modelSettings
        objectName: "meaningSettingsPopup"
        x: panel.width-width
        y: settingsButton.y+settingsButton.height+8
        width: Math.min(360, panel.width)
        padding: 16
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: "#181818"; radius: 12; border.color: "#38383c" }
        contentItem: ColumnLayout {
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                Label { text: "Модель Ollama"; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 14; font.weight: Font.Medium; Layout.fillWidth: true }
                PButton { objectName: "refreshMeaningModels"; iconName: "refresh-cw"; quiet: true; implicitHeight: 26; iconSize: 14; hint: "Обновить список моделей"; enabled: panel.config.ollamaState!=="checking"; onClicked: bridge.refreshOllama() }
            }
            ModelChoice {
                id: modelChoice
                objectName: "meaningModelCombo"
                Layout.fillWidth: true
                config: panel.config
            }
            Text { textFormat: Text.PlainText;
                Layout.fillWidth: true
                text: panel.config.ollamaState==="checking" ? "Обновляем список…"
                      : panel.config.ollamaError.length ? panel.config.ollamaError
                      : modelChoice.count===0 ? "Нет доступных локальных моделей до 3 ГБ. Добавьте модель в Ollama и обновите список."
                      : "Локальные модели до 3 ГБ. Выбор сохраняется сразу."
                color: panel.config.ollamaError.length ? "#f0b9ae" : "#a1a1aa"
                font.family: "Onest"; font.pixelSize: 12; wrapMode: Text.WordWrap; lineHeight: 1.35
            }
        }
    }
    ColumnLayout {
        Layout.fillWidth: true; spacing: 6
        Label { text: "Что найти в записи"; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 12 }
        ScrollView {
            Layout.fillWidth: true; Layout.preferredHeight: 84
            clip: true
            TextArea {
                id: prompt
                objectName: "meaningQuery"
                placeholderText: "Например: где обсуждают перенос сроков и его причины"
                Accessible.name: "Что найти в записи"
                wrapMode: TextEdit.Wrap
                color: "#eeeef0"; placeholderTextColor: "#a1a1aa"
                selectionColor: "#5b526f"; selectedTextColor: "#ffffff"
                font.family: "Onest"; font.pixelSize: 13
                padding: 12
                background: Rectangle { color: "#181818"; radius: 8; border.color: prompt.activeFocus ? "#b9b1f0" : "#303034" }
                onTextChanged: bridge.editMeaning(text)
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 8
        PButton {
            objectName: "semanticFind"
            text: "Найти фрагменты"
            primary: true
            visible: !panel.running
            enabled: panel.config.selectedModel.length>0 && prompt.text.trim().length > 0 && panel.hasTranscript && !panel.config.busy
            hint: Qt.platform.os === "osx" ? "Запустить поиск · ⌘Enter" : "Запустить поиск · Ctrl+Enter"
            onClicked: panel.launch()
        }
        PButton { objectName: "cancelMeaning"; visible: panel.running; text: "Остановить поиск"; iconName: "x"; onClicked: bridge.cancelMeaning() }
        Item { Layout.fillWidth: true }
        Text { textFormat: Text.PlainText; visible: !panel.running; text: "По запросу · локально"; color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 11 }
        Text { textFormat: Text.PlainText; visible: panel.running && panel.config.fraction >= 0; text: Math.round(panel.config.fraction*100) + "%"; color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 12 }
    }
    ProgressBar {
        visible: panel.running
        Layout.fillWidth: true; implicitHeight: 3
        indeterminate: panel.config.fraction < 0
        value: Math.max(0, panel.config.fraction)
        palette.highlight: "#b9b1f0"
    }
    Text { textFormat: Text.PlainText;
        objectName: "meaningFeedback"
        text: panel.running ? panel.config.status
              : panel.config.meaningError.length ? panel.config.meaningError
              : panel.config.meaningNotice.length ? panel.config.meaningNotice
              : !panel.config.selectedModel.length ? "Выберите модель через шестерёнку настроек поиска."
              : panel.config.meaningPerformed ? panel.config.meaningCount === 0 ? "По этой теме ничего не найдено. Попробуйте другой запрос."
                  : "Фрагментов: " + panel.config.meaningCount + " · " + panel.config.meaningHint
              : !panel.config.transcriptReady ? "Сначала откройте запись и дождитесь готовой расшифровки."
              : !panel.hasTranscript ? "В записи не обнаружена речь. Для поиска нужна расшифровка."
              : "Модель запускается по кнопке. Первый поиск может занять больше времени."
        color: panel.config.meaningError.length ? "#f0b9ae" : "#a1a1aa"
        font.family: "Onest"; font.pixelSize: 12; lineHeight: 1.35
        wrapMode: Text.WordWrap; Layout.fillWidth: true
        Accessible.role: Accessible.StaticText
        Accessible.name: text
    }
    ListView {
        id: results
        objectName: "meaningResultsView"
        Layout.fillWidth: true; Layout.fillHeight: true
        clip: true; spacing: 8
        model: bridge.meaningResults
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        delegate: ItemDelegate {
            id: hit
            required property var modelData
            required property int index
            objectName: "meaningResult_" + index
            width: ListView.view.width
            height: content.implicitHeight + 24
            padding: 12
            hoverEnabled: true
            Accessible.name: modelData.time + ". " + modelData.text
            background: Rectangle { radius: 9; color: panel.config.meaningIndex === hit.index ? "#25232b" : hit.hovered ? "#202022" : "#181818" }
            contentItem: ColumnLayout {
                id: content
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    Text { textFormat: Text.PlainText; text: hit.modelData.time + " — " + hit.modelData.endTime; color: "#c8bfef"; font.family: "Onest"; font.pixelSize: 12; Layout.fillWidth: true }
                    PButton {
                        objectName: "revealMeaning_" + hit.index
                        quiet: true; implicitHeight: 24; iconName: "file-text"; iconSize: 14
                        hint: "Показать в расшифровке"
                        onClicked: panel.showTranscript(hit.index)
                    }
                }
                Text { textFormat: Text.PlainText; text: hit.modelData.text; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 13; lineHeight: 1.4; wrapMode: Text.WordWrap; maximumLineCount: 4; elide: Text.ElideRight; Layout.fillWidth: true }
            }
            onClicked: bridge.selectMeaningResult(index)
        }
        Text { textFormat: Text.PlainText;
            visible: !panel.running && !panel.config.meaningPerformed && !panel.config.meaningError.length
            anchors.centerIn: parent; width: parent.width - 24
            text: "Найденные фрагменты появятся здесь.\nНажмите на фрагмент, чтобы перейти к нему."
            color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12; lineHeight: 1.5
            horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
        }
    }
    RowLayout {
        visible: panel.config.meaningCount > 0
        Layout.fillWidth: true
        Text { textFormat: Text.PlainText; text: panel.config.meaningIndex >= 0 ? (panel.config.meaningIndex+1) + " из " + panel.config.meaningCount : "Выберите фрагмент"; color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 12; Layout.fillWidth: true }
        PButton { objectName: "previousMeaning"; iconName: "chevron-left"; hint: "Предыдущий фрагмент"; onClicked: bridge.navigateMeaning(-1) }
        PButton { objectName: "nextMeaning"; iconName: "chevron-right"; hint: "Следующий фрагмент"; onClicked: bridge.navigateMeaning(1) }
    }
}
