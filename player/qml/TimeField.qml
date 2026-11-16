import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    property string label: ""
    property real seconds: 0
    readonly property bool popupVisible: picker.visible
    signal edited(real value)
    function displayTime(value) {
        const millis=Math.round(value*1000)
        const fraction=millis%1000
        return bridge.formatTime(millis/1000)+(fraction?"."+String(fraction).padStart(3,"0").replace(/0+$/,""):"")
    }
    spacing: 5
    Layout.preferredWidth: 100
    Layout.minimumWidth: 82
    Layout.maximumWidth: 116
    Text { textFormat: Text.PlainText; text: root.label; color: "#a1a1aa"; font.family: "Onest"; font.pixelSize: 11 }
    PField {
        id: input
        property bool modified: false
        objectName: root.objectName + "Input"
        Layout.fillWidth: true
        implicitWidth: 100
        implicitHeight: 34
        leftPadding:10;rightPadding:28
        text: root.displayTime(root.seconds)
        horizontalAlignment: Text.AlignHCenter
        Accessible.name: root.label
        validator: RegularExpressionValidator { regularExpression: /\d{1,3}:[0-5]\d(?::[0-5]\d)?(?:\.\d{1,3})?/ }
        onTextEdited: modified=true
        onEditingFinished: {
            if(!modified) return
            modified=false
            let pieces = text.split(":")
            let value = 0
            for (let piece of pieces) value = value * 60 + Number(piece)
            if (acceptableInput && Number.isFinite(value)) root.edited(value)
            text=Qt.binding(function(){return root.displayTime(root.seconds)})
        }
        Keys.onUpPressed:root.edited(root.seconds+1)
        Keys.onDownPressed:root.edited(Math.max(0,root.seconds-1))
        PButton {
            anchors.right:parent.right;anchors.verticalCenter:parent.verticalCenter
            implicitHeight:30;implicitWidth:26;leftPadding:6;rightPadding:6
            iconName:"chevron-down";iconSize:12;quiet:true
            hint:"Выбрать точное время";onClicked:picker.open()
        }
        Popup {
            id:picker
            objectName:root.objectName+"Picker"
            y:-height-8;width:292;height:166;padding:14;focus:true
            closePolicy:Popup.CloseOnEscape|Popup.CloseOnPressOutside
            background:Rectangle{color:"#181818";radius:14;border.color:"#38383b"}
            onOpened:{hours.value=Math.floor(root.seconds/3600);minutes.value=Math.floor(root.seconds/60)%60;secs.value=Math.floor(root.seconds)%60;millis.value=Math.round(root.seconds*1000)%1000}
            ColumnLayout {
                anchors.fill:parent;spacing:10
                Text{ textFormat: Text.PlainText;text:root.label+" фрагмента";color:"#eeeef0";font.family:"Onest";font.pixelSize:13}
                RowLayout {
                    Layout.fillWidth:true;spacing:6
                    ColumnLayout{spacing:4;Layout.fillWidth:true
                        Text{ textFormat: Text.PlainText;text:"Часы";color:"#a1a1aa";font.family:"Onest";font.pixelSize:10}
                        TimeSpin{id:hours;Layout.fillWidth:true;from:0;to:999;Accessible.name:"Часы"}
                    }
                    ColumnLayout{spacing:4;Layout.fillWidth:true
                        Text{ textFormat: Text.PlainText;text:"Минуты";color:"#a1a1aa";font.family:"Onest";font.pixelSize:10}
                        TimeSpin{id:minutes;Layout.fillWidth:true;from:0;to:59;Accessible.name:"Минуты"}
                    }
                    ColumnLayout{spacing:4;Layout.fillWidth:true
                        Text{ textFormat: Text.PlainText;text:"Секунды";color:"#a1a1aa";font.family:"Onest";font.pixelSize:10}
                        TimeSpin{id:secs;Layout.fillWidth:true;from:0;to:59;Accessible.name:"Секунды"}
                    }
                    ColumnLayout{spacing:4;Layout.fillWidth:true
                        Text{ textFormat: Text.PlainText;text:"мс";color:"#a1a1aa";font.family:"Onest";font.pixelSize:10}
                        TimeSpin{id:millis;objectName:root.objectName+"Millis";Layout.fillWidth:true;from:0;to:999;Accessible.name:"Миллисекунды"}
                    }
                }
                PButton{objectName:root.objectName+"Apply";text:"Применить";primary:true;Layout.alignment:Qt.AlignRight;onClicked:{root.edited(hours.value*3600+minutes.value*60+secs.value+millis.value/1000);picker.close()}}
            }
        }
    }
}

