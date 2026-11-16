import QtQuick

Item {
    id: root
    property var peaks: []
    property real duration: 0
    property real position: 0
    property real viewStart: 0
    property real viewEnd: Math.max(1, duration)
    property real selectionStart: -1
    property real selectionEnd: -1
    property bool editable: false
    signal seek(real seconds)
    signal selectionEdited(real start, real end)
    implicitHeight: 92
    clip: true
    readonly property real tickStep: {
        const wanted=(viewEnd-viewStart)/6
        for(let value of [1,2,5,10,15,30,60,120,300,600,900,1800,3600,7200]) if(value>=wanted) return value
        return 14400
    }
    readonly property var ticks: {
        let values=[]
        for(let t=Math.ceil(viewStart/tickStep)*tickStep;t<=viewEnd;t+=tickStep) values.push(t)
        return values
    }
    function coordinate(t) { return (t - viewStart) / Math.max(0.001, viewEnd - viewStart) * width }
    function timeAt(x) { return Math.max(0, Math.min(duration, viewStart + x / Math.max(1,width) * (viewEnd-viewStart))) }
    onPeaksChanged: drawing.requestPaint()
    onPositionChanged: drawing.requestPaint()
    onSelectionStartChanged: drawing.requestPaint()
    onSelectionEndChanged: drawing.requestPaint()
    onViewStartChanged: drawing.requestPaint()
    onViewEndChanged: drawing.requestPaint()
    onWidthChanged: drawing.requestPaint()
    Rectangle {
        visible:root.editable && root.selectionEnd>root.selectionStart
        x:root.coordinate(root.selectionStart);y:26
        width:root.coordinate(root.selectionEnd)-x;height:root.height-34
        radius:7;color:"#24212e";border.color:"#8c81a9";border.width:1
    }
    Repeater {
        model:root.ticks
        Text { textFormat: Text.PlainText;
            required property real modelData
            x:Math.max(0,Math.min(root.width-width,root.coordinate(modelData)-width/2));y:0
            text:bridge.formatTime(modelData);color:"#a1a1aa";font.family:"Onest";font.pixelSize:11
        }
    }
    Canvas {
        id: drawing
        anchors.fill: parent
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const top = 26, h = height - top - 8, center = top + h / 2
            const left = root.coordinate(root.selectionStart), right = root.coordinate(root.selectionEnd)
            for (let t=Math.ceil(root.viewStart/(root.tickStep/5))*(root.tickStep/5);t<=root.viewEnd;t+=root.tickStep/5) {
                const x=root.coordinate(t),major=Math.abs(t/root.tickStep-Math.round(t/root.tickStep))<.01
                ctx.fillStyle=major?"#727279":"#38383b"
                ctx.fillRect(x,major?19:22,1,major?7:4)
            }
            const bars = Math.floor(width/4)
            for (let i=0; i<bars; i++) {
                const x = i*4+1
                const t = root.viewStart + x/width*(root.viewEnd-root.viewStart)
                const index = Math.min(root.peaks.length-1, Math.floor(t/Math.max(1,root.duration)*root.peaks.length))
                const value = root.peaks[index] || 0
                const bar = Math.max(2,value*h*.85)
                ctx.fillStyle = root.editable && t>=root.selectionStart && t<=root.selectionEnd ? "#b9b1f0" : "#727279"
                ctx.fillRect(x,center-bar/2,2,bar)
            }
            if (root.position>=root.viewStart && root.position<=root.viewEnd) {
                const x = root.coordinate(root.position)
                ctx.fillStyle = "#eeeef0"
                ctx.fillRect(x,top-4,1,h+8)
                ctx.beginPath();ctx.arc(x,top-4,3,0,Math.PI*2);ctx.fill()
            }
        }
    }
    Repeater {
        model: root.editable ? 2 : 0
        Rectangle {
            required property int index
            x: root.coordinate(index === 0 ? root.selectionStart : root.selectionEnd)-3
            y: 26+(root.height-34)/2-15
            width: 6
            height: 30
            radius: 3
            color: "#c8c1ef"
            visible: x>=-4 && x<=root.width
        }
    }
    MouseArea {
        anchors.fill: parent
        property int dragHandle: -1
        cursorShape: root.editable ? Qt.SizeHorCursor : Qt.PointingHandCursor
        onPressed: mouse => {
            let a=Math.abs(mouse.x-root.coordinate(root.selectionStart))
            let b=Math.abs(mouse.x-root.coordinate(root.selectionEnd))
            dragHandle = root.editable && Math.min(a,b)<18 ? (a<=b ? 0 : 1) : -1
            if (dragHandle<0) root.seek(root.timeAt(mouse.x))
        }
        onPositionChanged: mouse => {
            if (!pressed) return
            let t=root.timeAt(mouse.x)
            if (dragHandle===0) root.selectionEdited(Math.min(t,root.selectionEnd-.1),root.selectionEnd)
            else if (dragHandle===1) root.selectionEdited(root.selectionStart,Math.max(t,root.selectionStart+.1))
            else root.seek(t)
        }
        onReleased: dragHandle=-1
    }
}

