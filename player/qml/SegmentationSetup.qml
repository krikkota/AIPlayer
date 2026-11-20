import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: section
    required property var config
    property bool showComparison: false
    spacing: section.showComparison ? 11 : 9

    Rectangle { visible: !section.showComparison; Layout.fillWidth: true; implicitHeight: 1; color: "#29292d" }

    RowLayout {
        Layout.fillWidth: true
        spacing: 12

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Text {
                textFormat: Text.PlainText
                text: "Более цельные фразы"
                color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 14
            }
            Text {
                textFormat: Text.PlainText
                text: "Если человек сделал паузу посреди предложения, улучшение помогает сохранить фразу целиком."
                    + (section.showComparison ? " Его можно включить позже в настройках." : "")
                color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 12
                wrapMode: Text.WordWrap; Layout.fillWidth: true
            }
        }

        Text {
            visible: section.showComparison && !section.config.satInstalled
            textFormat: Text.PlainText
            text: "По желанию"
            color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 12
            Layout.alignment: Qt.AlignTop
        }

        Switch {
            objectName: "segmentationEnabled"
            visible: section.config.satInstalled && !section.config.satDownloading
            checked: section.config.satEnabled
            Accessible.name: "Улучшенное разбиение фраз"
            onToggled: bridge.setSegmentationEnabled(checked)
        }
    }

    Text {
        visible: section.showComparison
        textFormat: Text.PlainText
        text: "Потяните границу в примере, чтобы увидеть разницу."
        color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12
        wrapMode: Text.WordWrap; Layout.fillWidth: true
    }

    Loader {
        active: section.showComparison
        visible: active
        Layout.fillWidth: true
        sourceComponent: PhraseComparison {}
    }

    RowLayout {
        visible: !section.config.satInstalled || section.config.satDownloading
        Layout.fillWidth: true
        spacing: 12

        PButton {
            objectName: "downloadSegmentation"
            text: section.config.satDownloading ? "Приостановить" : "Скачать · 251 МБ"
            iconName: section.config.satDownloading ? "" : "download"
            onClicked: section.config.satDownloading ? bridge.pauseSegmentationDownload() : bridge.downloadSegmentation()
        }
        Text {
            visible: !section.showComparison && !section.config.satDownloading && !section.config.satDownloadMessage
            textFormat: Text.PlainText
            text: "По желанию"
            color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 12
        }
    }

    ProgressBar {
        visible: section.config.satDownloading
        Layout.fillWidth: true
        indeterminate: section.config.satFraction < 0
        value: Math.max(0, section.config.satFraction)
        palette.highlight: "#b9b1f0"
    }
    Text {
        visible: text.length > 0
        textFormat: Text.PlainText
        text: section.config.satDownloadMessage || section.config.satNotice
        color: "#b6b6bd"; font.family: "Onest"; font.pixelSize: 12
        wrapMode: Text.WordWrap; Layout.fillWidth: true
    }
}
