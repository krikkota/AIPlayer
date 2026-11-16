import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ComboBox {
    id: choice
    required property var config
    objectName: "modelChoice"
    Layout.fillWidth: true
    implicitHeight: 36
    model: bridge.meaningModels
    textRole: "name"
    currentIndex: model.findIndex(item => item.name===choice.config.selectedModel)
    displayText: currentIndex>=0 ? currentText : choice.config.selectedModel || "Выберите модель"
    enabled: choice.config.ollamaState!=="checking" && count>0
    Accessible.name: "Модель смыслового поиска"
    onActivated: index => bridge.selectOllamaModel(model[index].name)
    leftPadding: 12; rightPadding: 32
    contentItem: Text { textFormat: Text.PlainText; text: choice.displayText; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter; elide: Text.ElideMiddle }
    indicator: Image { x: parent.width-width-12; y: (parent.height-height)/2; width: 14; height: 14; source: assetRoot+"icons/chevron-down.svg"; sourceSize: Qt.size(28,28) }
    background: Rectangle { color: "#101010"; radius: 8; border.color: choice.visualFocus ? "#b9b1f0" : "#3a3a3e" }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        objectName: "meaningModelOption_"+index
        width: choice.width
        implicitHeight: 36
        highlighted: choice.highlightedIndex===index
        contentItem: Text { textFormat: Text.PlainText; text: modelData.name; color: "#eeeef0"; font.family: "Onest"; font.pixelSize: 13; elide: Text.ElideMiddle; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 6; color: parent.highlighted ? "#302b3b" : "transparent" }
    }
    popup: Popup {
        y: choice.height+4; width: choice.width
        padding: 4
        implicitHeight: Math.min(240, choices.contentHeight+8)
        background: Rectangle { color: "#202022"; radius: 8; border.color: "#3a3a3e" }
        contentItem: ListView {
            id: choices
            clip: true; implicitHeight: contentHeight
            model: choice.popup.visible ? choice.delegateModel : null
            currentIndex: choice.highlightedIndex
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        }
    }
}
