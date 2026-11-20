import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: comparison
    implicitHeight: Math.max(splitExample.implicitHeight, joinedExample.implicitHeight) + 59
    radius: 10
    color: "#18181b"
    border.color: "#363439"

    readonly property real seam: inset.width * divider.visualPosition
    readonly property string firstPart: "Давайте оставим этот раздел,"
    readonly property string secondPart: "а остальное обсудим завтра."

    Item {
        id: inset
        anchors.fill: parent
        anchors.margins: 1

        Item {
            width: comparison.seam
            height: parent.height
            clip: true

            Example {
                id: splitExample
                objectName: "standardPhraseExample"
                x: 12; y: 39
                width: inset.width - 24
                combine: false
            }
        }

        Item {
            x: comparison.seam
            width: parent.width - x
            height: parent.height
            clip: true

            Rectangle {
                x: -comparison.seam
                width: inset.width
                height: parent.height
                radius: 9
                color: "#22212a"
            }

            Example {
                id: joinedExample
                objectName: "combinedPhraseExample"
                x: 12 - comparison.seam; y: 39
                width: inset.width - 24
                combine: true
            }
        }

        Slider {
            id: divider
            objectName: "phraseComparisonDivider"
            anchors.fill: parent
            padding: 0
            value: 0.5
            stepSize: 0.1
            focusPolicy: Qt.StrongFocus
            Accessible.name: "Граница сравнения обычного и цельного текста"
            background: Item {}
            handle: Item {
                x: comparison.seam
                width: 0
                height: divider.height

                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 2; height: parent.height
                    color: "#beb6e0"
                }
                Rectangle {
                    x: Math.min(Math.max(-width / 2, 2 - comparison.seam),
                                inset.width - comparison.seam - width - 2)
                    anchors.verticalCenter: parent.verticalCenter
                    width: 34; height: 34; radius: 17
                    color: divider.pressed ? "#c8bfef" : "#ecebf2"
                    border.color: divider.visualFocus ? "#957bc9" : "#ecebf2"
                    border.width: divider.visualFocus ? 2 : 1

                    Row {
                        anchors.centerIn: parent
                        spacing: 1
                        Image { width: 12; height: 12; source: assetRoot + "icons/chevron-left-dark.svg" }
                        Image { width: 12; height: 12; source: assetRoot + "icons/chevron-right-dark.svg" }
                    }
                }
            }

            HoverHandler { cursorShape: Qt.SizeHorCursor }
        }

        PButton {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.margins: 7
            text: "Обычное разбиение"
            implicitHeight: 24
            font.pixelSize: 11
            onClicked: divider.value = 1
        }
        PButton {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 7
            text: "Фраза целиком"
            implicitHeight: 24
            font.pixelSize: 11
            onClicked: divider.value = 0
        }
    }

    component Example: ColumnLayout {
        required property bool combine
        spacing: 7

        ExampleLine {
            time: "00:12"
            phrase: combine ? comparison.firstPart + " " + comparison.secondPart : comparison.firstPart
        }
        ExampleLine {
            visible: !combine
            time: "00:15"
            phrase: comparison.secondPart
        }
    }

    component ExampleLine: RowLayout {
        id: line
        required property string time
        required property string phrase
        Layout.fillWidth: true
        spacing: 8

        Text {
            textFormat: Text.PlainText
            text: line.time
            Layout.preferredWidth: 34; Layout.alignment: Qt.AlignTop
            color: "#c8bfef"; font.family: "Onest"; font.pixelSize: 11
        }
        Text {
            textFormat: Text.PlainText
            text: line.phrase
            Layout.fillWidth: true; wrapMode: Text.WordWrap
            color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 13
            lineHeight: 1.25
        }
    }
}
