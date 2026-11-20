import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: welcome
    objectName: "firstRunOverlay"
    required property var config
    readonly property bool selectedAvailable: bridge.meaningModels.some(item => item.name===config.selectedModel)
    color: "#ed080808"
    z: 110
    focus: visible
    Accessible.name: "Первый запуск плеера"
    MouseArea { anchors.fill: parent }
    Rectangle {
        id: surface
        anchors.centerIn: parent
        width: Math.min(820, parent.width-48)
        height: Math.min(600, parent.height-48)
        radius: 18; color: "#101010"; border.color: "#303034"
        RowLayout {
            anchors.fill: parent; anchors.margins: 30; spacing: 30
            ColumnLayout {
                Layout.preferredWidth: 166; Layout.fillHeight: true; spacing: 24
                RowLayout {
                    spacing: 10
                    Image { source: assetRoot+"icons/audio-lines.svg"; sourceSize: Qt.size(48,48); Layout.preferredWidth: 24; Layout.preferredHeight: 24 }
                    Text { textFormat: Text.PlainText; text: "Плеер"; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 19; font.weight: Font.Medium }
                }
                ColumnLayout {
                    spacing: 10; Layout.fillWidth: true
                    Repeater {
                        model: ["Речь в текст", "Поиск по смыслу", "Первая запись"]
                        Button {
                            required property int index
                            required property string modelData
                            objectName: "onboardingStep_"+index
                            Layout.fillWidth: true; implicitHeight: 40
                            enabled: !welcome.config.setupBusy
                            Accessible.name: modelData + ", шаг " + (index+1) + " из 3"
                            background: Rectangle { color: "transparent"; radius: 8; border.width: parent.visualFocus ? 1 : 0; border.color: "#b9b1f0" }
                            contentItem: RowLayout {
                                spacing: 10
                                Rectangle {
                                    Layout.preferredWidth: 24; Layout.preferredHeight: 24; radius: 12
                                    color: welcome.config.step===index ? "#ecebf2" : "#242426"
                                    Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: index+1; color: welcome.config.step===index ? "#101010" : "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12 }
                                }
                                Text { textFormat: Text.PlainText; text: modelData; color: welcome.config.step===index ? "#eeeef0" : "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12; Layout.fillWidth: true }
                            }
                            onClicked: bridge.setStep(index)
                        }
                    }
                }
                Item { Layout.fillHeight: true }
            }
            Rectangle { Layout.fillHeight: true; Layout.preferredWidth: 1; color: "#29292d" }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 20
                RowLayout {
                    Layout.fillWidth: true
                    Item { Layout.fillWidth: true }
                    PButton { objectName: "deferOnboarding"; text: "Настроить позже"; quiet: true; implicitHeight: 28; onClicked: bridge.finishSetup() }
                }
                StackLayout {
                    currentIndex: welcome.config.step
                    Layout.fillWidth: true; Layout.fillHeight: true
                    ScrollView {
                        id: page0
                        clip: true
                        contentWidth: availableWidth
                        ColumnLayout {
                            width: page0.availableWidth
                            spacing: 12
                            Text { textFormat: Text.PlainText; text: "Настройте расшифровку"; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 27; font.weight: Font.Medium; lineHeight: 1.15; Layout.fillWidth: true }
                            ColumnLayout {
                                visible: !welcome.config.asrReady
                                Layout.fillWidth: true
                                spacing: 6

                                Text {
                                    textFormat: Text.PlainText
                                    text: "Скачайте модель, чтобы плеер мог превращать речь из записи в текст."
                                    color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 14
                                    wrapMode: Text.WordWrap; Layout.fillWidth: true
                                }
                                Text {
                                    textFormat: Text.PlainText
                                    text: "Это нужно сделать один раз. Дальше расшифровка работает без интернета."
                                    color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 12
                                    wrapMode: Text.WordWrap; Layout.fillWidth: true
                                }
                            }
                            RowLayout {
                                visible: welcome.config.asrReady
                                Layout.fillWidth: true
                                spacing: 8

                                Image {
                                    source: assetRoot + "icons/check.svg"
                                    sourceSize: Qt.size(32, 32)
                                    Layout.preferredWidth: 16; Layout.preferredHeight: 16
                                }
                                Text {
                                    textFormat: Text.PlainText
                                    text: "Распознавание речи готово"
                                    color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 13
                                    Layout.fillWidth: true
                                }
                            }
                            ColumnLayout {
                                visible: welcome.config.setupBusy || welcome.config.asrChecking || welcome.config.setupPhase==="paused"
                                Layout.fillWidth: true; spacing: 8
                                ProgressBar { Layout.fillWidth: true; indeterminate: welcome.config.asrChecking || welcome.config.setupFraction<0 || welcome.config.setupPhase==="verifying"; value: Math.max(0,welcome.config.setupFraction); palette.highlight: "#b9b1f0" }
                                Text { textFormat: Text.PlainText; text: welcome.config.setupLabel; color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                Text { textFormat: Text.PlainText; visible: welcome.config.setupBusy && welcome.config.setupSpeed>0 && welcome.config.setupPhase==="downloading"; text: (welcome.config.setupSpeed/1e6).toFixed(1)+" МБ/с · "+Math.min(99,Math.round(welcome.config.setupFraction*100))+"%"; color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 11 }
                                PButton { objectName: "pauseModelDownload"; visible: welcome.config.setupBusy; text: "Приостановить"; quiet: true; onClicked: bridge.cancelSetup() }
                            }
                            Text { textFormat: Text.PlainText; objectName: "onboardingError"; visible: welcome.config.setupError.length>0; text: welcome.config.setupError; color: "#f0b9ae"; font.family: "Onest"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            RowLayout {
                                visible: !welcome.config.asrReady && !welcome.config.setupBusy && !welcome.config.asrChecking
                                Layout.fillWidth: true
                                spacing: 8
                                PButton {
                                    objectName: "downloadSpeechModel"
                                    text: welcome.config.setupError.length ? "Повторить загрузку"
                                        : welcome.config.setupCanResume ? "Продолжить загрузку" : "Скачать модель · 225 МБ"
                                    iconName: "download"
                                    primary: true
                                    onClicked: bridge.downloadModel()
                                }
                                PButton {
                                    objectName: "chooseExistingModel"
                                    text: "Модель уже есть"
                                    hint: "Выбрать папку с моделью GigaAM"
                                    quiet: true
                                    onClicked: bridge.chooseModelFolder()
                                }
                            }
                            SegmentationSetup {
                                objectName: "onboardingSegmentation"
                                config: welcome.config
                                showComparison: true
                                Layout.fillWidth: true
                                Layout.topMargin: 32
                            }
                        }
                    }
                    ScrollView {
                        id: page1
                        clip: true
                        contentWidth: availableWidth
                        ColumnLayout {
                            width: page1.availableWidth
                            spacing: 16
                            RowLayout {
                                Layout.fillWidth: true; spacing: 14
                                Image { source: assetRoot+"ollama-light.svg"; fillMode: Image.PreserveAspectFit; Layout.preferredWidth: 32; Layout.preferredHeight: 46; sourceSize: Qt.size(64,92) }
                                Text { textFormat: Text.PlainText; text: "Подключите поиск по смыслу"; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 24; font.weight: Font.Medium; Layout.fillWidth: true }
                            }
                            Text { textFormat: Text.PlainText; text: "Чтобы искать в записи по теме, выберите модель из Ollama. Этот шаг можно пропустить."; color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 13; lineHeight: 1.45; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            RowLayout {
                                Layout.fillWidth: true
                                Text { textFormat: Text.PlainText; text: welcome.config.ollamaState==="checking" ? "Проверяем Ollama…" : welcome.config.ollamaState==="ready" || welcome.config.ollamaState==="empty" ? "Ollama подключена" : welcome.config.ollamaInstalled ? "Ollama нужно запустить" : "Для поиска нужна Ollama"; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 14; Layout.fillWidth: true }
                                PButton { objectName: "onboardingRefreshOllama"; iconName: "refresh-cw"; quiet: true; hint: "Обновить модели"; enabled: welcome.config.ollamaState!=="checking"; onClicked: bridge.refreshOllama() }
                            }
                            ColumnLayout {
                                visible: welcome.config.ollamaState==="ready" || welcome.config.ollamaState==="empty"
                                Layout.fillWidth: true; spacing: 8
                                Label { text: "Модель для поиска"; color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 12 }
                                ModelChoice { objectName: "onboardingModelChoice"; config: welcome.config; Layout.fillWidth: true; enabled: count>0 }
                                Text { textFormat: Text.PlainText; text: bridge.meaningModels.length===0 ? "Добавьте локальную модель до 3 ГБ в Ollama и обновите список." : welcome.selectedAvailable ? "Выбор сохранён. Поиск запускается только по вашему запросу." : "Выберите установленную модель до 3 ГБ."; color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            }
                            RowLayout {
                                visible: welcome.config.ollamaState!=="ready" && welcome.config.ollamaState!=="empty" && welcome.config.ollamaState!=="checking"
                                PButton { objectName: "onboardingLaunchOllama"; text: welcome.config.ollamaInstalled ? "Запустить Ollama" : "Установить Ollama"; iconName: welcome.config.ollamaInstalled ? "play" : "external-link"; onClicked: welcome.config.ollamaInstalled ? bridge.launchOllama() : bridge.installOllama() }
                            }
                            Text { textFormat: Text.PlainText; visible: welcome.config.ollamaState==="offline"; text: "Запустите Ollama и обновите список моделей."; color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12; lineHeight: 1.4; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        }
                    }
                    ScrollView {
                        id: page2
                        clip: true
                        contentWidth: availableWidth
                        ColumnLayout {
                            width: page2.availableWidth
                            spacing: 20
                            Image { source: assetRoot+"icons/check.svg"; sourceSize: Qt.size(64,64); Layout.preferredWidth: 32; Layout.preferredHeight: 32 }
                            Text { textFormat: Text.PlainText; text: "Откройте первую запись"; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 27; font.weight: Font.Medium; lineHeight: 1.15; Layout.fillWidth: true }
                            Text { textFormat: Text.PlainText; text: "Выберите аудио или видео. Если GigaAM настроена, плеер начнёт расшифровку автоматически."; color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 14; lineHeight: 1.45; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 12
                                Text { textFormat: Text.PlainText; text: "Распознавание речи · "+(welcome.config.asrReady ? "готово" : "можно настроить позже"); color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                Text { textFormat: Text.PlainText; text: "Смысловой поиск · "+(welcome.selectedAvailable ? "модель выбрана" : "можно настроить позже"); color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                            }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    PButton { objectName: "onboardingBack"; visible: welcome.config.step>0; text: "Назад"; quiet: true; enabled: !welcome.config.setupBusy; onClicked: bridge.setStep(welcome.config.step-1) }
                    Item { Layout.fillWidth: true }
                    PButton {
                        objectName: "onboardingContinue"
                        text: welcome.config.step === 2 ? "Открыть запись"
                            : welcome.config.step === 0 && !welcome.config.asrReady ? "Продолжить без расшифровки"
                            : "Продолжить"
                        primary: welcome.config.step !== 0 || welcome.config.asrReady
                        iconName: welcome.config.step === 2 ? "folder-open" : "arrow-right"
                        enabled: !welcome.config.setupBusy && !(welcome.config.step === 0 && welcome.config.asrChecking)
                        onClicked: {
                            if (welcome.config.step === 2) bridge.finishSetupAndOpen()
                            else bridge.setStep(welcome.config.step+1)
                        }
                    }
                }
            }
        }
    }
}
