import QtQuick
import QtQuick.Controls

TextField {
    id: control
    implicitHeight: 34
    color: "#eeeef0"
    placeholderTextColor: "#a1a1aa"
    selectionColor: "#5b526f"
    selectedTextColor: "#ffffff"
    font.family: "Onest"
    font.pixelSize: 13
    leftPadding: 15
    rightPadding: 15
    background: Rectangle {
        radius: 8
        color: "#181818"
        border.width: 1
        border.color: control.activeFocus ? "#b9b1f0" : "#303034"
    }
}

