import QtQuick
import QtQuick.Controls

SpinBox {
    id:control
    implicitWidth:60;implicitHeight:32
    leftPadding:7;rightPadding:18;topPadding:0;bottomPadding:0
    editable:true;hoverEnabled:true
    font.family:"Onest";font.pixelSize:12
    background:Rectangle{radius:7;color:"#101010";border.color:control.activeFocus?"#b9b1f0":"#38383b"}
    contentItem:TextInput {
        text:control.textFromValue(control.value,control.locale)
        font:control.font;color:"#eeeef0";selectionColor:"#5b526f";selectedTextColor:"#ffffff"
        horizontalAlignment:TextInput.AlignHCenter;verticalAlignment:TextInput.AlignVCenter
        validator:control.validator;inputMethodHints:Qt.ImhDigitsOnly
        readOnly:!control.editable
    }
    up.indicator:Rectangle {
        x:control.width-width;y:0;width:17;height:control.height/2
        radius:4;color:control.up.pressed?"#38383b":control.up.hovered?"#252527":"transparent"
        Image{anchors.centerIn:parent;width:10;height:10;rotation:180;source:assetRoot+"icons/chevron-down.svg";sourceSize:Qt.size(20,20)}
    }
    down.indicator:Rectangle {
        x:control.width-width;y:control.height/2;width:17;height:control.height/2
        radius:4;color:control.down.pressed?"#38383b":control.down.hovered?"#252527":"transparent"
        Image{anchors.centerIn:parent;width:10;height:10;source:assetRoot+"icons/chevron-down.svg";sourceSize:Qt.size(20,20)}
    }
}
