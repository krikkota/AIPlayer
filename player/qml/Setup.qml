import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: overlay
    required property var config
    color: "#d9080808"
    z: 100
    focus: visible
    Accessible.name: "Настройка моделей"
    MouseArea { anchors.fill: parent }
    Rectangle {
        id: surface
        width: Math.min(640, parent.width-48)
        height: Math.min(570, parent.height-48)
        Behavior on height { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
        anchors.centerIn: parent
        color: "#101010"
        radius: 20
        border.color: "#303033"
        border.width: 1
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 30
            spacing: 20
            RowLayout {
                Layout.fillWidth: true
                Text { textFormat: Text.PlainText;
                    text: overlay.config.settingsOpen ? "Модели и подключение" : "Подготовим плеер"
                    color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 24; font.weight: Font.Medium
                    Layout.fillWidth: true
                }
                PButton { visible: overlay.config.settingsOpen; iconName: "x"; quiet: true; hint: "Закрыть настройки"; onClicked: bridge.closeSettings() }
            }
            Rectangle {
                id: tabs
                Layout.fillWidth: true
                height: 40
                radius: 10
                color: "#080808"
                Rectangle {
                    x: overlay.config.step === 0 ? 3 : tabs.width/2
                    y: 3; width: tabs.width/2-3; height: 34; radius: 8
                    color: "#242426"; border.color: "#39393d"
                    Behavior on x { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
                }
                Row {
                    anchors.fill: parent
                    Repeater {
                        model: ["Распознавание речи", "Ollama"]
                        Button {
                            required property int index
                            required property string modelData
                            width: tabs.width/2; height: 40
                            text: modelData
                            background: Rectangle { color:"transparent";radius:8;border.width:parent.visualFocus?1:0;border.color:"#b9b1f0" }
                            contentItem: Text { textFormat: Text.PlainText;
                                text: modelData; color: overlay.config.step===index ? "#eeeef0" : "#a1a1aa"
                                font.family: "Onest"; font.pixelSize: 13
                                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                            }
                            onClicked: bridge.setStep(index)
                        }
                    }
                }
            }
            StackLayout {
                currentIndex: overlay.config.step
                Layout.fillWidth: true
                Layout.fillHeight: true
                ScrollView {
                    id: speechSettings
                    clip: true
                    contentWidth: availableWidth
                    ColumnLayout {
                        width: speechSettings.availableWidth
                        spacing: 16
                        RowLayout {
                            spacing: 14
                            Image { source: assetRoot+"icons/audio-lines.svg"; sourceSize: Qt.size(28,28); Layout.preferredWidth: 28; Layout.preferredHeight: 28 }
                            ColumnLayout {
                                spacing: 4
                                Text { textFormat: Text.PlainText; text: "GigaAM"; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 19; font.weight: Font.Medium }
                                Text { textFormat: Text.PlainText; text: "Русская речь · локально · 225 МБ"; color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12 }
                            }
                            Item { Layout.fillWidth: true }
                            Image { visible: overlay.config.asrReady; source: assetRoot+"icons/check.svg"; sourceSize: Qt.size(20,20); Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
                        }
                        Text { textFormat: Text.PlainText;
                            text: overlay.config.asrReady ? "Совместимая модель уже найдена. Можно переходить к следующему шагу."
                                  : "Модель превращает речь в текст с временными метками. Загрузим её один раз или используем уже скачанную."
                            color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 14; lineHeight: 1.5
                            wrapMode: Text.WordWrap; Layout.fillWidth: true
                        }
                        Rectangle { Layout.fillWidth: true; height: 1; color: "#28282a" }
                        Text { textFormat: Text.PlainText;
                            text: overlay.config.setupLabel
                            color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true
                        }
                        ProgressBar {
                            visible: overlay.config.setupBusy || overlay.config.asrChecking
                            Layout.fillWidth: true; implicitHeight: 3
                            indeterminate: overlay.config.setupFraction < 0
                            value: Math.max(0,overlay.config.setupFraction)
                            background: Rectangle { implicitHeight: 3; color: "#28282a"; radius: 2 }
                            contentItem: Item {
                                Rectangle { width: parent.width * (parent.parent.indeterminate ? .3 : parent.parent.visualPosition); height: 3; color: "#b9b1f0"; radius: 2 }
                            }
                        }
                        RowLayout {
                            visible: !overlay.config.asrReady && !overlay.config.asrChecking
                            spacing: 10
                            PButton { text: "Загрузить модель"; iconName: "download"; primary: true; enabled: !overlay.config.setupBusy; onClicked: bridge.downloadModel() }
                            PButton { text: "Указать папку"; iconName: "folder-open"; enabled: !overlay.config.setupBusy; onClicked: bridge.chooseModelFolder() }
                        }
                        PButton { visible: overlay.config.setupBusy; text: "Отменить загрузку"; quiet: true; onClicked: bridge.cancelSetup() }
                        Text { textFormat: Text.PlainText; visible: overlay.config.setupError.length>0; text: overlay.config.setupError; color: "#f0b9ae"; font.family: "Onest"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        SegmentationSetup { config: overlay.config; Layout.fillWidth: true }
                    }
                }
                ColumnLayout {
                    spacing: 13
                    RowLayout {
                        spacing: 14
                        Image { source: assetRoot+"ollama-light.svg"; fillMode: Image.PreserveAspectFit; Layout.preferredWidth: 30; Layout.preferredHeight: 44; sourceSize: Qt.size(60,88) }
                        ColumnLayout {
                            spacing: 3
                            Text { textFormat: Text.PlainText; text: "Ollama"; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 19; font.weight: Font.Medium }
                            Text { textFormat: Text.PlainText; text: "Модели для поиска по смыслу"; color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12 }
                        }
                        Item { Layout.fillWidth: true }
                        PButton { iconName: "refresh-cw"; hint: "Обновить список моделей"; enabled: overlay.config.ollamaState!=="checking"; onClicked: bridge.refreshOllama() }
                    }
                    Text { textFormat: Text.PlainText; text: "Подключим уже установленные модели. Веса остаются в Ollama, без повторной загрузки."; color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 13; lineHeight: 1.45; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Rectangle { Layout.fillWidth: true; height: 1; color: "#28282a" }
                    Text { textFormat: Text.PlainText;
                        visible: overlay.config.ollamaState!=="ready"
                        text: overlay.config.ollamaState==="checking" ? "Проверяем подключение…"
                              : overlay.config.ollamaState==="empty" ? "Ollama доступна. Добавьте локальную модель в Ollama и обновите список."
                              : "Запустите Ollama, чтобы выбрать модель. Настроить это можно и позже."
                        color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true
                    }
                    ListView {
                        visible: overlay.config.models.length>0
                        Layout.fillWidth: true; Layout.fillHeight: true
                        clip: true; spacing: 6
                        model: overlay.config.models
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        delegate: ItemDelegate {
                            required property var modelData
                            objectName: "ollamaModel_" + modelData.name
                            width: ListView.view.width; height: 59
                            enabled: modelData.fits
                            background: Rectangle { radius: 12; color: overlay.config.selectedModel===modelData.name ? "#27252e" : parent.hovered ? "#1d1d1f" : "#181818" }
                            contentItem: RowLayout {
                                spacing: 12
                                ColumnLayout {
                                    spacing: 4; Layout.fillWidth: true
                                    Text { textFormat: Text.PlainText; text: modelData.name; color: modelData.fits ? "#eeeef0" : "#8c8c93"; font.family: "Onest"; font.pixelSize: 13; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Text { textFormat: Text.PlainText; text: (modelData.kind==="embedding" ? "Смысловой поиск" : "Обработка запросов") + " · " + modelData.sizeLabel + (modelData.fits ? "" : " · больше 3 ГБ"); color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 11 }
                                }
                                Image { visible: overlay.config.selectedModel===modelData.name; source: assetRoot+"icons/check.svg"; sourceSize: Qt.size(17,17); Layout.preferredWidth: 17; Layout.preferredHeight: 17 }
                            }
                            onClicked: bridge.selectOllamaModel(modelData.name)
                        }
                    }
                    RowLayout {
                        visible: overlay.config.ollamaState!=="ready" && overlay.config.ollamaState!=="checking"
                        spacing: 10
                        PButton { text: "Запустить Ollama"; onClicked: bridge.launchOllama() }
                        PButton { text: "Установить"; iconName: "external-link"; quiet: true; onClicked: bridge.installOllama() }
                    }
                    Text { textFormat: Text.PlainText; visible: overlay.config.ollamaError.length>0; text: overlay.config.ollamaError; color: "#f0b9ae"; font.family: "Onest"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Item { Layout.fillHeight: true; visible: overlay.config.models.length===0 }
                    Text { textFormat: Text.PlainText; text: "Рекомендуемый предел — 3 ГБ. Смысловой поиск запускается только по вашему запросу."; color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#28282a" }
            RowLayout {
                Layout.fillWidth: true
                PButton { visible: !overlay.config.settingsOpen; text: "Настроить позже"; quiet: true; enabled: !overlay.config.setupBusy; onClicked: bridge.finishSetup() }
                Item { Layout.fillWidth: true }
                PButton {
                    objectName: "finishModelSettings"
                    text: overlay.config.settingsOpen ? "Готово" : overlay.config.step===0 ? "Продолжить" : "Открыть плеер"
                    iconName: overlay.config.settingsOpen ? "" : "arrow-right"; primary: true; enabled: !overlay.config.setupBusy && (overlay.config.settingsOpen || !overlay.config.asrChecking)
                    onClicked: overlay.config.settingsOpen ? bridge.closeSettings() : overlay.config.step===0 ? bridge.setStep(1) : bridge.finishSetup()
                }
            }
        }
    }
}

