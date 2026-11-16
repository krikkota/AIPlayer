import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: control
    property string iconName: ""
    property bool primary: false
    property bool quiet: false
    property bool iconTrailing: false
    property string hint: ""
    property int iconSize: 16
    property bool circular: false
    implicitHeight: 32
    implicitWidth: text.length ? Math.max(32, contents.implicitWidth + leftPadding + rightPadding) : implicitHeight
    leftPadding: text.length ? 14 : 8
    rightPadding: leftPadding
    topPadding: 0
    bottomPadding: 0
    hoverEnabled: true
    font.family: "Onest"
    font.pixelSize: 13
    Accessible.name: text || hint
    ToolTip {
        visible: control.enabled && control.hovered && control.hint.length>0
        text:control.hint;delay:550;padding:8
        contentItem:Text{ textFormat: Text.PlainText;text:control.hint;color:"#eeeef0";font.family:"Onest";font.pixelSize:12}
        background:Rectangle{color:"#242426";radius:6;border.color:"#3a3a3e"}
    }
    opacity: enabled ? 1 : 0.38
    background: Rectangle {
        radius: control.circular ? height / 2 : 8
        color: control.primary ? (control.down ? "#cdcbd6" : control.hovered ? "#ffffff" : "#ecebf2")
                               : (control.down ? "#303032" : control.checked ? "#272430" : control.hovered ? "#252527" : control.quiet ? "transparent" : "#181818")
        border.width: control.primary || control.quiet ? 0 : 1
        border.color: "#303034"
        Behavior on color { ColorAnimation { duration: 120 } }
        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: parent.radius + 2
            color: "transparent"
            border.color: "#b9b1f0"
            border.width: control.visualFocus ? 1 : 0
        }
    }
    contentItem: Item {
        implicitWidth: contents.implicitWidth
        implicitHeight: contents.implicitHeight
      Row {
        id: contents
        spacing: 8
        layoutDirection: control.iconTrailing || (control.primary && control.iconName==="arrow-right") ? Qt.RightToLeft : Qt.LeftToRight
        anchors.centerIn: parent
        width: implicitWidth
        height: implicitHeight
        Image {
            objectName:control.objectName+"Icon"
            visible: control.iconName.length > 0
            source: visible ? assetRoot + "icons/" + control.iconName + (control.primary ? "-dark" : "") + ".svg" : ""
            width: control.iconSize
            height: control.iconSize
            anchors.verticalCenter: parent.verticalCenter
            sourceSize: Qt.size(width * 2, height * 2)
            fillMode: Image.PreserveAspectFit
            opacity: control.primary || control.hovered || control.down || control.checked ? 1 : .82
            transform:Translate{x:control.iconName==="play-filled"?1:0}
        }
        Text { textFormat: Text.PlainText;
            visible: control.text.length > 0
            text: control.text
            color: control.primary ? "#101010" : "#eeeef0"
            font: control.font
            anchors.verticalCenter: parent.verticalCenter
        }
      }
    }
}

